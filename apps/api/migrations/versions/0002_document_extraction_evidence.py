"""document extraction evidence and corrections

Revision ID: 0002_document_extraction_evidence
Revises: 0001_initial_schema
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_document_extraction_evidence"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    extracted_field_columns = {column["name"] for column in inspector.get_columns("extracted_fields")}
    tables = set(inspector.get_table_names())
    if "detected_document_type" not in document_columns:
        op.add_column("documents", sa.Column("detected_document_type", sa.String(length=120), nullable=False, server_default=""))
    if "document_type_confidence" not in document_columns:
        op.add_column("documents", sa.Column("document_type_confidence", sa.Float(), nullable=True))
    if "extraction_warnings" not in document_columns:
        op.add_column("documents", sa.Column("extraction_warnings", sa.JSON(), nullable=False, server_default="[]"))
    if "page_number" not in extracted_field_columns:
        op.add_column("extracted_fields", sa.Column("page_number", sa.Integer(), nullable=True))
    if "bounding_box" not in extracted_field_columns:
        op.add_column("extracted_fields", sa.Column("bounding_box", sa.JSON(), nullable=True))
    if "raw_text_snippet" not in extracted_field_columns and "text_snippet" not in extracted_field_columns:
        op.add_column("extracted_fields", sa.Column("raw_text_snippet", sa.Text(), nullable=False, server_default=""))
    if "extraction_metadata" not in extracted_field_columns:
        op.add_column("extracted_fields", sa.Column("extraction_metadata", sa.JSON(), nullable=False, server_default="{}"))
    if "user_field_corrections" not in tables and "field_corrections" not in tables:
        op.create_table(
            "user_field_corrections",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_document_id", sa.String(length=36), nullable=False),
            sa.Column("extracted_field_id", sa.String(length=36), nullable=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("field_name", sa.String(length=120), nullable=False),
            sa.Column("ai_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("corrected_value", sa.Text(), nullable=False),
            sa.Column("normalized_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"]),
            sa.ForeignKeyConstraint(["extracted_field_id"], ["extracted_fields.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "user_field_corrections" in tables:
        op.drop_table("user_field_corrections")
    elif "field_corrections" in tables:
        op.drop_table("field_corrections")
    op.drop_column("extracted_fields", "extraction_metadata")
    inspector = sa.inspect(bind)
    extracted_field_columns = {column["name"] for column in inspector.get_columns("extracted_fields")}
    if "raw_text_snippet" in extracted_field_columns:
        op.drop_column("extracted_fields", "raw_text_snippet")
    elif "text_snippet" in extracted_field_columns:
        op.drop_column("extracted_fields", "text_snippet")
    op.drop_column("extracted_fields", "bounding_box")
    op.drop_column("extracted_fields", "page_number")
    op.drop_column("documents", "extraction_warnings")
    op.drop_column("documents", "document_type_confidence")
    op.drop_column("documents", "detected_document_type")
