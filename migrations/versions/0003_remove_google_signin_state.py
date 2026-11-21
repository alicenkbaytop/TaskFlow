"""Retain legacy PKCE state table without using it in the retired sign-in flow.

Revision ID: 0003_remove_google_signin_state
Revises: 0002_google_signin
"""

revision = "0003_remove_google_signin_state"
down_revision = "0002_google_signin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This table may exist in a deployed database. It contains only ephemeral
    # OAuth state, but deployment migrations must not delete existing data.
    pass


def downgrade() -> None:
    pass
