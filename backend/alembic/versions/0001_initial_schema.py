"""initial schema

Squashed baseline of the former 0001-0014 chain (pre-first-deploy). Generated
from the models; the DB-level server defaults the old chain set are kept.

Revision ID: 0001
Revises:
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clubs',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clubs_slug'), 'clubs', ['slug'], unique=True)
    op.create_table('tracks',
    sa.Column('sqorz_account_id', sa.String(length=255), nullable=False),
    sa.Column('external_track_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('track_type', sa.String(length=64), nullable=True),
    sa.Column('validation_method', sa.String(length=64), nullable=True),
    sa.Column('length_m', sa.Float(), nullable=True),
    sa.Column('indoor', sa.Boolean(), nullable=True),
    sa.Column('elevation_m', sa.Float(), nullable=True),
    sa.Column('default_temp_c', sa.Float(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sqorz_account_id', 'external_track_id', name='uq_track_account_external_id')
    )
    op.create_index(op.f('ix_tracks_external_track_id'), 'tracks', ['external_track_id'], unique=False)
    op.create_index(op.f('ix_tracks_sqorz_account_id'), 'tracks', ['sqorz_account_id'], unique=False)
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('is_platform_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('locale', sa.String(length=8), nullable=True),
    sa.Column('theme', sa.String(length=16), nullable=True),
    sa.Column('credentials_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('worker_heartbeats',
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_poll_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_poll_finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_poll_connections', sa.Integer(), nullable=True),
    sa.Column('last_poll_failures', sa.Integer(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('athletes',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('club_id', sa.Uuid(), nullable=True),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('birthdate', sa.Date(), nullable=True),
    sa.Column('sex', sa.String(length=32), nullable=True),
    sa.Column('height_cm', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_athletes_club_id'), 'athletes', ['club_id'], unique=False)
    op.create_index(op.f('ix_athletes_user_id'), 'athletes', ['user_id'], unique=True)
    op.create_table('club_invites',
    sa.Column('club_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('role', sa.Enum('athlete', 'coach', 'club_admin', name='club_role'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('max_uses', sa.Integer(), nullable=True),
    sa.Column('use_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_club_invites_club_id'), 'club_invites', ['club_id'], unique=False)
    op.create_table('club_memberships',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('club_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('athlete', 'coach', 'club_admin', name='club_role'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'club_id', name='uq_club_membership_user_club')
    )
    op.create_index(op.f('ix_club_memberships_club_id'), 'club_memberships', ['club_id'], unique=False)
    op.create_index(op.f('ix_club_memberships_user_id'), 'club_memberships', ['user_id'], unique=False)
    op.create_table('club_sqorz_accounts',
    sa.Column('club_id', sa.Uuid(), nullable=False),
    sa.Column('sqorz_account_id', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('club_id', 'sqorz_account_id', name='uq_club_sqorz_account')
    )
    op.create_index(op.f('ix_club_sqorz_accounts_club_id'), 'club_sqorz_accounts', ['club_id'], unique=False)
    op.create_index(op.f('ix_club_sqorz_accounts_sqorz_account_id'), 'club_sqorz_accounts', ['sqorz_account_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('track_loops',
    sa.Column('track_id', sa.Uuid(), nullable=False),
    sa.Column('external_loop_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('distance_m', sa.Float(), nullable=True),
    sa.Column('hidden', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('track_id', 'external_loop_id', name='uq_track_loop_external_id')
    )
    op.create_index(op.f('ix_track_loops_external_loop_id'), 'track_loops', ['external_loop_id'], unique=False)
    op.create_index(op.f('ix_track_loops_track_id'), 'track_loops', ['track_id'], unique=False)
    op.create_table('track_views',
    sa.Column('track_id', sa.Uuid(), nullable=False),
    sa.Column('external_track_view_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('circuit', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('hidden', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('track_id', 'external_track_view_id', name='uq_track_view_external_id')
    )
    op.create_index(op.f('ix_track_views_external_track_view_id'), 'track_views', ['external_track_view_id'], unique=False)
    op.create_index(op.f('ix_track_views_track_id'), 'track_views', ['track_id'], unique=False)
    op.create_table('athlete_metrics',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('weight_kg', sa.Float(), nullable=True),
    sa.Column('ftp_w', sa.Integer(), nullable=True),
    sa.Column('max_hr', sa.Integer(), nullable=True),
    sa.Column('resting_hr', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'effective_date', name='uq_athlete_metric_date')
    )
    op.create_index(op.f('ix_athlete_metrics_athlete_id'), 'athlete_metrics', ['athlete_id'], unique=False)
    op.create_table('coach_athletes',
    sa.Column('coach_user_id', sa.Uuid(), nullable=False),
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('initiated_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('pending_athlete_acceptance', 'pending_coach_acceptance', 'active', 'revoked', name='coach_athlete_status'), nullable=False),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['coach_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['initiated_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('coach_user_id', 'athlete_id', name='uq_coach_athlete')
    )
    op.create_index(op.f('ix_coach_athletes_athlete_id'), 'coach_athletes', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_coach_athletes_coach_user_id'), 'coach_athletes', ['coach_user_id'], unique=False)
    op.create_table('data_source_connections',
    sa.Column('provider', sa.Enum('sqorz', 'strava', 'garmin', name='data_source_provider'), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('athlete_id', sa.Uuid(), nullable=True),
    sa.Column('credentials', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('active', 'inactive', name='data_source_connection_status'), server_default='active', nullable=False),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sqorz_account_id', sa.String(length=255), nullable=True),
    sa.Column('sqorz_account_name', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'external_id', name='uq_connection_provider_external_id')
    )
    op.create_index(op.f('ix_data_source_connections_athlete_id'), 'data_source_connections', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_data_source_connections_external_id'), 'data_source_connections', ['external_id'], unique=False)
    op.create_table('manual_results',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('track_id', sa.Uuid(), nullable=True),
    sa.Column('venue', sa.String(length=255), nullable=True),
    sa.Column('event_key', sa.String(length=16), nullable=False),
    sa.Column('start_type', sa.String(length=16), nullable=False),
    sa.Column('time_ms', sa.Integer(), nullable=False),
    sa.Column('achieved_on', sa.Date(), nullable=False),
    sa.Column('is_competition', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_results_athlete_id'), 'manual_results', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_manual_results_track_id'), 'manual_results', ['track_id'], unique=False)
    op.create_table('track_view_loops',
    sa.Column('track_view_id', sa.Uuid(), nullable=False),
    sa.Column('track_loop_id', sa.Uuid(), nullable=False),
    sa.Column('sequence_index', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['track_loop_id'], ['track_loops.id'], ),
    sa.ForeignKeyConstraint(['track_view_id'], ['track_views.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('track_view_id', 'sequence_index', name='uq_track_view_loop_sequence')
    )
    op.create_index(op.f('ix_track_view_loops_track_loop_id'), 'track_view_loops', ['track_loop_id'], unique=False)
    op.create_index(op.f('ix_track_view_loops_track_view_id'), 'track_view_loops', ['track_view_id'], unique=False)
    op.create_table('training_events',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('sqorz_account_id', sa.String(length=255), nullable=False),
    sa.Column('external_event_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('sport_type', sa.String(length=64), nullable=True),
    sa.Column('start_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('end_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('title_override', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('rpe', sa.Integer(), nullable=True),
    sa.Column('tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'sqorz_account_id', 'external_event_id', name='uq_event_athlete_account_external_id')
    )
    op.create_index(op.f('ix_training_events_athlete_id'), 'training_events', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_training_events_event_date'), 'training_events', ['event_date'], unique=False)
    op.create_index(op.f('ix_training_events_external_event_id'), 'training_events', ['external_event_id'], unique=False)
    op.create_index(op.f('ix_training_events_sqorz_account_id'), 'training_events', ['sqorz_account_id'], unique=False)
    op.create_table('event_classes',
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('class_code', sa.String(length=64), nullable=False),
    sa.Column('class_name', sa.String(length=255), nullable=True),
    sa.Column('class_type', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('training_event_id', 'class_code', name='uq_event_class_code')
    )
    op.create_index(op.f('ix_event_classes_training_event_id'), 'event_classes', ['training_event_id'], unique=False)
    op.create_table('event_tracks',
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('track_id', sa.Uuid(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('gate', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('start_from', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('training_event_id', 'track_id', name='uq_event_track')
    )
    op.create_index(op.f('ix_event_tracks_track_id'), 'event_tracks', ['track_id'], unique=False)
    op.create_index(op.f('ix_event_tracks_training_event_id'), 'event_tracks', ['training_event_id'], unique=False)
    op.create_table('ingestion_runs',
    sa.Column('data_source_connection_id', sa.Uuid(), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('pending', 'success', 'failed', name='ingestion_run_status'), server_default='pending', nullable=False),
    sa.Column('http_status', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['data_source_connection_id'], ['data_source_connections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingestion_runs_data_source_connection_id'), 'ingestion_runs', ['data_source_connection_id'], unique=False)
    op.create_table('session_comment_reads',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'training_event_id', name='uq_session_comment_read')
    )
    op.create_index(op.f('ix_session_comment_reads_training_event_id'), 'session_comment_reads', ['training_event_id'], unique=False)
    op.create_index(op.f('ix_session_comment_reads_user_id'), 'session_comment_reads', ['user_id'], unique=False)
    op.create_table('session_comments',
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('author_user_id', sa.Uuid(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_comments_author_user_id'), 'session_comments', ['author_user_id'], unique=False)
    op.create_index(op.f('ix_session_comments_training_event_id'), 'session_comments', ['training_event_id'], unique=False)
    op.create_table('transponder_assignments',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('data_source_connection_id', sa.Uuid(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['data_source_connection_id'], ['data_source_connections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transponder_assignments_athlete_id'), 'transponder_assignments', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_transponder_assignments_data_source_connection_id'), 'transponder_assignments', ['data_source_connection_id'], unique=False)
    op.create_table('raw_snapshots',
    sa.Column('ingestion_run_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.Enum('sqorz', 'strava', 'garmin', name='data_source_provider'), nullable=False),
    sa.Column('external_ref', sa.String(length=255), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_raw_snapshots_content_hash'), 'raw_snapshots', ['content_hash'], unique=False)
    op.create_index(op.f('ix_raw_snapshots_external_ref'), 'raw_snapshots', ['external_ref'], unique=False)
    op.create_index(op.f('ix_raw_snapshots_ingestion_run_id'), 'raw_snapshots', ['ingestion_run_id'], unique=False)
    op.create_table('training_laps',
    sa.Column('event_track_id', sa.Uuid(), nullable=False),
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('transponder_code', sa.String(length=255), nullable=False),
    sa.Column('class_code', sa.String(length=64), nullable=True),
    sa.Column('external_lap_id', sa.String(length=255), nullable=False),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('from_start', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('start_number', sa.Integer(), nullable=True),
    sa.Column('excluded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=True),
    sa.Column('effort_label', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['event_track_id'], ['event_tracks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_track_id', 'external_lap_id', name='uq_training_lap_external_id')
    )
    op.create_index(op.f('ix_training_laps_athlete_id'), 'training_laps', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_training_laps_event_track_id'), 'training_laps', ['event_track_id'], unique=False)
    op.create_index(op.f('ix_training_laps_external_lap_id'), 'training_laps', ['external_lap_id'], unique=False)
    op.create_index(op.f('ix_training_laps_start_time'), 'training_laps', ['start_time'], unique=False)
    op.create_index(op.f('ix_training_laps_transponder_code'), 'training_laps', ['transponder_code'], unique=False)
    op.create_table('lap_segment_times',
    sa.Column('training_lap_id', sa.Uuid(), nullable=False),
    sa.Column('track_loop_id', sa.Uuid(), nullable=False),
    sa.Column('sequence_index', sa.Integer(), nullable=False),
    sa.Column('time_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['track_loop_id'], ['track_loops.id'], ),
    sa.ForeignKeyConstraint(['training_lap_id'], ['training_laps.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('training_lap_id', 'sequence_index', name='uq_lap_segment_sequence')
    )
    op.create_index(op.f('ix_lap_segment_times_track_loop_id'), 'lap_segment_times', ['track_loop_id'], unique=False)
    op.create_index(op.f('ix_lap_segment_times_training_lap_id'), 'lap_segment_times', ['training_lap_id'], unique=False)
    op.create_table('personal_records',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('track_id', sa.Uuid(), nullable=False),
    sa.Column('event_key', sa.String(length=16), nullable=False),
    sa.Column('start_type', sa.String(length=16), nullable=False),
    sa.Column('time_ms', sa.Integer(), nullable=False),
    sa.Column('achieved_on', sa.Date(), nullable=False),
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('training_lap_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.ForeignKeyConstraint(['training_lap_id'], ['training_laps.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'track_id', 'event_key', 'start_type', name='uq_personal_record_key')
    )
    op.create_index(op.f('ix_personal_records_athlete_id'), 'personal_records', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_personal_records_track_id'), 'personal_records', ['track_id'], unique=False)
    op.create_index(op.f('ix_personal_records_training_event_id'), 'personal_records', ['training_event_id'], unique=False)
    op.create_index(op.f('ix_personal_records_training_lap_id'), 'personal_records', ['training_lap_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_personal_records_training_lap_id'), table_name='personal_records')
    op.drop_index(op.f('ix_personal_records_training_event_id'), table_name='personal_records')
    op.drop_index(op.f('ix_personal_records_track_id'), table_name='personal_records')
    op.drop_index(op.f('ix_personal_records_athlete_id'), table_name='personal_records')
    op.drop_table('personal_records')
    op.drop_index(op.f('ix_lap_segment_times_training_lap_id'), table_name='lap_segment_times')
    op.drop_index(op.f('ix_lap_segment_times_track_loop_id'), table_name='lap_segment_times')
    op.drop_table('lap_segment_times')
    op.drop_index(op.f('ix_training_laps_transponder_code'), table_name='training_laps')
    op.drop_index(op.f('ix_training_laps_start_time'), table_name='training_laps')
    op.drop_index(op.f('ix_training_laps_external_lap_id'), table_name='training_laps')
    op.drop_index(op.f('ix_training_laps_event_track_id'), table_name='training_laps')
    op.drop_index(op.f('ix_training_laps_athlete_id'), table_name='training_laps')
    op.drop_table('training_laps')
    op.drop_index(op.f('ix_raw_snapshots_ingestion_run_id'), table_name='raw_snapshots')
    op.drop_index(op.f('ix_raw_snapshots_external_ref'), table_name='raw_snapshots')
    op.drop_index(op.f('ix_raw_snapshots_content_hash'), table_name='raw_snapshots')
    op.drop_table('raw_snapshots')
    op.drop_index(op.f('ix_transponder_assignments_data_source_connection_id'), table_name='transponder_assignments')
    op.drop_index(op.f('ix_transponder_assignments_athlete_id'), table_name='transponder_assignments')
    op.drop_table('transponder_assignments')
    op.drop_index(op.f('ix_session_comments_training_event_id'), table_name='session_comments')
    op.drop_index(op.f('ix_session_comments_author_user_id'), table_name='session_comments')
    op.drop_table('session_comments')
    op.drop_index(op.f('ix_session_comment_reads_user_id'), table_name='session_comment_reads')
    op.drop_index(op.f('ix_session_comment_reads_training_event_id'), table_name='session_comment_reads')
    op.drop_table('session_comment_reads')
    op.drop_index(op.f('ix_ingestion_runs_data_source_connection_id'), table_name='ingestion_runs')
    op.drop_table('ingestion_runs')
    op.drop_index(op.f('ix_event_tracks_training_event_id'), table_name='event_tracks')
    op.drop_index(op.f('ix_event_tracks_track_id'), table_name='event_tracks')
    op.drop_table('event_tracks')
    op.drop_index(op.f('ix_event_classes_training_event_id'), table_name='event_classes')
    op.drop_table('event_classes')
    op.drop_index(op.f('ix_training_events_sqorz_account_id'), table_name='training_events')
    op.drop_index(op.f('ix_training_events_external_event_id'), table_name='training_events')
    op.drop_index(op.f('ix_training_events_event_date'), table_name='training_events')
    op.drop_index(op.f('ix_training_events_athlete_id'), table_name='training_events')
    op.drop_table('training_events')
    op.drop_index(op.f('ix_track_view_loops_track_view_id'), table_name='track_view_loops')
    op.drop_index(op.f('ix_track_view_loops_track_loop_id'), table_name='track_view_loops')
    op.drop_table('track_view_loops')
    op.drop_index(op.f('ix_manual_results_track_id'), table_name='manual_results')
    op.drop_index(op.f('ix_manual_results_athlete_id'), table_name='manual_results')
    op.drop_table('manual_results')
    op.drop_index(op.f('ix_data_source_connections_external_id'), table_name='data_source_connections')
    op.drop_index(op.f('ix_data_source_connections_athlete_id'), table_name='data_source_connections')
    op.drop_table('data_source_connections')
    op.drop_index(op.f('ix_coach_athletes_coach_user_id'), table_name='coach_athletes')
    op.drop_index(op.f('ix_coach_athletes_athlete_id'), table_name='coach_athletes')
    op.drop_table('coach_athletes')
    op.drop_index(op.f('ix_athlete_metrics_athlete_id'), table_name='athlete_metrics')
    op.drop_table('athlete_metrics')
    op.drop_index(op.f('ix_track_views_track_id'), table_name='track_views')
    op.drop_index(op.f('ix_track_views_external_track_view_id'), table_name='track_views')
    op.drop_table('track_views')
    op.drop_index(op.f('ix_track_loops_track_id'), table_name='track_loops')
    op.drop_index(op.f('ix_track_loops_external_loop_id'), table_name='track_loops')
    op.drop_table('track_loops')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_club_sqorz_accounts_sqorz_account_id'), table_name='club_sqorz_accounts')
    op.drop_index(op.f('ix_club_sqorz_accounts_club_id'), table_name='club_sqorz_accounts')
    op.drop_table('club_sqorz_accounts')
    op.drop_index(op.f('ix_club_memberships_user_id'), table_name='club_memberships')
    op.drop_index(op.f('ix_club_memberships_club_id'), table_name='club_memberships')
    op.drop_table('club_memberships')
    op.drop_index(op.f('ix_club_invites_club_id'), table_name='club_invites')
    op.drop_table('club_invites')
    op.drop_index(op.f('ix_athletes_user_id'), table_name='athletes')
    op.drop_index(op.f('ix_athletes_club_id'), table_name='athletes')
    op.drop_table('athletes')
    op.drop_table('worker_heartbeats')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_tracks_sqorz_account_id'), table_name='tracks')
    op.drop_index(op.f('ix_tracks_external_track_id'), table_name='tracks')
    op.drop_table('tracks')
    op.drop_index(op.f('ix_clubs_slug'), table_name='clubs')
    op.drop_table('clubs')

    for enum_name in (
        "club_role",
        "coach_athlete_status",
        "data_source_connection_status",
        "data_source_provider",
        "ingestion_run_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
