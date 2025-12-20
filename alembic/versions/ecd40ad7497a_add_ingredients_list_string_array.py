"""Add ingredients_list string array

Revision ID: ecd40ad7497a
Revises: 3cd8dc5eb8e0
Create Date: 2025-12-17 09:51:11.892646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ecd40ad7497a'
down_revision: Union[str, Sequence[str], None] = '3cd8dc5eb8e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recipes', sa.Column('ingredients_list', postgresql.ARRAY(sa.String), nullable=True))
    op.execute("""
               UPDATE recipes 
               SET ingredients_list = subquery.names
               FROM (
                   SELECT ria.recipe_id, array_agg(i.name) as names
                   FROM recipe_ingredient_association ria
                   JOIN ingredients i ON ria.ingredient_id = i.id
                   GROUP BY ria.recipe_id
                   ) AS subquery
                WHERE recipes.id = subquery.recipe_id;
            """)
    op.execute("UPDATE recipes SET ingredients_list = '{}' WHERE ingredients_list IS NULL;")

    op.alter_column('recipes', 'ingredients_list', nullable=False, server_default='{}')
    
    op.create_index('ix_recipes_ingredients_list', 'recipes', ['ingredients_list'], postgresql_using='gin')

def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_recipes_ingredients_list")
    op.drop_column('recipes', 'ingredients_list')