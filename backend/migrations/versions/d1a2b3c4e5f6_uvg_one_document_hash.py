"""uvg one: huella SHA-256 de cada documento de documentos_uvg/

Revision ID: d1a2b3c4e5f6
Revises: c4e8a1f0b2d7
Create Date: 2026-10-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f0b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('content_hash', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'content_hash')
