"""The AI coach's API: `/athletes/{id}/ai-coach/…` for the athlete (and,
read-only, their coach: reports and proposals), `/admin/ai-coach` for the
platform admin who turns it on."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access, require_platform_admin
from app.auth.models import User
from app.coach_ai import proposals as proposal_service
from app.coach_ai import service
from app.coach_ai.access import (
    CapReached,
    access_row,
    cap_of,
    cost_usd,
    is_usable,
    month_start,
    month_tokens,
    require_ai_coach,
    require_ai_enabled,
)
from app.coach_ai.client import MistralClient, ai_coach_available
from app.coach_ai.context import today_of
from app.coach_ai.models import (
    AiCoachAccess,
    AiCoachProfile,
    AiConversation,
    AiMessage,
    AiProposal,
    AiReport,
    AiUsage,
    ConversationKind,
    ProposalStatus,
    ReportKind,
)
from app.coach_ai.ports import LlmClientPort, LlmError
from app.coach_ai.reports import generate_report, report_read
from app.coach_ai.schemas import (
    AccessRead,
    AdminAiOverview,
    AdminAiRow,
    AdminAiUpdate,
    CoachProfileRead,
    CoachProfileWrite,
    CoachSettings,
    ConsentWithdraw,
    ConversationCreate,
    ConversationRead,
    ConversationSummary,
    MessageCreate,
    ProposalRead,
    ReportRead,
    TurnRead,
    UsageRead,
)
from app.connections.intervals_router import PlanPusher, get_plan_pusher, push_now
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.base import utcnow
from app.db.session import get_db

router = APIRouter(prefix="/athletes/{athlete_id}/ai-coach", tags=["ai-coach"])
admin_router = APIRouter(prefix="/admin/ai-coach", tags=["admin"], dependencies=[Depends(require_platform_admin)])

_INTAKE_KICKOFF = {
    "fr": "Je veux un programme d'entraînement pour atteindre mon objectif.",
    "en": "I want a training program to reach my goal.",
}
_INTAKE_TITLE = {"fr": "Programme d'entraînement", "en": "Training program"}


def get_llm_client() -> LlmClientPort:
    return MistralClient()


def _model_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CapReached):
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "ai_coach_cap_reached")
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "ai_coach_failed")


# --- access & consent ---------------------------------------------------------------


async def _access_read(db: AsyncSession, athlete: Athlete, viewer: User) -> AccessRead:
    access = await access_row(db, athlete.id)
    is_self = athlete.user_id == viewer.id
    enabled = bool(access and access.enabled)
    usage = None
    if is_self and enabled:
        usage = UsageRead(month_tokens=await month_tokens(db, athlete.id), monthly_cap=cap_of(access))
    return AccessRead(
        available=ai_coach_available(),
        enabled=enabled,
        consented=bool(access and access.consent_at),
        is_self=is_self,
        can_use=is_self and is_usable(access),
        usage=usage,
        provider="Mistral AI",
        model=get_settings().mistral_model,
    )


@router.get("", response_model=AccessRead)
async def get_access(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessRead:
    return await _access_read(db, athlete, current_user)


@router.post("/consent", response_model=AccessRead)
async def give_consent(
    athlete: Athlete = Depends(require_ai_enabled),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessRead:
    access = await access_row(db, athlete.id)
    if access.consent_at is None:
        access.consent_at = utcnow()
        await db.commit()
    return await _access_read(db, athlete, current_user)


async def forget_history(db: AsyncSession, athlete_id: uuid.UUID) -> None:
    """Conversations, reports, pending proposals and the intake (not the plans
    the athlete accepted, which are theirs; not the usage, the admin's bill)."""
    conversation_ids = select(AiConversation.id).where(AiConversation.athlete_id == athlete_id)
    await db.execute(delete(AiReport).where(AiReport.athlete_id == athlete_id))
    await db.execute(delete(AiProposal).where(AiProposal.athlete_id == athlete_id))
    await db.execute(delete(AiMessage).where(AiMessage.conversation_id.in_(conversation_ids)))
    await db.execute(delete(AiConversation).where(AiConversation.athlete_id == athlete_id))
    await db.execute(delete(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete_id))


@router.post("/consent/withdraw", response_model=AccessRead)
async def withdraw_consent(
    payload: ConsentWithdraw,
    athlete: Athlete = Depends(require_ai_enabled),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessRead:
    access = await access_row(db, athlete.id)
    access.consent_at = None
    if payload.delete_history:
        await forget_history(db, athlete.id)
    else:  # nothing waits for an answer the athlete can no longer give
        for proposal in await db.scalars(
            select(AiProposal).where(AiProposal.athlete_id == athlete.id, AiProposal.status == ProposalStatus.PENDING.value)
        ):
            proposal.status = ProposalStatus.EXPIRED.value
    await db.commit()
    return await _access_read(db, athlete, current_user)


# --- intake profile & settings --------------------------------------------------------


async def _profile_read(db: AsyncSession, athlete: Athlete) -> CoachProfileRead:
    access = await access_row(db, athlete.id)
    row = await db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete.id))
    return CoachProfileRead(
        answers=await proposal_service.profile_answers(db, athlete.id),
        settings=CoachSettings(
            weekly_reports=access.weekly_reports, report_weekday=access.report_weekday, report_hour=access.report_hour
        ),
        program=row.program if row else None,
    )


