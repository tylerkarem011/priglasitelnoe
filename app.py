from __future__ import annotations

import json
import secrets
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = ROOT / "letters.sqlite3"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app = FastAPI(title="Своё письмо API", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def connect():
    if USE_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def execute(conn, query: str, params=()):
    # Keep one query style in the application while supporting SQLite locally
    # and PostgreSQL in production.
    if USE_POSTGRES:
        query = query.replace("?", "%s")
    return conn.execute(query, params)


def init_db() -> None:
    with closing(connect()) as conn:
        if USE_POSTGRES:
            execute(conn, """CREATE TABLE IF NOT EXISTS letters (
                id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                author_token TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            execute(conn, """CREATE TABLE IF NOT EXISTS reactions (
                id BIGSERIAL PRIMARY KEY,
                letter_id TEXT NOT NULL REFERENCES letters(id),
                reaction TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        else:
            execute(conn, """CREATE TABLE IF NOT EXISTS letters (
                id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                author_token TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            columns = {row["name"] for row in execute(conn, "PRAGMA table_info(letters)").fetchall()}
            if "author_token" not in columns:
                execute(conn, "ALTER TABLE letters ADD COLUMN author_token TEXT")
            execute(conn, """CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                letter_id TEXT NOT NULL,
                reaction TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(letter_id) REFERENCES letters(id)
            )""")
        conn.commit()


init_db()


class LetterPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    recipient: str = "тебе"
    sender: str = ""
    intro: str = "Это для тебя"
    envelopeHint: str = "нажми на конверт"
    greeting: str = "Это тебе, {name}"
    title: str = ""
    message: str = ""
    signature: str = ""
    ending: str = ""
    occasion: str = "Личное письмо"
    theme: str = "rose"


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/l/{letter_id}")
def recipient_page(letter_id: str):
    # The same app shell loads the saved letter through the API.
    return FileResponse(STATIC / "index.html")


@app.post("/api/letters", status_code=201)
def create_letter(payload: LetterPayload):
    config: dict[str, Any] = payload.model_dump()
    # Small uploaded media files are stored as data URLs with the letter in this MVP.

    author_token = secrets.token_urlsafe(24)
    with closing(connect()) as conn:
        for _ in range(5):
            letter_id = secrets.token_urlsafe(8).replace("-", "a").replace("_", "b")[:11]
            exists = execute(conn, "SELECT 1 FROM letters WHERE id = ?", (letter_id,)).fetchone()
            if not exists:
                break
        else:
            raise HTTPException(status_code=500, detail="Не удалось создать уникальную ссылку")

        execute(conn,
            "INSERT INTO letters (id, config_json, author_token) VALUES (?, ?, ?)",
            (letter_id, json.dumps(config, ensure_ascii=False), author_token),
        )
        conn.commit()

    return {
        "id": letter_id,
        "url": f"/l/{letter_id}",
        "author_url": f"/author/{letter_id}?token={author_token}",
    }


@app.get("/api/letters/{letter_id}")
def get_letter(letter_id: str):
    with closing(connect()) as conn:
        row = execute(conn,
            "SELECT config_json FROM letters WHERE id = ?", (letter_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Письмо не найдено")
    return json.loads(row["config_json"])


class ReactionPayload(BaseModel):
    reaction: str
    message: str = ""

@app.post("/api/letters/{letter_id}/reactions", status_code=201)
def create_reaction(letter_id: str, payload: ReactionPayload):
    allowed = {"smile", "talk", "time", "message"}
    if payload.reaction not in allowed:
        raise HTTPException(status_code=400, detail="Неизвестная реакция")
    message = payload.message.strip()[:500]
    with closing(connect()) as conn:
        exists = execute(conn, "SELECT 1 FROM letters WHERE id = ?", (letter_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Письмо не найдено")
        execute(conn,
            "INSERT INTO reactions (letter_id, reaction, message) VALUES (?, ?, ?)",
            (letter_id, payload.reaction, message),
        )
        conn.commit()
    return {"status": "saved"}

@app.get("/api/letters/{letter_id}/reactions")
def list_reactions(letter_id: str, token: str):
    with closing(connect()) as conn:
        owner = execute(conn,
            "SELECT author_token FROM letters WHERE id = ?", (letter_id,)
        ).fetchone()
        if owner is None:
            raise HTTPException(status_code=404, detail="Письмо не найдено")
        if not owner["author_token"] or not secrets.compare_digest(owner["author_token"], token):
            raise HTTPException(status_code=403, detail="Неверная ссылка автора")
        rows = execute(conn,
            "SELECT reaction, message, created_at FROM reactions WHERE letter_id = ? ORDER BY id DESC",
            (letter_id,),
        ).fetchall()
    return {"reactions": [dict(row) for row in rows]}

@app.get("/author/{letter_id}")
def author_page(letter_id: str):
    return FileResponse(STATIC / "index.html")

@app.get("/health")
def health():
    return {"status": "ok"}
