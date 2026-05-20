"""align schema with Mradi wa Ardhi product data model

Revision ID: 0005_mradi_schema_alignment
Revises: 0004_gazette_search_results
Create Date: 2026-05-19

This migration makes the PostgreSQL schema use the product-facing table and
column names requested for Mradi wa Ardhi while preserving the Python model
attribute names already used by the API.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_mradi_schema_alignment"
down_revision = "0004_gazette_search_results"
branch_labels = None
depends_on = None


RISK_LEVEL = sa.Enum("low", "medium", "high", "critical", name="riskband", native_enum=False)


def upgrade() -> None:
    _rename_legacy_tables()
    _align_case_columns()
    _align_document_columns()
    _create_case_participants()
    _create_document_extractions()
    _align_extracted_field_columns()
    _align_user_field_corrections()
    _create_gazette_searches()
    _align_gazette_results()
    _align_risk_analyses()
    _align_risk_factors()
    _align_expert_reviews()
    _align_audit_logs()
    _align_payments_optional()
    _create_notifications()
    _create_api_keys_optional()
    _create_requested_indexes()


def downgrade() -> None:
    _drop_index_if_exists("api_keys_optional", "ix_api_keys_optional_created_at")
    _drop_index_if_exists("api_keys_optional", "ix_api_keys_optional_key_prefix")
    _drop_index_if_exists("api_keys_optional", "ix_api_keys_optional_user_id")
    _drop_index_if_exists("notifications", "ix_notifications_created_at")
    _drop_index_if_exists("notifications", "ix_notifications_case_id")
    _drop_index_if_exists("notifications", "ix_notifications_user_id")
    _drop_index_if_exists("case_participants", "ix_case_participants_created_at")
    _drop_index_if_exists("case_participants", "ix_case_participants_user_id")
    _drop_index_if_exists("case_participants", "ix_case_participants_case_id")
    _drop_index_if_exists("document_extractions", "ix_document_extractions_created_at")
    _drop_index_if_exists("document_extractions", "ix_document_extractions_document_id")
    _drop_index_if_exists("document_extractions", "ix_document_extractions_case_id")

    _drop_table_if_exists("api_keys_optional")
    _drop_table_if_exists("notifications")
    _drop_table_if_exists("case_participants")

    _drop_column_if_exists("risk_factors", "risk_analysis_id")
    _drop_column_if_exists("extracted_fields", "document_extraction_id")
    _drop_table_if_exists("document_extractions")
    _drop_column_if_exists("gazette_results", "gazette_search_id")
    _drop_table_if_exists("gazette_searches")

    _rename_column_if_exists("payments_optional", "metadata", "metadata_json")
    for column in ("paid_at", "currency", "amount", "provider_payment_id", "provider", "case_id", "organization_id"):
        _drop_column_if_exists("payments_optional", column)
    _rename_table_if_exists("payments_optional", "pricing_plan_selections")

    _rename_column_if_exists("audit_logs", "metadata", "metadata_json")
    _rename_column_if_exists("audit_logs", "entity_id", "target_id")
    _rename_column_if_exists("audit_logs", "entity_type", "target_type")
    _rename_column_if_exists("audit_logs", "actor_id", "actor_user_id")

    for column in ("metadata", "completed_at", "review_summary"):
        _drop_column_if_exists("expert_reviews", column)
    _rename_column_if_exists("expert_reviews", "user_id", "requested_by_user_id")
    _rename_table_if_exists("expert_reviews", "review_requests")

    _drop_column_if_exists("risk_analyses", "engine_version")
    _rename_column_if_exists("risk_analyses", "level", "band")
    _rename_column_if_exists("risk_analyses", "model_version", "version")
    _rename_table_if_exists("risk_analyses", "risk_analysis_results")

    _rename_column_if_exists("user_field_corrections", "metadata", "metadata_json")
    _rename_column_if_exists("user_field_corrections", "user_id", "corrected_by_user_id")
    _rename_column_if_exists("user_field_corrections", "source_document_id", "document_id")
    _rename_table_if_exists("user_field_corrections", "field_corrections")

    _rename_column_if_exists("extracted_fields", "raw_text_snippet", "text_snippet")
    _rename_column_if_exists("extracted_fields", "field_value", "value")
    _rename_column_if_exists("extracted_fields", "source_document_id", "document_id")

    for column in ("uploaded_at", "extraction_status", "file_url"):
        _drop_column_if_exists("documents", column)
    _rename_column_if_exists("documents", "quality_score", "image_quality_score")
    _rename_column_if_exists("documents", "upload_status", "status")
    _rename_column_if_exists("documents", "mime_type", "content_type")
    _rename_column_if_exists("documents", "storage_key", "storage_uri")
    _rename_column_if_exists("documents", "file_name", "filename")
    _rename_column_if_exists("documents", "document_type", "category")

    for column in ("risk_score", "risk_level", "transaction_value", "title_number", "location"):
        _drop_column_if_exists("cases", column)
    _rename_column_if_exists("cases", "parcel_number", "parcel_number_claimed")
    _rename_column_if_exists("cases", "county", "location_county")
    _rename_column_if_exists("cases", "user_id", "owner_user_id")

    _rename_table_if_exists("gazette_results", "gazette_search_results")


def _rename_legacy_tables() -> None:
    _rename_table_if_exists("field_corrections", "user_field_corrections")
    _rename_table_if_exists("risk_analysis_results", "risk_analyses")
    _rename_table_if_exists("gazette_search_results", "gazette_results")
    _rename_table_if_exists("review_requests", "expert_reviews")
    _rename_table_if_exists("pricing_plan_selections", "payments_optional")


def _align_case_columns() -> None:
    _rename_column_if_exists("cases", "owner_user_id", "user_id")
    _rename_column_if_exists("cases", "location_county", "county")
    _rename_column_if_exists("cases", "parcel_number_claimed", "parcel_number")
    _add_column_if_missing("cases", sa.Column("location", sa.String(length=255), nullable=False, server_default=""))
    _add_column_if_missing("cases", sa.Column("title_number", sa.String(length=255), nullable=False, server_default=""))
    _add_column_if_missing("cases", sa.Column("transaction_value", sa.Numeric(14, 2), nullable=True))
    _add_column_if_missing("cases", sa.Column("risk_level", RISK_LEVEL, nullable=True))
    _add_column_if_missing("cases", sa.Column("risk_score", sa.Integer(), nullable=True))


def _align_document_columns() -> None:
    _rename_column_if_exists("documents", "category", "document_type")
    _rename_column_if_exists("documents", "filename", "file_name")
    _rename_column_if_exists("documents", "storage_uri", "storage_key")
    _rename_column_if_exists("documents", "content_type", "mime_type")
    _rename_column_if_exists("documents", "status", "upload_status")
    _rename_column_if_exists("documents", "image_quality_score", "quality_score")
    _add_column_if_missing("documents", sa.Column("file_url", sa.String(length=1000), nullable=False, server_default=""))
    _add_column_if_missing("documents", sa.Column("extraction_status", sa.String(length=60), nullable=False, server_default="pending"))
    _add_column_if_missing("documents", sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))


def _create_case_participants() -> None:
    if _table_exists("case_participants"):
        return
    op.create_table(
        "case_participants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("id_number", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("kra_pin", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="People and organizations involved in a case.",
    )


def _create_document_extractions() -> None:
    if _table_exists("document_extractions"):
        return
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="pending"),
        sa.Column("engine_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="One OCR/AI extraction run for a document.",
    )


def _align_extracted_field_columns() -> None:
    _rename_column_if_exists("extracted_fields", "document_id", "source_document_id")
    _rename_column_if_exists("extracted_fields", "value", "field_value")
    _rename_column_if_exists("extracted_fields", "text_snippet", "raw_text_snippet")
    _add_column_if_missing("extracted_fields", sa.Column("document_extraction_id", sa.String(length=36), nullable=True))
    _create_fk_if_missing(
        "fk_extracted_fields_document_extraction_id",
        "extracted_fields",
        "document_extractions",
        ["document_extraction_id"],
        ["id"],
    )


def _align_user_field_corrections() -> None:
    if not _table_exists("user_field_corrections"):
        return
    _rename_column_if_exists("user_field_corrections", "document_id", "source_document_id")
    _rename_column_if_exists("user_field_corrections", "corrected_by_user_id", "user_id")
    _rename_column_if_exists("user_field_corrections", "metadata_json", "metadata")


def _create_gazette_searches() -> None:
    if _table_exists("gazette_searches"):
        return
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
        comment="Gazette search requests made for a case.",
    )


def _align_gazette_results() -> None:
    if not _table_exists("gazette_results"):
        return
    _add_column_if_missing("gazette_results", sa.Column("gazette_search_id", sa.String(length=36), nullable=True))
    _create_fk_if_missing(
        "fk_gazette_results_gazette_search_id",
        "gazette_results",
        "gazette_searches",
        ["gazette_search_id"],
        ["id"],
    )


def _align_risk_analyses() -> None:
    if not _table_exists("risk_analyses"):
        return
    _rename_column_if_exists("risk_analyses", "version", "model_version")
    _rename_column_if_exists("risk_analyses", "band", "level")
    _add_column_if_missing(
        "risk_analyses",
        sa.Column("engine_version", sa.String(length=80), nullable=False, server_default="mradi-risk-engine-v1"),
    )


def _align_risk_factors() -> None:
    _add_column_if_missing("risk_factors", sa.Column("risk_analysis_id", sa.String(length=36), nullable=True))
    _create_fk_if_missing("fk_risk_factors_risk_analysis_id", "risk_factors", "risk_analyses", ["risk_analysis_id"], ["id"])


def _align_expert_reviews() -> None:
    if not _table_exists("expert_reviews"):
        return
    _rename_column_if_exists("expert_reviews", "requested_by_user_id", "user_id")
    _add_column_if_missing("expert_reviews", sa.Column("review_summary", sa.Text(), nullable=False, server_default=""))
    _add_column_if_missing("expert_reviews", sa.Column("completed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("expert_reviews", sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"))


def _align_audit_logs() -> None:
    _rename_column_if_exists("audit_logs", "actor_user_id", "actor_id")
    _rename_column_if_exists("audit_logs", "target_type", "entity_type")
    _rename_column_if_exists("audit_logs", "target_id", "entity_id")
    _rename_column_if_exists("audit_logs", "metadata_json", "metadata")


def _align_payments_optional() -> None:
    if not _table_exists("payments_optional"):
        return
    _add_column_if_missing("payments_optional", sa.Column("organization_id", sa.String(length=36), nullable=True))
    _add_column_if_missing("payments_optional", sa.Column("case_id", sa.String(length=36), nullable=True))
    _add_column_if_missing("payments_optional", sa.Column("provider", sa.String(length=80), nullable=False, server_default=""))
    _add_column_if_missing("payments_optional", sa.Column("provider_payment_id", sa.String(length=255), nullable=False, server_default=""))
    _add_column_if_missing("payments_optional", sa.Column("amount", sa.Numeric(14, 2), nullable=True))
    _add_column_if_missing("payments_optional", sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"))
    _add_column_if_missing("payments_optional", sa.Column("paid_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("payments_optional", sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"))
    _create_fk_if_missing("fk_payments_optional_organization_id", "payments_optional", "organizations", ["organization_id"], ["id"])
    _create_fk_if_missing("fk_payments_optional_case_id", "payments_optional", "cases", ["case_id"], ["id"])


def _create_notifications() -> None:
    if _table_exists("notifications"):
        return
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("notification_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("channel", sa.String(length=40), nullable=False, server_default="in_app"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="unread"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="In-app and email notification records.",
    )


def _create_api_keys_optional() -> None:
    if _table_exists("api_keys_optional"):
        return
    op.create_table(
        "api_keys_optional",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        comment="Optional hashed API keys for future partner/API access.",
    )


def _create_requested_indexes() -> None:
    indexes = [
        ("organizations", "ix_organizations_created_at", ["created_at"]),
        ("users", "ix_users_organization_id", ["organization_id"]),
        ("users", "ix_users_created_at", ["created_at"]),
        ("cases", "ix_cases_user_id", ["user_id"]),
        ("cases", "ix_cases_parcel_number", ["parcel_number"]),
        ("cases", "ix_cases_title_number", ["title_number"]),
        ("cases", "ix_cases_created_at", ["created_at"]),
        ("cases", "ix_cases_risk_level", ["risk_level"]),
        ("case_participants", "ix_case_participants_case_id", ["case_id"]),
        ("case_participants", "ix_case_participants_user_id", ["user_id"]),
        ("case_participants", "ix_case_participants_created_at", ["created_at"]),
        ("documents", "ix_documents_case_id", ["case_id"]),
        ("documents", "ix_documents_uploaded_by_user_id", ["uploaded_by_user_id"]),
        ("documents", "ix_documents_uploaded_at", ["uploaded_at"]),
        ("documents", "ix_documents_created_at", ["created_at"]),
        ("document_extractions", "ix_document_extractions_case_id", ["case_id"]),
        ("document_extractions", "ix_document_extractions_document_id", ["document_id"]),
        ("document_extractions", "ix_document_extractions_created_at", ["created_at"]),
        ("extracted_fields", "ix_extracted_fields_source_document_id", ["source_document_id"]),
        ("extracted_fields", "ix_extracted_fields_document_extraction_id", ["document_extraction_id"]),
        ("extracted_fields", "ix_extracted_fields_created_at", ["created_at"]),
        ("user_field_corrections", "ix_user_field_corrections_source_document_id", ["source_document_id"]),
        ("user_field_corrections", "ix_user_field_corrections_user_id", ["user_id"]),
        ("user_field_corrections", "ix_user_field_corrections_created_at", ["created_at"]),
        ("gazette_searches", "ix_gazette_searches_case_id", ["case_id"]),
        ("gazette_searches", "ix_gazette_searches_user_id", ["user_id"]),
        ("gazette_searches", "ix_gazette_searches_created_at", ["created_at"]),
        ("gazette_results", "ix_gazette_results_case_id", ["case_id"]),
        ("gazette_results", "ix_gazette_results_gazette_search_id", ["gazette_search_id"]),
        ("gazette_results", "ix_gazette_results_created_at", ["created_at"]),
        ("risk_analyses", "ix_risk_analyses_case_id", ["case_id"]),
        ("risk_analyses", "ix_risk_analyses_level", ["level"]),
        ("risk_analyses", "ix_risk_analyses_created_at", ["created_at"]),
        ("risk_factors", "ix_risk_factors_case_id", ["case_id"]),
        ("risk_factors", "ix_risk_factors_risk_analysis_id", ["risk_analysis_id"]),
        ("risk_factors", "ix_risk_factors_created_at", ["created_at"]),
        ("reports", "ix_reports_case_id", ["case_id"]),
        ("reports", "ix_reports_created_at", ["created_at"]),
        ("audit_logs", "ix_audit_logs_actor_id", ["actor_id"]),
        ("audit_logs", "ix_audit_logs_case_id", ["case_id"]),
        ("audit_logs", "ix_audit_logs_entity", ["entity_type", "entity_id"]),
        ("audit_logs", "ix_audit_logs_created_at", ["created_at"]),
        ("expert_reviews", "ix_expert_reviews_case_id", ["case_id"]),
        ("expert_reviews", "ix_expert_reviews_user_id", ["user_id"]),
        ("expert_reviews", "ix_expert_reviews_created_at", ["created_at"]),
        ("notifications", "ix_notifications_user_id", ["user_id"]),
        ("notifications", "ix_notifications_case_id", ["case_id"]),
        ("notifications", "ix_notifications_created_at", ["created_at"]),
        ("payments_optional", "ix_payments_optional_user_id", ["user_id"]),
        ("payments_optional", "ix_payments_optional_case_id", ["case_id"]),
        ("payments_optional", "ix_payments_optional_created_at", ["created_at"]),
        ("api_keys_optional", "ix_api_keys_optional_user_id", ["user_id"]),
        ("api_keys_optional", "ix_api_keys_optional_key_prefix", ["key_prefix"]),
        ("api_keys_optional", "ix_api_keys_optional_created_at", ["created_at"]),
        ("agent_audit_events", "ix_agent_audit_events_case_id", ["case_id"]),
        ("agent_audit_events", "ix_agent_audit_events_created_at", ["created_at"]),
    ]
    for table_name, index_name, columns in indexes:
        _create_index_if_missing(table_name, index_name, columns)


def _table_exists(table_name: str) -> bool:
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _rename_table_if_exists(old_name: str, new_name: str) -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if old_name in tables and new_name not in tables:
        op.rename_table(old_name, new_name)


def _drop_table_if_exists(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def _rename_column_if_exists(table_name: str, old_name: str, new_name: str) -> None:
    columns = _columns(table_name)
    if old_name in columns and new_name not in columns:
        op.alter_column(table_name, old_name, new_column_name=new_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_name in set(sa.inspect(op.get_bind()).get_table_names()) and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _table_exists(table_name):
        return
    table_columns = _columns(table_name)
    if not set(columns).issubset(table_columns):
        return
    existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name):
        return
    existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def _create_fk_if_missing(
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
) -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    if not _table_exists(source_table) or not _table_exists(referent_table):
        return
    if not set(local_cols).issubset(_columns(source_table)):
        return
    existing = {
        tuple(fk.get("constrained_columns", []))
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(source_table)
    }
    if tuple(local_cols) not in existing:
        op.create_foreign_key(constraint_name, source_table, referent_table, local_cols, remote_cols)
