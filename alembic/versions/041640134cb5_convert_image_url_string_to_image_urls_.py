"""Convert image_url string to image_urls array

Revision ID: 041640134cb5
Revises: f0dbe514fbb4
Create Date: 2025-12-31 09:01:11.845913

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "041640134cb5"
down_revision: Union[str, Sequence[str], None] = "f0dbe514fbb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("recipes", "image_url", new_column_name="image_urls")

    op.execute("""
        ALTER TABLE recipes
        ALTER COLUMN image_urls TYPE VARCHAR[]
        USING CASE
            WHEN image_urls IS NULL OR image_urls = '' THEN '{}'::VARCHAR[]
            ELSE ARRAY[image_urls]::VARCHAR[]
        END
    """)

    op.alter_column("recipes", "image_urls", nullable=False, server_default="{}")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("recipes", "image_urls", nullable=True)

    op.execute("""
        ALTER TABLE recipes
        ALTER COLUMN image_urls TYPE VARCHAR
        USING COALESCE(image_urls[1], '')
    """)

    op.alter_column("recipes", "image_urls", new_column_name="image_url")
