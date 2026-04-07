import random
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import save_quiz_result
from claude_api import generate_quiz_options

# In-memory quiz state: {user_id: {"words": [...], "current": 0, "score": 0}}
quiz_state: dict = {}


async def send_quiz(bot: Bot, user_id: int, words: list[dict]):
    """Start quiz session for a user."""
    quiz_state[user_id] = {
        "words": words,
        "current": 0,
        "score": 0,
    }
    await bot.send_message(user_id, "🧠 <b>Вечерний квиз!</b>\nПроверим, как усвоились слова дня.", parse_mode="HTML")
    await send_question(bot, user_id)


async def send_question(bot: Bot, user_id: int):
    state = quiz_state.get(user_id)
    if not state:
        return

    idx = state["current"]
    words = state["words"]

    if idx >= len(words):
        await finish_quiz(bot, user_id)
        return

    word_data = words[idx]
    word = word_data["word"]
    translation = word_data["translation"]

    options = await generate_quiz_options(word, translation, words)

    buttons = []
    for opt in options:
        is_correct = opt == translation
        callback_data = f"quiz:{1 if is_correct else 0}:{idx}"
        buttons.append([InlineKeyboardButton(text=opt, callback_data=callback_data)])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await bot.send_message(
        user_id,
        f"❓ <b>Вопрос {idx + 1}/{len(words)}</b>\n\nКак переводится: <b>{word}</b>?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def handle_quiz_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    state = quiz_state.get(user_id)
    if not state:
        await callback.answer("Квиз не найден. Дождись вечерней рассылки.", show_alert=True)
        return

    parts = callback.data.split(":")
    is_correct = parts[1] == "1"
    idx = int(parts[2])

    if idx != state["current"]:
        await callback.answer("Этот вопрос уже отвечен.", show_alert=True)
        return

    if is_correct:
        state["score"] += 1
        await callback.answer("✅ Правильно!")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Правильно!</b>",
            parse_mode="HTML",
        )
    else:
        word_data = state["words"][idx]
        await callback.answer("❌ Неверно!")
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ <b>Неверно.</b> Правильный ответ: {word_data['translation']}",
            parse_mode="HTML",
        )

    state["current"] += 1

    bot = callback.bot
    await send_question(bot, user_id)


async def finish_quiz(bot: Bot, user_id: int):
    state = quiz_state.pop(user_id, None)
    if not state:
        return

    score = state["score"]
    total = len(state["words"])

    streak = await save_quiz_result(user_id, score, total)

    emoji = "🎉" if score == total else "💪" if score >= total // 2 else "📖"

    text = (
        f"{emoji} <b>Квиз завершён!</b>\n\n"
        f"Результат: <b>{score}/{total}</b>\n"
        f"🔥 Streak: <b>{streak} дней подряд</b>\n\n"
    )

    if score == total:
        text += "Отлично! Все слова усвоены 🏆"
    elif score >= total // 2:
        text += "Хороший результат! Продолжай в том же духе."
    else:
        text += "Повтори слова командой /words и завтра будет лучше!"

    await bot.send_message(user_id, text, parse_mode="HTML")
