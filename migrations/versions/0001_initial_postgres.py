"""Initial PostgreSQL schema with user ownership and pgvector.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "title", sa.String(200), nullable=False, server_default="New conversation"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.create_table(
        "task_embeddings",
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
    )
    op.create_index("ix_task_embeddings_user_id", "task_embeddings", ["user_id"])
    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE task_embeddings ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY task_owner_policy ON tasks "
        "USING (user_id = auth.uid()::text) "
        "WITH CHECK (user_id = auth.uid()::text)"
    )
    op.execute(
        "CREATE POLICY conversation_owner_policy ON conversations "
        "USING (user_id = auth.uid()::text) "
        "WITH CHECK (user_id = auth.uid()::text)"
    )
    op.execute(
        "CREATE POLICY embedding_owner_policy ON task_embeddings "
        "USING (user_id = auth.uid()::text) "
        "WITH CHECK (user_id = auth.uid()::text)"
    )
    op.execute(
        "CREATE POLICY message_owner_policy ON messages "
        "USING (EXISTS (SELECT 1 FROM conversations "
        "WHERE conversations.id = messages.conversation_id "
        "AND conversations.user_id = auth.uid()::text))"
    )


def downgrade():
    op.drop_table("task_embeddings")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
