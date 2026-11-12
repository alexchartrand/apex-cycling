"""Conversations with the AI coach: one turn = the athlete's message (or a
hidden kick-off for reports and replans), then model calls with tools until
it answers. Every message is stored, tool traffic hidden, so a conversation
can go on; the brief is rebuilt each turn, so it is always current.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.models import User
from app.coach_ai import context, prompts
from app.coach_ai.access import check_cap
from app.coach_ai.models import AiConversation, AiMessage, AiProposal, AiUsage, ConversationKind, ProposalKind
from app.coach_ai.ports import LlmClientPort, LlmReply
from app.coach_ai.proposals import read_proposal
from app.coach_ai.schemas import ConversationRead, ConversationSummary, MessageRead
from app.coach_ai.tools import ToolContext, run_tool, tools_for
from app.db.base import utcnow

MAX_TOOL_ROUNDS = 8
# Messages of earlier turns sent back to the model (the brief carries the rest).
HISTORY_MESSAGES = 40
OLD_TOOL_RESULT_CHARS = 1500
MAX_REPLY_TOKENS = 8000

_PROPOSAL_KIND = {
    ConversationKind.CHAT: ProposalKind.ADJUSTMENT,
    ConversationKind.INTAKE: ProposalKind.PLAN,
    ConversationKind.REPORT: ProposalKind.ADJUSTMENT,
    ConversationKind.REPLAN: ProposalKind.REPLAN,
}


def locale_of(user: User | None) -> str:
    return user.locale if user is not None and user.locale in prompts.LANGUAGES else "fr"


def _api_message(message: AiMessage, *, old: bool) -> dict:
    if message.role == "tool":
        content = message.content or ""
        if old and len(content) > OLD_TOOL_RESULT_CHARS:
            content = content[:OLD_TOOL_RESULT_CHARS] + "…(truncated)"
        return {"role": "tool", "tool_call_id": message.tool_call_id or "", "name": message.name or "", "content": content}
    out: dict = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        out["tool_calls"] = message.tool_calls
    return out


async def _history(db: AsyncSession, conversation: AiConversation) -> list[AiMessage]:
    return list(
        await db.scalars(
            select(AiMessage).where(AiMessage.conversation_id == conversation.id).order_by(AiMessage.seq, AiMessage.created_at)
        )
    )


def _trim(history: list[AiMessage], turn_start: int) -> list[dict]:
    """The last messages, starting at a user message (never in the middle of
    a tool exchange); results of earlier turns' tools shortened."""
    start = max(0, len(history) - HISTORY_MESSAGES)
    while start < len(history) and history[start].role != "user":
        start += 1
    start = min(start, turn_start)  # the current turn always goes whole
    return [_api_message(m, old=i < turn_start) for i, m in enumerate(history) if i >= start]


def _usage(athlete_id: uuid.UUID, reply: LlmReply, purpose: str) -> AiUsage:
    return AiUsage(
        athlete_id=athlete_id,
        model=reply.model[:64],
        purpose=purpose,
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
    )


async def start_conversation(db: AsyncSession, athlete: Athlete, kind: ConversationKind, title: str | None) -> AiConversation:
    conversation = AiConversation(athlete_id=athlete.id, kind=kind.value, title=title, updated_at=utcnow())
    db.add(conversation)
    await db.flush()
    return conversation


