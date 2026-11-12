"""ai coach

The AI coach (app/coach_ai): per-athlete access and consent, the intake
profile, conversations and their messages, calendar proposals, reports and
token usage; plans and workouts remember being written by it.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0025'
down_revision: Union[str, None] = '0024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_coach_access',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('approved_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('monthly_token_cap', sa.Integer(), nullable=True),
        sa.Column('report_weekday', sa.Integer(), server_default=sa.text('7'), nullable=False),
        sa.Column('report_hour', sa.Integer(), server_default=sa.text('19'), nullable=False),
        sa.Column('weekly_reports', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('last_report_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_replan_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_id'),
    )
    op.create_table(
        'ai_coach_profiles',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('program', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_id'),
    )
    op.create_table(
        'ai_conversations',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_conversations_athlete_updated', 'ai_conversations', ['athlete_id', 'updated_at'])
    op.create_table(
        'ai_messages',
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('tool_call_id', sa.String(length=64), nullable=True),
        sa.Column('name', sa.String(length=64), nullable=True),
        sa.Column('hidden', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=True),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_messages_conversation_created', 'ai_messages', ['conversation_id', 'created_at'])
    op.create_table(
        'ai_proposals',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_proposals_athlete_status', 'ai_proposals', ['athlete_id', 'status'])
    op.create_table(
        'ai_reports',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('stats', sa.JSON(), nullable=False),
        sa.Column('proposal_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_reports_athlete_period', 'ai_reports', ['athlete_id', 'period_end'])
    op.create_table(
        'ai_usage',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('purpose', sa.String(length=16), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_usage_athlete_created', 'ai_usage', ['athlete_id', 'created_at'])
    op.add_column('planned_sessions', sa.Column('created_by_ai', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('planned_sessions', sa.Column('ai_proposal_id', sa.Uuid(), nullable=True))
    op.add_column('workouts', sa.Column('created_by_ai', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('workouts', 'created_by_ai')
    op.drop_column('planned_sessions', 'ai_proposal_id')
    op.drop_column('planned_sessions', 'created_by_ai')
    op.drop_index('ix_ai_usage_athlete_created', table_name='ai_usage')
    op.drop_table('ai_usage')
    op.drop_index('ix_ai_reports_athlete_period', table_name='ai_reports')
    op.drop_table('ai_reports')
    op.drop_index('ix_ai_proposals_athlete_status', table_name='ai_proposals')
    op.drop_table('ai_proposals')
    op.drop_index('ix_ai_messages_conversation_created', table_name='ai_messages')
    op.drop_table('ai_messages')
    op.drop_index('ix_ai_conversations_athlete_updated', table_name='ai_conversations')
    op.drop_table('ai_conversations')
    op.drop_table('ai_coach_profiles')
    op.drop_table('ai_coach_access')
