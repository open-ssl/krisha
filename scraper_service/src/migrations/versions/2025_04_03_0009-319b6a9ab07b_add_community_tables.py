"""add community tables

Revision ID: 319b6a9ab07b
Revises: c3acd84aab4a
Create Date: 2025-04-03 00:09:01.852273

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "319b6a9ab07b"
down_revision: Union[str, None] = "c3acd84aab4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "community_full_apartment_filters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("community_id", sa.BigInteger(), nullable=False),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("rooms", sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column("min_price", sa.Float(), nullable=True),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("min_square", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_community_full_apartment_filters_community_id"),
        "community_full_apartment_filters",
        ["community_id"],
        unique=False,
    )
    op.create_table(
        "community_sharing_filters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("community_id", sa.BigInteger(), nullable=False),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("roommate_preference", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("rooms", sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column("min_price", sa.Float(), nullable=True),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("min_square", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_community_sharing_filters_community_id"),
        "community_sharing_filters",
        ["community_id"],
        unique=False,
    )
    op.create_table(
        "community_seen_apartments",
        sa.Column("community_id", sa.BigInteger(), nullable=False),
        sa.Column("apartment_id", sa.Integer(), nullable=False),
        sa.Column("apartment_type", sa.String(), nullable=True),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["apartment_id"], ["apartments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("apartment_id"),
    )
    op.create_index(
        op.f("ix_community_seen_apartments_apartment_id"),
        "community_seen_apartments",
        ["apartment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_seen_apartments_community_id"),
        "community_seen_apartments",
        ["community_id"],
        unique=False,
    )
    op.create_table(
        "community_seen_telegram_apartments",
        sa.Column("community_id", sa.BigInteger(), nullable=False),
        sa.Column("apartment_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["apartment_id"], ["telegram_apartments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("community_id", "apartment_id"),
    )
    op.create_index(
        op.f("ix_community_seen_telegram_apartments_apartment_id"),
        "community_seen_telegram_apartments",
        ["apartment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_seen_telegram_apartments_community_id"),
        "community_seen_telegram_apartments",
        ["community_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_community_seen_telegram_apartments_community_id"),
        table_name="community_seen_telegram_apartments",
    )
    op.drop_index(
        op.f("ix_community_seen_telegram_apartments_apartment_id"),
        table_name="community_seen_telegram_apartments",
    )
    op.drop_table("community_seen_telegram_apartments")
    op.drop_index(
        op.f("ix_community_seen_apartments_community_id"),
        table_name="community_seen_apartments",
    )
    op.drop_index(
        op.f("ix_community_seen_apartments_apartment_id"),
        table_name="community_seen_apartments",
    )
    op.drop_table("community_seen_apartments")
    op.drop_index(
        op.f("ix_community_sharing_filters_community_id"),
        table_name="community_sharing_filters",
    )
    op.drop_table("community_sharing_filters")
    op.drop_index(
        op.f("ix_community_full_apartment_filters_community_id"),
        table_name="community_full_apartment_filters",
    )
    op.drop_table("community_full_apartment_filters")
    # ### end Alembic commands ###
