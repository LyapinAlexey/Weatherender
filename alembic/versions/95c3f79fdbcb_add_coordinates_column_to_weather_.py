"""add coordinates column to weather_requests

Revision ID: 95c3f79fdbcb
Revises: 72df5a15cf2f
Create Date: 2026-08-26 15:21:54.219690

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "95c3f79fdbcb"
down_revision: Union[str, None] = "72df5a15cf2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather_requests",
        sa.Column("coordinates", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weather_requests", "coordinates")
