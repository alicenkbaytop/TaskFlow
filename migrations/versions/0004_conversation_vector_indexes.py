"""Add indexes for chronological history and semantic vector search.

Revision ID: 0004_conversation_vector_indexes
Revises: 0003_remove_google_signin_state
"""

from alembic import op

revision = "0004_conversation_vector_indexes"
down_revision = "0003_remove_google_signin_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_conversation_id_id", "messages", ["conversation_id", "id"]
    )
    op.execute(
        "CREATE INDEX ix_task_embeddings_vector_cosine "
        "ON task_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_task_embeddings_vector_cosine")
    op.drop_index("ix_messages_conversation_id_id", table_name="messages")
