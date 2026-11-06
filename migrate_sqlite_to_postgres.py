"""One-time migration of the local letters.sqlite3 database to PostgreSQL.

Run after installing requirements:
  DATABASE_URL='postgresql://...' python migrate_sqlite_to_postgres.py
"""
import os
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent
SQLITE_PATH = ROOT / "letters.sqlite3"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if not DATABASE_URL:
    sys.exit("Set DATABASE_URL to your Neon PostgreSQL connection string first.")
if not SQLITE_PATH.exists():
    sys.exit(f"SQLite database not found: {SQLITE_PATH}")

source = sqlite3.connect(SQLITE_PATH)
source.row_factory = sqlite3.Row
letters = source.execute("SELECT id, config_json, author_token FROM letters").fetchall()
reactions = source.execute(
    "SELECT id, letter_id, reaction, message FROM reactions ORDER BY id"
).fetchall()

with psycopg.connect(DATABASE_URL, row_factory=dict_row) as target:
    target.execute("""CREATE TABLE IF NOT EXISTS letters (
        id TEXT PRIMARY KEY,
        config_json TEXT NOT NULL,
        author_token TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    target.execute("""CREATE TABLE IF NOT EXISTS reactions (
        id BIGSERIAL PRIMARY KEY,
        letter_id TEXT NOT NULL REFERENCES letters(id),
        reaction TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    for row in letters:
        target.execute(
            "INSERT INTO letters (id, config_json, author_token) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (row["id"], row["config_json"], row["author_token"]),
        )
    for row in reactions:
        target.execute(
            "INSERT INTO reactions (id, letter_id, reaction, message) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (row["id"], row["letter_id"], row["reaction"], row["message"]),
        )
    target.execute("SELECT setval(pg_get_serial_sequence('reactions', 'id'), COALESCE((SELECT MAX(id) FROM reactions), 1), true)")
    target.commit()

print(f"Migration complete: {len(letters)} letters, {len(reactions)} reactions.")
