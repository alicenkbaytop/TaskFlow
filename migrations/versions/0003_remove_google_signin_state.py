"""Remove transient PKCE state storage from retired Google sign-in flow.

Revision ID: 0003_remove_google_signin_state
Revises: 0002_google_signin
"""

from alembic import op

revision = "0003_remove_google_signin_state"
down_revision = "0002_google_signin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("oauth_states")


def downgrade() -> None:
    raise NotImplementedError(
        "Retired Google OAuth state cannot be restored automatically"
    )
