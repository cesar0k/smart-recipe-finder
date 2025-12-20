"""Migrate ingredients from Array to JSONB

Revision ID: b3631ada3c4f
Revises: ecd40ad7497a
Create Date: 2025-12-18 12:31:08.760252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3631ada3c4f'
down_revision: Union[str, Sequence[str], None] = 'ecd40ad7497a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recipes', sa.Column('ingredients', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("""
               UPDATE recipes
               SET ingredients = subquery.json_data
               FROM (
                   SELECT
                   id,
                   (
                       SELECT jsonb_agg(jsonb_build_object('name', elem))
                       FROM unnest(ingredients_list) as elem
                   ) as json_data
                   FROM recipes
               ) as subquery
               WHERE recipes.id = subquery.id;
               """)
    op.execute("UPDATE recipes set ingredients = '[]'::jsonb WHERE ingredients IS NULL")
    op.alter_column('recipes', 'ingredients', nullable=False, server_default='[]')
    
    op.create_index('ix_recipes_ingredients_jsonb', 'recipes', ['ingredients'], postgresql_using='gin')

    op.drop_column('recipes', 'ingredients_list')

def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('recipes', sa.Column('ingredients_list', postgresql.ARRAY(sa.String()), nullable=False))
    
    op.execute("""
               UPDATE recipes
               SET ingredients_list = subquery.arr_data
               FROM (
                   SELECT
                   id,
                   (
                       SELECT array_agg(elem->>'name')
                       FROM jsonb_array_element(ingredients) as elem
                   ) as arr_data
                   FROM recipes
               ) as subquery
               WHERE recipes.id = subquery.id
               """)
    op.drop_index('ix_recipes_ingredients_jsonb', table_name='recipes')
    op.drop_column('recipes', 'ingredients')