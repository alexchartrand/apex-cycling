"""notifications

The bell and the push/email outbox (`notifications`), per-user channel
preferences, and the browsers subscribed to Web Push.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018'
down_revision: Union[str, None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notifications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('dedupe_key', sa.String(length=255), nullable=True),
    sa.Column('in_app', sa.Boolean(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('want_push', sa.Boolean(), nullable=False),
    sa.Column('want_email', sa.Boolean(), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_notification_user_dedupe')
    )
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_notifications_delivered_at', 'notifications', ['delivered_at'], unique=False)

    op.create_table('notification_preferences',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('prefs', sa.JSON(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )

    op.create_table('push_subscriptions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('endpoint', sa.String(length=2048), nullable=False),
    sa.Column('p256dh', sa.String(length=255), nullable=False),
    sa.Column('auth', sa.String(length=255), nullable=False),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    op.create_index(op.f('ix_push_subscriptions_user_id'), 'push_subscriptions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_push_subscriptions_user_id'), table_name='push_subscriptions')
    op.drop_table('push_subscriptions')
    op.drop_table('notification_preferences')
    op.drop_index('ix_notifications_delivered_at', table_name='notifications')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
