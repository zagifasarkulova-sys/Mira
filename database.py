import os
import asyncpg
import logging

logger = logging.getLogger(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]
_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                user_name TEXT DEFAULT '',
                system_prompt TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                text TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS diary (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                entry_type TEXT,  -- 'success' | 'mistake' | 'note'
                text TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                role TEXT,  -- 'user' | 'assistant'
                content TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                filename TEXT,
                chunk_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    logger.info("DB initialized")


async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def create_user(user_id: int, username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, user_id, username)


async def update_user(user_id: int, **kwargs):
    pool = await get_pool()
    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE users SET {fields} WHERE user_id = $1",
            user_id, *kwargs.values()
        )


async def get_goals(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM goals WHERE user_id = $1 AND active = TRUE ORDER BY created_at DESC",
            user_id
        )


async def add_goal(user_id: int, text: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO goals (user_id, text) VALUES ($1, $2)",
            user_id, text
        )


async def delete_goal(goal_id: int, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE goals SET active = FALSE WHERE id = $1 AND user_id = $2",
            goal_id, user_id
        )


async def add_diary_entry(user_id: int, entry_type: str, text: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO diary (user_id, entry_type, text) VALUES ($1, $2, $3)",
            user_id, entry_type, text
        )


async def get_diary_entries(user_id: int, limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM diary WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2
        """, user_id, limit)


async def get_chat_history(user_id: int, limit: int = 10):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content FROM chat_history
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2
        """, user_id, limit)
        return list(reversed(rows))


async def save_message(user_id: int, role: str, content: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
            user_id, role, content
        )
        # Держим только последние 50 сообщений
        await conn.execute("""
            DELETE FROM chat_history WHERE user_id = $1
            AND id NOT IN (
                SELECT id FROM chat_history WHERE user_id = $1
                ORDER BY created_at DESC LIMIT 50
            )
        """, user_id)


async def clear_history(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)


async def add_document(user_id: int, filename: str, chunk_count: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO documents (user_id, filename, chunk_count) VALUES ($1, $2, $3)",
            user_id, filename, chunk_count
        )


async def get_documents(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