async def run_turn(
    db: AsyncSession,
    client: LlmClientPort,
    athlete: Athlete,
    conversation: AiConversation,
    *,
    user_text: str | None,
    hidden_user_text: bool = False,
    extra: dict | None = None,
) -> tuple[list[AiMessage], list[AiProposal]]:
    """Runs one turn and commits. Returns the new visible messages and the
    proposals made. Raises `CapReached`, `LlmError` (nothing is kept then)."""
    await check_cap(db, athlete.id)
    kind = ConversationKind(conversation.kind)
    user = await db.get(User, athlete.user_id) if athlete.user_id else None
    locale = locale_of(user)

    history = await _history(db, conversation)
    seq = (history[-1].seq + 1) if history else 0
    turn_start = len(history)
    new: list[AiMessage] = []

    def add(**fields) -> AiMessage:
        nonlocal seq
        message = AiMessage(conversation_id=conversation.id, seq=seq, **fields)
        seq += 1
        db.add(message)
        history.append(message)
        new.append(message)
        return message

    if user_text is not None:
        add(role="user", content=user_text, hidden=hidden_user_text)

    brief = await context.build_brief(db, athlete, locale=locale)
    system = prompts.system_prompt(kind.value, locale=locale, brief_json=context.to_json(brief), extra=extra)
    ctx = ToolContext(
        db=db,
        athlete=athlete,
        conversation_id=conversation.id,
        proposal_kind=_PROPOSAL_KIND[kind],
        allow_profile=kind in (ConversationKind.CHAT, ConversationKind.INTAKE),
    )
    tools = tools_for(ctx)
    spent: list[LlmReply] = []
    athlete_id = athlete.id  # still readable after a rollback expired the instance

    try:
        final: str | None = None
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            messages = [{"role": "system", "content": system}, *_trim(history, turn_start)]
            last_round = round_no == MAX_TOOL_ROUNDS
            reply = await client.chat(messages, tools=None if last_round else tools, max_tokens=MAX_REPLY_TOKENS)
            spent.append(reply)
            db.add(_usage(athlete_id, reply, kind.value))
            if reply.tool_calls and not last_round:
                add(
                    role="assistant",
                    content=reply.content or "",
                    hidden=True,
                    tool_calls=[
                        {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                        for call in reply.tool_calls
                    ],
                )
                for call in reply.tool_calls:
                    result = await run_tool(ctx, call.name, call.arguments)
                    add(role="tool", content=result, tool_call_id=call.id, name=call.name, hidden=True)
                continue
            final = (reply.content or "").strip()
            break
        # Every proposal made in the turn gets a card; the answer carries the last one.
        for proposal in ctx.proposals[:-1]:
            add(role="assistant", content="", proposal_id=proposal.id)
        add(role="assistant", content=final or "", proposal_id=ctx.proposals[-1].id if ctx.proposals else None)
        conversation.updated_at = utcnow()
        await db.commit()
    except BaseException:
        await db.rollback()
        if spent:  # the tokens were spent all the same
            db.add_all([_usage(athlete_id, reply, kind.value) for reply in spent])
            await db.commit()
        raise
    visible = [m for m in new if not m.hidden and m.role in ("user", "assistant")]
    return visible, ctx.proposals


# --- reads -----------------------------------------------------------------------------


async def message_reads(db: AsyncSession, athlete: Athlete, viewer: User, messages: list[AiMessage]) -> list[MessageRead]:
    proposal_ids = {m.proposal_id for m in messages if m.proposal_id}
    proposals = {
        p.id: p
        for p in await db.scalars(
            select(AiProposal).where(AiProposal.id.in_(proposal_ids), AiProposal.athlete_id == athlete.id)
        )
    }
    reads = []
    for message in messages:
        if message.hidden or message.role not in ("user", "assistant"):
            continue
        proposal = proposals.get(message.proposal_id) if message.proposal_id else None
        if not message.content and proposal is None:
            continue
        reads.append(
            MessageRead(
                id=message.id,
                role=message.role,
                content=message.content or "",
                created_at=message.created_at,
                proposal=await read_proposal(db, athlete, proposal, viewer) if proposal else None,
            )
        )
    return reads


def summary(conversation: AiConversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        kind=ConversationKind(conversation.kind),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def list_conversations(db: AsyncSession, athlete_id: uuid.UUID, *, limit: int = 50) -> list[ConversationSummary]:
    rows = await db.scalars(
        select(AiConversation)
        .where(AiConversation.athlete_id == athlete_id)
        .order_by(func.coalesce(AiConversation.updated_at, AiConversation.created_at).desc())
        .limit(limit)
    )
    return [summary(c) for c in rows]


async def get_conversation(db: AsyncSession, athlete_id: uuid.UUID, conversation_id: uuid.UUID) -> AiConversation | None:
    conversation = await db.get(AiConversation, conversation_id)
    return conversation if conversation is not None and conversation.athlete_id == athlete_id else None


async def conversation_read(db: AsyncSession, athlete: Athlete, viewer: User, conversation: AiConversation) -> ConversationRead:
    messages = await _history(db, conversation)
    return ConversationRead(
        **summary(conversation).model_dump(), messages=await message_reads(db, athlete, viewer, messages)
    )


def title_from(text: str | None, fallback: str | None = None) -> str | None:
    if not text:
        return fallback
    text = " ".join(text.split())
    return text if len(text) <= 80 else text[:79] + "…"
