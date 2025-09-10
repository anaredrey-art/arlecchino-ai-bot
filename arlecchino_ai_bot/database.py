import aiosqlite
import os

DB_PATH = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                messages_used INTEGER DEFAULT 0,
                tier TEXT DEFAULT 'free',  -- 'free', 'basic', 'premium'
                last_reset DATE
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT messages_used, tier, last_reset FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"messages_used": row[0], "tier": row[1], "last_reset": row[2]}
            return None

async def create_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, messages_used, tier, last_reset) VALUES (?, 0, 'free', date('now'))",
            (user_id,)
        )
        await db.commit()

async def increment_message(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET messages_used = messages_used + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def set_tier(user_id: int, tier: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET tier = ?, messages_used = 0 WHERE user_id = ?", (tier, user_id))
        await db.commit()