@router.get("/profile", response_model=CoachProfileRead)
async def get_profile(athlete: Athlete = Depends(require_ai_coach), db: AsyncSession = Depends(get_db)) -> CoachProfileRead:
    return await _profile_read(db, athlete)


@router.put("/profile", response_model=CoachProfileRead)
async def put_profile(
    payload: CoachProfileWrite, athlete: Athlete = Depends(require_ai_coach), db: AsyncSession = Depends(get_db)
) -> CoachProfileRead:
    if payload.answers is not None:
        row = await db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete.id))
        if row is None:
            row = AiCoachProfile(athlete_id=athlete.id, answers={})
            db.add(row)
        row.answers = payload.answers.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        row.updated_at = utcnow()
    if payload.settings is not None:
        access = await access_row(db, athlete.id)
        access.weekly_reports = payload.settings.weekly_reports
        access.report_weekday = payload.settings.report_weekday
        access.report_hour = payload.settings.report_hour
    await db.commit()
    return await _profile_read(db, athlete)


# --- conversations -----------------------------------------------------------------------


@router.get("/conversations", response_model=list[ConversationSummary])
async def conversations(athlete: Athlete = Depends(require_ai_coach), db: AsyncSession = Depends(get_db)):
    return await service.list_conversations(db, athlete.id)


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def conversation(
    conversation_id: uuid.UUID,
    athlete: Athlete = Depends(require_ai_coach),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    found = await service.get_conversation(db, athlete.id, conversation_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return await service.conversation_read(db, athlete, current_user, found)


async def _turn_read(db, athlete, user, conversation_id, messages) -> TurnRead:
    return TurnRead(conversation_id=conversation_id, messages=await service.message_reads(db, athlete, user, messages))


@router.post("/conversations", response_model=TurnRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_conversation(
    request: Request,
    payload: ConversationCreate,
    athlete: Athlete = Depends(require_ai_coach),
    current_user: User = Depends(get_current_user),
    client: LlmClientPort = Depends(get_llm_client),
    db: AsyncSession = Depends(get_db),
) -> TurnRead:
    locale = service.locale_of(current_user)
    content = payload.content.strip() if payload.content else None
    if payload.kind == "chat" and not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A chat starts with a message")
    kind = ConversationKind(payload.kind)
    title = service.title_from(content) if kind is ConversationKind.CHAT else _INTAKE_TITLE[locale]
    conversation = await service.start_conversation(db, athlete, kind, title)
    conversation_id = conversation.id
    try:
        messages, _ = await service.run_turn(
            db,
            client,
            athlete,
            conversation,
            user_text=content or _INTAKE_KICKOFF[locale],
            hidden_user_text=content is None,
        )
    except (CapReached, LlmError) as exc:
        raise _model_error(exc) from exc
    return await _turn_read(db, athlete, current_user, conversation_id, messages)


@router.post("/conversations/{conversation_id}/messages", response_model=TurnRead)
@limiter.limit("20/minute")
async def post_message(
    request: Request,
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    athlete: Athlete = Depends(require_ai_coach),
    current_user: User = Depends(get_current_user),
    client: LlmClientPort = Depends(get_llm_client),
    db: AsyncSession = Depends(get_db),
) -> TurnRead:
    found = await service.get_conversation(db, athlete.id, conversation_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    try:
        messages, _ = await service.run_turn(db, client, athlete, found, user_text=payload.content)
    except (CapReached, LlmError) as exc:
        raise _model_error(exc) from exc
    return await _turn_read(db, athlete, current_user, conversation_id, messages)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, athlete: Athlete = Depends(require_ai_coach), db: AsyncSession = Depends(get_db)
) -> Response:
    found = await service.get_conversation(db, athlete.id, conversation_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    await db.execute(delete(AiMessage).where(AiMessage.conversation_id == found.id))
    for model in (AiReport, AiProposal):
        for row in await db.scalars(select(model).where(model.conversation_id == found.id)):
            row.conversation_id = None
    await db.delete(found)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- proposals ------------------------------------------------------------------------------


@router.get("/proposals", response_model=list[ProposalRead])
async def proposals(
    status_filter: ProposalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProposalRead]:
    """Newest first. The athlete's coach reads them too (never the chat)."""
    query = select(AiProposal).where(AiProposal.athlete_id == athlete.id)
    if status_filter is not None:
        query = query.where(AiProposal.status == status_filter.value)
    rows = list(await db.scalars(query.order_by(AiProposal.created_at.desc()).limit(limit)))
    reads = [await proposal_service.read_proposal(db, athlete, row, current_user) for row in rows]
    await db.commit()  # expired ones were marked
    if status_filter is not None:
        reads = [r for r in reads if r.status == status_filter]
    return reads


async def _own_proposal(db: AsyncSession, athlete: Athlete, proposal_id: uuid.UUID) -> AiProposal:
    proposal = await db.get(AiProposal, proposal_id)
    if proposal is None or proposal.athlete_id != athlete.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return proposal


@router.get("/proposals/{proposal_id}", response_model=ProposalRead)
async def proposal(
    proposal_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalRead:
    return await proposal_service.read_proposal(db, athlete, await _own_proposal(db, athlete, proposal_id), current_user)


@router.post("/proposals/{proposal_id}/accept", response_model=ProposalRead)
async def accept_proposal(
    proposal_id: uuid.UUID,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_ai_coach),
    current_user: User = Depends(get_current_user),
    pusher: PlanPusher = Depends(get_plan_pusher),
    db: AsyncSession = Depends(get_db),
) -> ProposalRead:
    found = await _own_proposal(db, athlete, proposal_id)
    try:
        await proposal_service.accept(db, athlete, found)
    except proposal_service.NotPending as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "proposal_not_pending") from exc
    except proposal_service.StaleProposal as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, {"code": "proposal_stale", "errors": exc.errors}) from exc
    await push_now(db, background, pusher, athlete.id)
    return await proposal_service.read_proposal(db, athlete, found, current_user)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalRead)
async def reject_proposal(
    proposal_id: uuid.UUID,
    athlete: Athlete = Depends(require_ai_coach),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalRead:
    found = await _own_proposal(db, athlete, proposal_id)
    try:
        await proposal_service.reject(db, found)
    except proposal_service.NotPending as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "proposal_not_pending") from exc
    return await proposal_service.read_proposal(db, athlete, found, current_user)


# --- reports ---------------------------------------------------------------------------------


@router.get("/reports", response_model=list[ReportRead])
async def reports(
    limit: int = Query(default=20, ge=1, le=100),
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[ReportRead]:
    rows = await db.scalars(
        select(AiReport).where(AiReport.athlete_id == athlete.id).order_by(AiReport.created_at.desc()).limit(limit)
    )
    return [report_read(r) for r in rows]


@router.post("/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_report(
    request: Request,
    athlete: Athlete = Depends(require_ai_coach),
    client: LlmClientPort = Depends(get_llm_client),
    db: AsyncSession = Depends(get_db),
) -> ReportRead:
    """On demand: the last 7 days, today included."""
    today = await today_of(db, athlete)
    try:
        report = await generate_report(
            db, client, athlete, kind=ReportKind.ON_DEMAND, start=today - timedelta(days=6), end=today
        )
    except (CapReached, LlmError) as exc:
        raise _model_error(exc) from exc
    return report_read(report)


# --- admin ------------------------------------------------------------------------------------


async def _admin_rows(db: AsyncSession, athletes: list[tuple[Athlete, str]]) -> list[AdminAiRow]:
    ids = [a.id for a, _ in athletes]
    access = {r.athlete_id: r for r in await db.scalars(select(AiCoachAccess).where(AiCoachAccess.athlete_id.in_(ids)))}
    usage = {
        athlete_id: (int(prompt or 0), int(completion or 0))
        for athlete_id, prompt, completion in (
            await db.execute(
                select(AiUsage.athlete_id, func.sum(AiUsage.prompt_tokens), func.sum(AiUsage.completion_tokens))
                .where(AiUsage.athlete_id.in_(ids), AiUsage.created_at >= month_start())
                .group_by(AiUsage.athlete_id)
            )
        ).all()
    }
    rows = []
    for athlete, email in athletes:
        row = access.get(athlete.id)
        prompt, completion = usage.get(athlete.id, (0, 0))
        rows.append(
            AdminAiRow(
                athlete_id=athlete.id,
                display_name=athlete.display_name,
                email=email,
                enabled=bool(row and row.enabled),
                consented=bool(row and row.consent_at),
                approved_at=row.approved_at if row else None,
                monthly_token_cap=row.monthly_token_cap if row else None,
                month_tokens=int(prompt + completion),
                month_cost_usd=cost_usd(int(prompt), int(completion)),
            )
        )
    return rows


@admin_router.get("", response_model=AdminAiOverview)
async def admin_overview(q: str | None = Query(default=None, max_length=100), db: AsyncSession = Depends(get_db)):
    """The athletes with AI access (ever enabled), plus those matching `q`
    (email or name) to enable someone new."""
    query = select(Athlete, User.email).join(User, User.id == Athlete.user_id)
    if q and q.strip():
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.email).like(pattern), func.lower(Athlete.display_name).like(pattern)))
    else:
        query = query.where(Athlete.id.in_(select(AiCoachAccess.athlete_id)))
    athletes = [(a, e) for a, e in (await db.execute(query.order_by(Athlete.display_name).limit(50))).all()]
    rows = await _admin_rows(db, athletes)
    totals = (
        await db.execute(
            select(func.sum(AiUsage.prompt_tokens), func.sum(AiUsage.completion_tokens)).where(
                AiUsage.created_at >= month_start()
            )
        )
    ).one()
    prompt, completion = int(totals[0] or 0), int(totals[1] or 0)
    return AdminAiOverview(
        available=ai_coach_available(),
        model=get_settings().mistral_model,
        default_monthly_tokens=get_settings().ai_coach_default_monthly_tokens,
        rows=rows,
        month_tokens=prompt + completion,
        month_cost_usd=cost_usd(prompt, completion),
    )


@admin_router.put("/{athlete_id}", response_model=AdminAiRow)
async def admin_update(
    athlete_id: uuid.UUID,
    payload: AdminAiUpdate,
    admin: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAiRow:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Athlete not found")
    user = await db.get(User, athlete.user_id) if athlete.user_id else None
    if user is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only athletes with their own login can use the AI coach")
    row = await access_row(db, athlete.id)
    if row is None:
        row = AiCoachAccess(athlete_id=athlete.id, enabled=False)
        db.add(row)
    if payload.enabled is not None and payload.enabled != row.enabled:
        row.enabled = payload.enabled
        if payload.enabled:
            row.approved_by_user_id = admin.id
            row.approved_at = utcnow()
    if payload.monthly_token_cap is not None:
        row.monthly_token_cap = payload.monthly_token_cap or None
    await db.commit()
    return (await _admin_rows(db, [(athlete, user.email)]))[0]
