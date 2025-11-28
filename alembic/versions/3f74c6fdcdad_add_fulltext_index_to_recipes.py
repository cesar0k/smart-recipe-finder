"""Add FULLTEXT index to recipes

Revision ID: 3f74c6fdcdad
Revises: 3cd8dc5eb8e0
Create Date: 2025-11-15 17:27:05.751243

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f74c6fdcdad'
down_revision: Union[str, Sequence[str], None] = '3cd8dc5eb8e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE recipes ADD FULLTEXT INDEX ft_index (title, instructions)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ft_index', table_name='recipes', mysql_drop_ft=True)
