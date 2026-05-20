"""risk analysis results

Revision ID: 0003_risk_analysis_results
Revises: 0002_document_extraction_evidence
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_risk_analysis_results"
down_revision = "0002_document_extraction_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if {"risk_analyses", "risk_analysis_results"} & set(inspector.get_table_names()):
        return
    op.create_table(
        "risk_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False, server_default="mradi-risk-engine-v1"),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "level",
            sa.Enum("low", "medium", "high", "critical", name="riskband", native_enum=False),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "risk_analyses" in set(inspector.get_table_names()):
        op.drop_table("risk_analyses")
    elif "risk_analysis_results" in set(inspector.get_table_names()):
        op.drop_table("risk_analysis_results")
