"""Migrate existing admins/sessions; add accounts, scheduling and pause controls."""
from alembic import op
import sqlalchemy as sa

revision = "b719ac82d401"
down_revision = "637ce92cdb99"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE edition_status ADD VALUE IF NOT EXISTS 'SCHEDULED'")
    op.execute("ALTER TYPE edition_status ADD VALUE IF NOT EXISTS 'PAUSED'")
    op.rename_table("admins", "accounts")
    role = sa.Enum("ADMIN", "USER", name="account_role")
    role.create(op.get_bind())
    op.add_column("accounts", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("accounts", sa.Column("name", sa.String(80), nullable=True))
    op.add_column("accounts", sa.Column("role", role, nullable=False, server_default="USER"))
    op.add_column("accounts", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.execute("""UPDATE accounts SET name = username, role = 'ADMIN',
        email = CASE WHEN id = (SELECT min(id) FROM accounts) THEN 'admin@example.com'
        ELSE 'admin-' || id || '@example.com' END""")
    op.alter_column("accounts", "email", nullable=False)
    op.alter_column("accounts", "name", nullable=False)
    op.alter_column("accounts", "username", nullable=True)
    op.alter_column("accounts", "created_at", server_default=None)
    op.create_unique_constraint("uq_accounts_email", "accounts", ["email"])
    op.alter_column("auth_sessions", "admin_id", new_column_name="account_id")
    op.execute("ALTER INDEX ix_auth_sessions_admin_id RENAME TO ix_auth_sessions_account_id")
    op.add_column("editions", sa.Column("scheduled_at", sa.DateTime(timezone=True)))
    op.add_column("editions", sa.Column("results_published", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE editions SET results_published = true WHERE status = 'FINISHED'")
    op.add_column("participants", sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL")))
    op.create_index("ix_participants_account_id", "participants", ["account_id"])
    op.create_unique_constraint("uq_participants_edition_account", "participants", ["edition_id", "account_id"])
    op.add_column("participants", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    # Refuse a lossy rollback rather than deleting newly registered accounts.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM accounts WHERE username IS NULL OR role = 'USER'")):
        raise RuntimeError("Cannot downgrade while new user accounts exist. Export/migrate accounts explicitly first.")
    op.execute("UPDATE editions SET status = 'LIVE' WHERE status = 'PAUSED'")
    op.execute("UPDATE editions SET status = 'DRAFT' WHERE status = 'SCHEDULED'")
    op.drop_column("participants", "is_active")
    op.drop_constraint("uq_participants_edition_account", "participants", type_="unique")
    op.drop_index("ix_participants_account_id", table_name="participants")
    op.drop_column("participants", "account_id")
    op.drop_column("editions", "results_published")
    op.drop_column("editions", "scheduled_at")
    op.execute("ALTER INDEX ix_auth_sessions_account_id RENAME TO ix_auth_sessions_admin_id")
    op.alter_column("auth_sessions", "account_id", new_column_name="admin_id")
    op.drop_constraint("uq_accounts_email", "accounts", type_="unique")
    for column in ["email", "name", "role", "created_at"]:
        op.drop_column("accounts", column)
    op.alter_column("accounts", "username", nullable=False)
    op.rename_table("accounts", "admins")
    sa.Enum(name="account_role").drop(connection)
    # PostgreSQL cannot drop individual enum values; leaving unused values is safe.
