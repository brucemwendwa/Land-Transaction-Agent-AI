"""add production integration tables and review assignment fields

Revision ID: 0006_production_integrations
Revises: 0005_mradi_schema_alignment
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_production_integrations"
down_revision = "0005_mradi_schema_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_column_if_missing("documents", sa.Column("bucket", sa.String(length=255), nullable=False, server_default=""))
    _add_column_if_missing("expert_reviews", sa.Column("assigned_to_user_id", sa.String(length=36), nullable=True))
    _add_column_if_missing("expert_reviews", sa.Column("recommendation", sa.Text(), nullable=False, server_default=""))
    _create_fk_if_missing(
        "fk_expert_reviews_assigned_to_user_id",
        "expert_reviews",
        "users",
        ["assigned_to_user_id"],
        ["id"],
    )
    _create_payments()
    _create_payment_events()
    _create_subscriptions()
    _create_requested_indexes()


def downgrade() -> None:
    for table_name, index_name in [
        ("subscriptions", "ix_subscriptions_created_at"),
        ("subscriptions", "ix_subscriptions_status"),
        ("subscriptions", "ix_subscriptions_user_id"),
        ("payment_events", "ix_payment_events_created_at"),
        ("payment_events", "ix_payment_events_provider_event_id"),
        ("payment_events", "ix_payment_events_payment_id"),
        ("payments", "ix_payments_created_at"),
        ("payments", "ix_payments_provider_checkout_request_id"),
        ("payments", "ix_payments_status"),
        ("payments", "ix_payments_case_id"),
        ("payments", "ix_payments_user_id"),
        ("expert_reviews", "ix_expert_reviews_assigned_to_user_id"),
    ]:
        _drop_index_if_exists(table_name, index_name)
    _drop_table_if_exists("subscriptions")
    _drop_table_if_exists("payment_events")
    _drop_table_if_exists("payments")
    _drop_column_if_exists("expert_reviews", "recommendation")
    _drop_column_if_exists("expert_reviews", "assigned_to_user_id")
    _drop_column_if_exists("documents", "bucket")


def _create_payments() -> None:
    if _table_exists("payments"):
        return
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="mpesa"),
        sa.Column("purpose", sa.String(length=80), nullable=False, server_default="report_unlock"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("phone_number", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="pending"),
        sa.Column("provider_merchant_request_id", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("provider_checkout_request_id", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("provider_receipt_number", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("result_code", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("result_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="Provider-backed payment attempts, including M-Pesa STK Push.",
    )


def _create_payment_events() -> None:
    if _table_exists("payment_events"):
        return
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="mpesa"),
        sa.Column("provider_event_id", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="Append-only payment provider callback and status events.",
    )


def _create_subscriptions() -> None:
    if _table_exists("subscriptions"):
        return
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("plan_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="inactive"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="Optional recurring entitlement records for firms and repeat buyers.",
    )


def _create_requested_indexes() -> None:
    indexes = [
        ("expert_reviews", "ix_expert_reviews_assigned_to_user_id", ["assigned_to_user_id"]),
        ("payments", "ix_payments_user_id", ["user_id"]),
        ("payments", "ix_payments_case_id", ["case_id"]),
        ("payments", "ix_payments_status", ["status"]),
        ("payments", "ix_payments_provider_checkout_request_id", ["provider_checkout_request_id"]),
        ("payments", "ix_payments_created_at", ["created_at"]),
        ("payment_events", "ix_payment_events_payment_id", ["payment_id"]),
        ("payment_events", "ix_payment_events_provider_event_id", ["provider_event_id"]),
        ("payment_events", "ix_payment_events_created_at", ["created_at"]),
        ("subscriptions", "ix_subscriptions_user_id", ["user_id"]),
        ("subscriptions", "ix_subscriptions_status", ["status"]),
        ("subscriptions", "ix_subscriptions_created_at", ["created_at"]),
    ]
    for table_name, index_name, columns in indexes:
        _create_index_if_missing(table_name, index_name, columns)


def _table_exists(table_name: str) -> bool:
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _table_exists(table_name) and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def _drop_table_if_exists(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _table_exists(table_name) or not set(columns).issubset(_columns(table_name)):
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
