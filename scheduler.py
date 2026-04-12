from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

from database import get_all_users, get_todays_words, get_all_used_words, save_words
from claude_api import generate_words
from quiz import send_quiz

logger = logging.getLogger(__name__)


def _words_keyboard(words: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🔊 {w['word']}", callback_data=f"tts:{w['word']}")]
        for w in words
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _words_text(words: list) -> str:
    text = "☀️ <b>Утренние слова на сегодня:</b>\n\n"
    for i, w in enumerate(words, 1):
        text += f"{i}. <b>{w['word']}</b> — {w['translation']}\n"
        text += f"   <i>{w['example']}</i>\n\n"
    text += "⏰ Квиз придёт сегодня в <b>20:00</b>"
    return text


async def send_morning_words(bot: Bot):
    """Send 5 new words at 9:00 to all users who have no words today."""
    users = await get_all_users()
    for user in users:
        user_id = user["user_id"]
        try:
            existing = await get_todays_words(user_id)
            if existing:
                continue  # Already has words today (requested manually)

            used = await get_all_used_words(user_id)
            words = await generate_words(used)
            await save_words(user_id, words)

            await bot.send_message(
                user_id,
                _words_text(words),
                parse_mode="HTML",
                reply_markup=_words_keyboard(words),
            )
            logger.info(f"Morning words sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending morning words to {user_id}: {e}")


async def send_evening_quiz(bot: Bot):
    """Send quiz at 20:00 only to users who requested words today."""
    users = await get_all_users()
    for user in users:
        user_id = user["user_id"]
        try:
            words = await get_todays_words(user_id)
            if words:
                await send_quiz(bot, user_id, list(words))
                logger.info(f"Quiz sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending quiz to {user_id}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Aqtobe")

    scheduler.add_job(
        send_morning_words,
        CronTrigger(hour=9, minute=0, timezone="Asia/Aqtobe"),
        args=[bot],
        id="morning_words",
        replace_existing=True,
    )

    scheduler.add_job(
        send_evening_quiz,
        CronTrigger(hour=20, minute=0, timezone="Asia/Aqtobe"),
        args=[bot],
        id="evening_quiz",
        replace_existing=True,
    )

    return scheduler
