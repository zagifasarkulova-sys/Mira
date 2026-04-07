import asyncpg
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DATABASE_URL = os.getenv("DATABASE_URL")
_AQTOBE_TZ = ZoneInfo("Asia/Aqtobe")


def _today() -> date:
    """Return today's date in Aqtobe timezone (matches scheduler timezone)."""
    return datetime.now(_AQTOBE_TZ).date()

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                morning_hour INT DEFAULT 9,
                evening_hour INT DEFAULT 20,
                streak INT DEFAULT 0,
                last_quiz_date DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                example TEXT NOT NULL,
                sent_date DATE NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                quiz_date DATE NOT NULL,
                score INT NOT NULL,
                total INT NOT NULL
            )
        """)
        # Ensure uniqueness so ON CONFLICT DO NOTHING works correctly
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_quiz_results_user_date
            ON quiz_results (user_id, quiz_date)
        """)


async def register_user(user_id: int, username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, username)


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users")


async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def save_words(user_id: int, words: list[dict]):
    pool = await get_pool()
    async with pool.acquire() as conn:
        today = _today()
        for w in words:
            await conn.execute("""
                INSERT INTO words (user_id, word, translation, example, sent_date)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, w["word"], w["translation"], w["example"], today)


async def get_todays_words(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        today = _today()
        return await conn.fetch("""
            SELECT word, translation, example FROM words
            WHERE user_id = $1 AND sent_date = $2
        """, user_id, today)


async def get_all_used_words(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT word FROM words WHERE user_id = $1", user_id)
        return [r["word"] for r in rows]


async def save_quiz_result(user_id: int, score: int, total: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        today = _today()
        await conn.execute("""
            INSERT INTO quiz_results (user_id, quiz_date, score, total)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
        """, user_id, today, score, total)

        user = await conn.fetchrow("SELECT last_quiz_date, streak FROM users WHERE user_id = $1", user_id)
        last = user["last_quiz_date"]
        streak = user["streak"]

        if last == today - timedelta(days=1):
            streak += 1
        elif last != today:
            streak = 1

        await conn.execute("""
            UPDATE users SET streak = $1, last_quiz_date = $2 WHERE user_id = $3
        """, streak, today, user_id)

        return streak


async def get_stats(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT streak FROM users WHERE user_id = $1", user_id)
        total_words = await conn.fetchval("SELECT COUNT(*) FROM words WHERE user_id = $1", user_id)
        quizzes = await conn.fetch("SELECT score, total FROM quiz_results WHERE user_id = $1", user_id)
        return {
            "streak": user["streak"],
            "total_words": total_words,
            "quizzes": quizzes,
        }
