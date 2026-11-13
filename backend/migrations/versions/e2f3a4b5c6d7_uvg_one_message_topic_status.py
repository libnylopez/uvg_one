"""uvg one: tema de la conversación y tipo de respuesta en cada mensaje

Revision ID: e2f3a4b5c6d7
Revises: d1a2b3c4e5f6
Create Date: 2026-11-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1a2b3c4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('topic_query', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('status', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'status')
    op.drop_column('messages', 'topic_query')
