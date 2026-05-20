"""gazette search results

Revision ID: 0004_gazette_search_results
Revises: 0003_risk_analysis_results
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_gazette_search_results"
down_revision = "0003_risk_analysis_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "gazette_searches" not in tables:
        op.create_table(
            "gazette_searches",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("case_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("query_terms", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("county", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("parcel_number", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("title_number", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=60), nullable=False, server_default="completed"),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("searched_at", sa.DateTime(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if {"gazette_results", "gazette_search_results"} & tables:
        return
    op.create_table(
        "gazette_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("gazette_search_id", sa.String(length=36), nullable=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("notice_title", sa.String(length=500), nullable=False),
        sa.Column("publication_date", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("matched_keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["gazette_search_id"], ["gazette_searches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "gazette_results" in tables:
        op.drop_table("gazette_results")
    elif "gazette_search_results" in tables:
        op.drop_table("gazette_search_results")
    if "gazette_searches" in tables:
        op.drop_table("gazette_searches")
