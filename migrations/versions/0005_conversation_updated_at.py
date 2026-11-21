"""Track conversation activity for recent-first history ordering.

Revision ID: 0005_conversation_updated_at
Revises: 0004_conversation_vector_indexes
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_conversation_updated_at"
down_revision = "0004_conversation_vector_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_conversations_user_updated",
        "conversations",
        ["user_id", "updated_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.drop_column("conversations", "updated_at")
