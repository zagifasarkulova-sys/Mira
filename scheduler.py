from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
import logging

from database import get_all_users, get_todays_words
from quiz import send_quiz

logger = logging.getLogger(__name__)


async def send_evening_quiz(bot: Bot):
    """Send quiz at 20:00 only to users who requested words today."""
    users = await get_all_users()
    for user in users:
        try:
            words = await get_todays_words(user["user_id"])
            if words:
                await send_quiz(bot, user["user_id"], list(words))
                logger.info(f"Quiz sent to {user['user_id']}")
        except Exception as e:
            logger.error(f"Error sending quiz to {user['user_id']}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Aqtobe")

    scheduler.add_job(
        send_evening_quiz,
        CronTrigger(hour=20, minute=0, timezone="Asia/Aqtobe"),
        args=[bot],
        id="evening_quiz",
        replace_existing=True,
    )

    return scheduler
