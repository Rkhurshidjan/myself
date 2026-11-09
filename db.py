"""Ma'lumotlar bazasi qatlami.

DATABASE_URL o'rnatilgan bo'lsa PostgreSQL (Railway Postgres) ishlatiladi,
aks holda SQLite fayli (DB_PATH, standart: data/birthdays.db).
"""
import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", "data/birthdays.db")
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_PG:
    import psycopg


@contextmanager
def _conn():
    if IS_PG:
        conn = psycopg.connect(DATABASE_URL)
    else:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _q(sql: str) -> str:
    """SQLite '?' belgilarini PostgreSQL '%s' ga almashtiradi."""
    return sql.replace("?", "%s") if IS_PG else sql


def init_db() -> None:
    id_col = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with _conn() as c:
        cur = c.cursor()
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS employees (
                id {id_col},
                name TEXT NOT NULL,
                day INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS chats (
                chat_id BIGINT PRIMARY KEY,
                title TEXT
            )"""
        )


def add_employee(name: str, day: int, month: int, year: int | None) -> int:
    with _conn() as c:
        cur = c.cursor()
        if IS_PG:
            cur.execute(
                _q("INSERT INTO employees (name, day, month, year) VALUES (?, ?, ?, ?) RETURNING id"),
                (name, day, month, year),
            )
            return cur.fetchone()[0]
        cur.execute(
            "INSERT INTO employees (name, day, month, year) VALUES (?, ?, ?, ?)",
            (name, day, month, year),
        )
        return cur.lastrowid


def delete_employee(emp_id: int) -> bool:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM employees WHERE id = ?"), (emp_id,))
        return cur.rowcount > 0


def list_employees() -> list[tuple]:
    """(id, name, day, month, year) ro'yxati."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, name, day, month, year FROM employees ORDER BY month, day, name")
        return cur.fetchall()


def add_chat(chat_id: int, title: str | None) -> None:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM chats WHERE chat_id = ?"), (chat_id,))
        cur.execute(_q("INSERT INTO chats (chat_id, title) VALUES (?, ?)"), (chat_id, title))


def remove_chat(chat_id: int) -> bool:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM chats WHERE chat_id = ?"), (chat_id,))
        return cur.rowcount > 0


def list_chats() -> list[int]:
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT chat_id FROM chats")
        return [r[0] for r in cur.fetchall()]
