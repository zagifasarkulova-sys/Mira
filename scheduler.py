import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from database import get_pool, get_goals, get_diary_entries, get_user
from ai import ask_ai

logger = logging.getLogger(__name__)


async def send_morning_plan(bot: Bot):
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT * FROM users")

    for user in users:
        try:
            user_id = user["user_id"]
            name = user["user_name"] or user["username"] or "друг"
            goals = await get_goals(user_id)
            diary = await get_diary_entries(user_id, limit=5)

            goals_text = "\n".join([f"- {g['text']}" for g in goals]) or "не заданы"
            diary_text = "\n".join([f"[{e['entry_type']}] {e['text']}" for e in diary]) or "нет"

            prompt = (
                f"Составь короткий утренний план на сегодня для пользователя.\n"
                f"Его цели: {goals_text}\n"
                f"Последние записи в дневнике: {diary_text}\n\n"
                f"3-5 конкретных действий на сегодня. Коротко и по делу."
            )

            plan = await ask_ai(
                user_id=user_id,
                user_message=prompt,
                history=[],
                system_prompt=user["system_prompt"] or "",
            )

            await bot.send_message(
                user_id,
                f"☀️ <b>Доброе утро, {name}!</b>\n\n{plan}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Morning plan failed for {user['user_id']}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    scheduler.add_job(
        send_morning_plan,
        CronTrigger(hour=8, minute=0, timezone="Asia/Almaty"),
        args=[bot],
        id="morning_plan",
        replace_existing=True,
        misfire_grace_time=300
    )

    logger.info("Scheduler configured")
    return scheduler
