"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-05-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


account_type_enum = postgresql.ENUM(
    "privato",
    "libero_professionista",
    "azienda",
    "ditta_individuale",
    "pubblica_amministrazione",
    name="account_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    account_type_enum.create(bind, checkfirst=True)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("codice_fiscale", sa.String(length=32), nullable=True),
        sa.Column("partita_iva", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column("profile_picture_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("external_auth_provider", sa.String(length=64), nullable=True),
        sa.Column("external_auth_subject", sa.String(length=255), nullable=True),
        sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_privacy_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("external_auth_subject"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index("ix_users_codice_fiscale", "users", ["codice_fiscale"], unique=False)
    op.create_index("ix_users_partita_iva", "users", ["partita_iva"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_users_partita_iva", table_name="users")
    op.drop_index("ix_users_codice_fiscale", table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    account_type_enum.drop(bind, checkfirst=True)
