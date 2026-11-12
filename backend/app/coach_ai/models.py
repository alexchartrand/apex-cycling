"""The AI coach's tables.

`AiCoachAccess` is the gate (a platform admin enables it, the athlete
consents, a monthly token cap bounds the cost); `AiCoachProfile` is what the
intake interview learnt plus the accepted program outline; conversations
keep every message the model saw (tool calls included) so a chat can go on;
an `AiProposal` is a set of calendar changes waiting for the athlete's
Accept — the AI never writes the calendar itself; `AiReport` is a weekly or
on-demand training report; `AiUsage` is one model call, for the cap and the
admin's bill.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, false, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationKind(str, enum.Enum):
    CHAT = "chat"
    INTAKE = "intake"  # building a plan: the interview, then the proposal
    REPORT = "report"
    REPLAN = "replan"


class ProposalKind(str, enum.Enum):
    PLAN = "plan"  # a new program
    ADJUSTMENT = "adjustment"  # asked for in chat, or suggested by a report
    REPLAN = "replan"  # after missed sessions or a load drift


class ProposalStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class ReportKind(str, enum.Enum):
    WEEKLY = "weekly"
    ON_DEMAND = "on_demand"


class AiCoachAccess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_coach_access"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Null once the approving admin's account is gone.
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The athlete agreed to their data being sent to the model provider.
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Null = the server default (`ai_coach_default_monthly_tokens`).
    monthly_token_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Weekly report: ISO weekday 1 = Monday … 7 = Sunday, local hour.
    report_weekday: Mapped[int] = mapped_column(Integer, default=7, server_default=text("7"))
    report_hour: Mapped[int] = mapped_column(Integer, default=19, server_default=text("19"))
    weekly_reports: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    last_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_replan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiCoachProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """`answers` holds the intake (`schemas.CoachProfile`); `program` the
    accepted plan's goal and block outline, which later reports refine."""

    __tablename__ = "ai_coach_profiles"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), unique=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    program: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_athlete_updated", "athlete_id", "updated_at"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"))
    kind: Mapped[str] = mapped_column(String(16), default=ConversationKind.CHAT.value)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One message as the model API knows it: role system/user/assistant/tool,
    the assistant's `tool_calls`, a tool result's `tool_call_id` and `name`.
    `proposal_id` ties an assistant message to the proposal it made (the chat
    shows it as a card). `hidden` messages are sent to the model but not
    shown (tool traffic, the kick-off instruction of a report)."""

    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Position inside the conversation (created_at can tie within one turn).
    seq: Mapped[int] = mapped_column(Integer, default=0)


class AiProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """`payload` is `schemas.ProposalPayload` (ops + optional program outline),
    validated when made and again on Accept."""

    __tablename__ = "ai_proposals"
    __table_args__ = (Index("ix_ai_proposals_athlete_status", "athlete_id", "status"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_conversations.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=ProposalStatus.PENDING.value)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_reports"
    __table_args__ = (Index("ix_ai_reports_athlete_period", "athlete_id", "period_end"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_conversations.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    # The numbers the report was written from (shown next to it).
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class AiUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_athlete_created", "athlete_id", "created_at"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"))
    model: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(16))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
