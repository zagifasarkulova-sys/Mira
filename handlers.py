from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.filters import CommandStart

from database import register_user, get_todays_words, get_stats, get_all_used_words, save_words
from claude_api import generate_words
from quiz import handle_quiz_answer, send_quiz
from tts import word_to_voice

router = Router()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Новые слова")],
        [KeyboardButton(text="🔁 Слова на сегодня"), KeyboardButton(text="📊 Статистика")],
    ],
    resize_keyboard=True,
)


def words_text_with_buttons(words: list) -> tuple[str, InlineKeyboardMarkup]:
    text = "📚 <b>Слова на сегодня:</b>\n\n"
    buttons = []
    for i, w in enumerate(words, 1):
        word = w["word"]
        translation = w["translation"]
        example = w["example"]
        text += f"{i}. <b>{word}</b> — {translation}\n"
        text += f"   <i>{example}</i>\n\n"
        buttons.append([
            InlineKeyboardButton(text=f"🔊 {word}", callback_data=f"tts:{word}")
        ])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await register_user(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "👋 Привет! Я помогу учить английские слова уровня B1-B2.\n\n"
        "Нажми <b>📚 Новые слова</b> — получишь 5 слов.\n"
        "Каждый вечер в <b>20:00</b> придёт квиз по словам дня.",
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD,
    )


@router.message(F.text == "📚 Новые слова")
async def btn_new_words(message: Message):
    user_id = message.from_user.id
    await register_user(user_id, message.from_user.username or "")

    existing = await get_todays_words(user_id)
    if existing:
        await message.answer(
            "📖 На сегодня слова уже есть. Нажми <b>🔁 Слова на сегодня</b> чтобы посмотреть.\n\n"
            "Новые слова будут доступны завтра.",
            parse_mode="HTML",
        )
        return

    await message.answer("⏳ Генерирую слова...")

    used = await get_all_used_words(user_id)
    try:
        words = await generate_words(used)
        await save_words(user_id, words)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        return

    text, keyboard = words_text_with_buttons(words)
    text += "⏰ Квиз придёт сегодня в <b>20:00</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "🔁 Слова на сегодня")
async def btn_todays_words(message: Message):
    user_id = message.from_user.id
    await register_user(user_id, message.from_user.username or "")
    words = await get_todays_words(user_id)

    if not words:
        await message.answer(
            "📭 Ты ещё не запрашивал слова сегодня.\nНажми <b>📚 Новые слова</b>",
            parse_mode="HTML",
        )
        return

    text, keyboard = words_text_with_buttons(list(words))
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(F.text == "📊 Статистика")
async def btn_stats(message: Message):
    user_id = message.from_user.id
    await register_user(user_id, message.from_user.username or "")
    stats = await get_stats(user_id)

    streak = stats["streak"]
    total_words = stats["total_words"]
    quizzes = stats["quizzes"]

    total_quizzes = len(quizzes)
    if total_quizzes > 0:
        avg_score = sum(q["score"] / q["total"] for q in quizzes) / total_quizzes * 100
        avg_str = f"{avg_score:.0f}%"
    else:
        avg_str = "—"

    streak_emoji = "🔥" if streak >= 3 else "📅"
    await message.answer(
        "📊 <b>Твой прогресс:</b>\n\n"
        f"{streak_emoji} Streak: <b>{streak} дней подряд</b>\n"
        f"📖 Слов изучено: <b>{total_words}</b>\n"
        f"🧠 Квизов пройдено: <b>{total_quizzes}</b>\n"
        f"✅ Средний результат: <b>{avg_str}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tts:"))
async def handle_tts(callback: CallbackQuery):
    word = callback.data.split(":", 1)[1]
    await callback.answer(f"🔊 {word}")
    try:
        audio = word_to_voice(word)
        await callback.message.answer_voice(
            BufferedInputFile(audio.read(), filename="word.mp3"),
            caption=f"🔊 <b>{word}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.answer(f"❌ Не удалось воспроизвести: {e}")


@router.callback_query(F.data.startswith("quiz:"))
async def quiz_callback(callback: CallbackQuery):
    await handle_quiz_answer(callback)
