"""Store short-lived PKCE state for Supabase Google sign-in.

Revision ID: 0002_google_signin
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_google_signin"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code_verifier", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE oauth_states ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("oauth_states")
