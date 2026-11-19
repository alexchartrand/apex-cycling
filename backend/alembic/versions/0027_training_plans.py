"""training plans

`training_plans` (one sport, its own goal / dates / weekly hours / phases /
week outline; app/training_plans) and `planned_sessions.training_plan_id`.
The AI coach's single program (`ai_coach_profiles.program`) becomes a plan
of its own, taking the athlete's AI sessions from its start on, and the
plan-level answers (goal, goal_date, hours_per_week) leave the intake.
`ai_conversations.training_plan_id` ties an intake to the plan it builds.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-18

"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027'
down_revision: Union[str, None] = '0026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLAN_FIELDS = ('goal', 'goal_date', 'hours_per_week')


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def upgrade() -> None:
    op.create_table(
        'training_plans',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('sport', sa.String(length=32), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('goal_text', sa.Text(), nullable=True),
        sa.Column('goal_date', sa.Date(), nullable=True),
        sa.Column('goal_id', sa.Uuid(), nullable=True),
        sa.Column('competition_id', sa.Uuid(), nullable=True),
        sa.Column('hours_per_week', sa.Float(), nullable=True),
        sa.Column('phases', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('weeks', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_by_ai', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('ai_proposal_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id']),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_training_plans_athlete_id', 'training_plans', ['athlete_id'], unique=False)
    op.add_column('planned_sessions', sa.Column('training_plan_id', sa.Uuid(), nullable=True))
    op.create_index('ix_planned_sessions_training_plan_id', 'planned_sessions', ['training_plan_id'], unique=False)
    op.create_foreign_key(
        'planned_sessions_training_plan_id_fkey', 'planned_sessions', 'training_plans', ['training_plan_id'], ['id']
    )
    op.add_column('ai_conversations', sa.Column('training_plan_id', sa.Uuid(), nullable=True))

    bind = op.get_bind()
    profiles = bind.execute(sa.text('SELECT id, athlete_id, answers, program FROM ai_coach_profiles')).all()
    for profile_id, athlete_id, answers, program in profiles:
        answers = _json(answers) or {}
        program = _json(program)
        if program:
            weeks = [w for w in program.get('outline') or [] if _date(w.get('week_start'))]
            accepted = _date(program.get('accepted_at')) or date.today()
            goal_date = _date(answers.get('goal_date'))
            starts = [_date(w['week_start']) for w in weeks]
            start = min([accepted, *starts])
            end = max([d for d in [goal_date, *(s + timedelta(days=6) for s in starts)] if d] or [start + timedelta(days=27)])
            if goal_date is not None and not (start <= goal_date <= end):
                goal_date = None
            plan_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    'INSERT INTO training_plans (id, created_at, athlete_id, name, sport, start_date, end_date, '
                    'goal_text, goal_date, hours_per_week, phases, weeks, created_by_ai) VALUES (:id, :now, :athlete, '
                    ':name, :sport, :start, :end, :goal, :goal_date, :hours, :phases, :weeks, :ai)'
                ).bindparams(
                    sa.bindparam('phases', type_=sa.JSON()), sa.bindparam('weeks', type_=sa.JSON())
                ),
                {
                    'id': plan_id,
                    'now': datetime.now(timezone.utc),
                    'athlete': athlete_id,
                    'name': (program.get('goal') or answers.get('goal') or 'Programme')[:120],
                    'sport': 'track_cycling' if answers.get('track_days') else 'cycling',
                    'start': start,
                    'end': end,
                    'goal': program.get('goal') or answers.get('goal'),
                    'goal_date': goal_date,
                    'hours': answers.get('hours_per_week'),
                    'phases': [],
                    'weeks': weeks,
                    'ai': True,
                },
            )
            bind.execute(
                sa.text(
                    'UPDATE planned_sessions SET training_plan_id = :plan WHERE athlete_id = :athlete '
                    'AND created_by_ai = :ai AND planned_date >= :start'
                ),
                {'plan': plan_id, 'athlete': athlete_id, 'ai': True, 'start': start},
            )
        if any(key in answers for key in PLAN_FIELDS):
            kept = {k: v for k, v in answers.items() if k not in PLAN_FIELDS}
            bind.execute(
                sa.text('UPDATE ai_coach_profiles SET answers = :answers WHERE id = :id').bindparams(
                    sa.bindparam('answers', type_=sa.JSON())
                ),
                {'answers': kept, 'id': profile_id},
            )
    op.drop_column('ai_coach_profiles', 'program')


def downgrade() -> None:
    op.add_column('ai_coach_profiles', sa.Column('program', sa.JSON(), nullable=True))
    bind = op.get_bind()
    # Each athlete's newest AI plan goes back to being their program.
    rows = bind.execute(
        sa.text(
            'SELECT athlete_id, goal_text, created_at, weeks FROM training_plans '
            'WHERE created_by_ai = :ai ORDER BY created_at'
        ),
        {'ai': True},
    ).all()
    newest = {athlete_id: (goal, created, weeks) for athlete_id, goal, created, weeks in rows}
    for athlete_id, (goal, created, weeks) in newest.items():
        program = {'goal': goal, 'accepted_at': str(created), 'outline': _json(weeks) or []}
        bind.execute(
            sa.text('UPDATE ai_coach_profiles SET program = :program WHERE athlete_id = :athlete').bindparams(
                sa.bindparam('program', type_=sa.JSON())
            ),
            {'program': program, 'athlete': athlete_id},
        )
    op.drop_column('ai_conversations', 'training_plan_id')
    op.drop_constraint('planned_sessions_training_plan_id_fkey', 'planned_sessions', type_='foreignkey')
    op.drop_index('ix_planned_sessions_training_plan_id', table_name='planned_sessions')
    op.drop_column('planned_sessions', 'training_plan_id')
    op.drop_index('ix_training_plans_athlete_id', table_name='training_plans')
    op.drop_table('training_plans')
