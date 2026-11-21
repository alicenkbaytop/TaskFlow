"""Add indexes for chronological history and semantic vector search.

Revision ID: 0004_conversation_vector_indexes
Revises: 0003_remove_google_signin_state
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_conversation_vector_indexes"
down_revision = "0003_remove_google_signin_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_conversation_id_id "
        "ON messages (conversation_id, id)"
    )
    # Concurrent creation avoids blocking writes while the vector index builds.
    context = op.get_context()
    with context.autocommit_block():
        if not context.as_sql:
            invalid_index = (
                op.get_bind()
                .execute(
                    sa.text(
                        "SELECT EXISTS (SELECT 1 FROM pg_index "
                        "WHERE indexrelid = to_regclass(:index_name) "
                        "AND NOT indisvalid)"
                    ),
                    {"index_name": "ix_task_embeddings_vector_cosine"},
                )
                .scalar()
            )
            if invalid_index:
                op.execute(
                    "DROP INDEX CONCURRENTLY IF EXISTS ix_task_embeddings_vector_cosine"
                )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_task_embeddings_vector_cosine "
            "ON task_embeddings USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_task_embeddings_vector_cosine")
    op.drop_index("ix_messages_conversation_id_id", table_name="messages")
