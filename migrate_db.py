import sqlite3

conn = sqlite3.connect("taskflow.db")
cursor = conn.cursor()

# Check which columns already exist
cursor.execute("PRAGMA table_info(tasks)")
existing_columns = {row[1] for row in cursor.fetchall()}

# Add missing columns
if "due_date" not in existing_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN due_date DATE")

if "created_at" not in existing_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN created_at DATETIME")

if "updated_at" not in existing_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN updated_at DATETIME")

# Give existing tasks timestamps
cursor.execute("""
    UPDATE tasks
    SET created_at = CURRENT_TIMESTAMP
    WHERE created_at IS NULL
""")

cursor.execute("""
    UPDATE tasks
    SET updated_at = CURRENT_TIMESTAMP
    WHERE updated_at IS NULL
""")

conn.commit()
conn.close()

print("Database migration completed.")
