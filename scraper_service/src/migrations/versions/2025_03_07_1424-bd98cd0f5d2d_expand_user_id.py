"""expand user id

Revision ID: bd98cd0f5d2d
Revises: d3badc7774c7
Create Date: 2025-03-07 14:24:33.725981

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bd98cd0f5d2d"
down_revision: Union[str, None] = "d3badc7774c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "full_apartment_filters",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "room_sharing_filters",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_filters",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_seen_apartments",
        "user_id",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "user_seen_apartments",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
    op.alter_column(
        "user_filters",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
    op.alter_column(
        "room_sharing_filters",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
    op.alter_column(
        "full_apartment_filters",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
    # ### end Alembic commands ###
