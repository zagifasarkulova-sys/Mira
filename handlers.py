import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database import (
    get_user, create_user, update_user,
    get_goals, add_goal, delete_goal,
    get_diary_entries, add_diary_entry,
    get_chat_history, save_message, clear_history,
    add_document, get_documents,
)
from rag import add_text_to_kb, add_pdf_to_kb, search_kb, delete_user_kb
from ai import ask_ai, generate_image, analyze_week_progress
from keyboards import (
    main_menu_kb, goals_kb, diary_type_kb,
    kb_menu_kb, settings_kb, cancel_kb, confirm_kb
)
from states import MentorStates

router = Router()
logger = logging.getLogger(__name__)


def _name(user) -> str:
    return user["user_name"] or user["username"] or "друг"


# ─── ONBOARDING ────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, message.from_user.username or "")
        await message.answer(
            "👋 <b>Привет! Я твой личный ИИ-ментор.</b>\n\n"
            "Я буду знать твои цели, читать твои книги и анализировать твой прогресс.\n\n"
            "Как мне тебя называть?",
            parse_mode="HTML"
        )
        await state.set_state(MentorStates.entering_name)
    else:
        name = _name(user)
        await message.answer(
            f"👋 Рад видеть тебя, <b>{name}</b>!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )


@router.message(MentorStates.entering_name)
async def handle_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await update_user(message.from_user.id, user_name=name)
    await message.answer(
        f"Отлично, <b>{name}</b>! 🎯\n\n"
        "Теперь напиши мне инструкцию — как я должен себя вести?\n\n"
        "<i>Например: «Ты строгий ментор. Критикуй меня если я ленюсь. "
        "Моя цель — запустить стартап за 6 месяцев»</i>\n\n"
        "Или нажми /skip чтобы использовать стандартный промпт.",
        parse_mode="HTML"
    )
    await state.set_state(MentorStates.entering_system_prompt)


@router.message(MentorStates.entering_system_prompt)
async def handle_system_prompt(message: Message, state: FSMContext):
    if message.text.strip() == "/skip":
        prompt = ""
    else:
        prompt = message.text.strip()

    await update_user(message.from_user.id, system_prompt=prompt)
    await state.clear()
    await message.answer(
        "✅ <b>Настроено!</b>\n\n"
        "Теперь добавь свои цели и загрузи документы в базу знаний — "
        "чем больше я о тебе знаю, тем точнее помогаю.\n\n"
        "Используй меню ниже 👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ─── CHAT ──────────────────────────────────────────────────────────────────────

@router.message(F.text == "💬 Спросить ментора")
async def handle_chat_start(message: Message, state: FSMContext):
    await message.answer(
        "💬 <b>Задай любой вопрос.</b>\n"
        "<i>Я отвечу опираясь на твою базу знаний и цели.</i>\n\n"
        "Чтобы выйти — нажми любую кнопку меню.",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(MentorStates.chatting)


@router.message(MentorStates.chatting)
async def handle_chat_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text.strip()

    # Выход из чата по кнопкам меню
    menu_buttons = {"🎨 Создать изображение", "🎯 Мои цели", "📓 Дневник",
                    "📚 База знаний", "📊 Анализ недели", "⚙️ Настройки"}
    if user_text in menu_buttons:
        await state.clear()
        await message.answer("Вышел из чата.", reply_markup=main_menu_kb())
        return

    thinking = await message.answer("🤔 <i>Думаю...</i>", parse_mode="HTML")

    user = await get_user(user_id)
    history = await get_chat_history(user_id)
    context = await search_kb(user_id, user_text)

    history_dicts = [{"role": r["role"], "content": r["content"]} for r in history]

    response = await ask_ai(
        user_id=user_id,
        user_message=user_text,
        history=history_dicts,
        context=context,
        system_prompt=user["system_prompt"] if user else "",
    )

    await save_message(user_id, "user", user_text)
    await save_message(user_id, "assistant", response)

    await thinking.delete()
    await message.answer(response, parse_mode="HTML")


# ─── IMAGE GENERATION ──────────────────────────────────────────────────────────

@router.message(F.text == "🎨 Создать изображение")
async def handle_image_start(message: Message, state: FSMContext):
    await message.answer(
        "🎨 <b>Опиши что хочешь создать:</b>\n\n"
        "<i>Например: «закат над горами в стиле аниме» или "
        "«продуктивный рабочий стол с кофе»</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(MentorStates.entering_image_prompt)


@router.message(MentorStates.entering_image_prompt)
async def handle_image_prompt(message: Message, state: FSMContext):
    prompt = message.text.strip()
    await state.clear()

    generating = await message.answer(
        "🎨 <i>Генерирую изображение... это займёт 20-40 секунд</i>",
        parse_mode="HTML"
    )

    image_url = await generate_image(prompt)

    await generating.delete()

    if image_url:
        async with __import__("httpx").AsyncClient() as client:
            resp = await client.get(image_url)
            img_bytes = resp.content

        await message.answer_photo(
            BufferedInputFile(img_bytes, filename="image.jpg"),
            caption=f"🎨 <i>{prompt}</i>",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer(
            "⚠️ Не удалось сгенерировать изображение.\n"
            "Проверь REPLICATE_API_TOKEN в настройках Render.",
            reply_markup=main_menu_kb()
        )


# ─── GOALS ─────────────────────────────────────────────────────────────────────

@router.message(F.text == "🎯 Мои цели")
async def handle_goals(message: Message):
    goals = await get_goals(message.from_user.id)
    if goals:
        text = "🎯 <b>Твои цели:</b>"
    else:
        text = "🎯 <b>Целей пока нет.</b>\nДобавь первую!"

    await message.answer(text, reply_markup=goals_kb(goals), parse_mode="HTML")


@router.callback_query(F.data == "goal_add")
async def cb_goal_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "✍️ Напиши свою цель:\n\n"
        "<i>Например: «Выучить английский до B2 к декабрю»</i>",
        parse_mode="HTML"
    )
    await state.set_state(MentorStates.adding_goal)


@router.message(MentorStates.adding_goal)
async def handle_add_goal(message: Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    await add_goal(user_id, text)
    # Добавляем цель и в базу знаний
    await add_text_to_kb(user_id, f"Цель пользователя: {text}", source="goals")
    await state.clear()
    goals = await get_goals(user_id)
    await message.answer(
        f"✅ <b>Цель добавлена!</b>\n\n<i>{text}</i>",
        reply_markup=goals_kb(goals),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("goal_del_"))
async def cb_goal_delete(callback: CallbackQuery):
    goal_id = int(callback.data.replace("goal_del_", ""))
    await delete_goal(goal_id, callback.from_user.id)
    goals = await get_goals(callback.from_user.id)
    await callback.message.edit_text(
        "🎯 <b>Твои цели:</b>" if goals else "🎯 Целей пока нет.",
        reply_markup=goals_kb(goals),
        parse_mode="HTML"
    )
    await callback.answer("Цель удалена")


# ─── DIARY ─────────────────────────────────────────────────────────────────────

@router.message(F.text == "📓 Дневник")
async def handle_diary(message: Message):
    entries = await get_diary_entries(message.from_user.id, limit=5)
    if entries:
        lines = []
        for e in entries:
            icon = {"success": "✅", "mistake": "❌", "note": "📝"}.get(e["entry_type"], "📝")
            date = e["created_at"].strftime("%d.%m")
            lines.append(f"{icon} <i>{date}</i>: {e['text'][:80]}...")
        text = "📓 <b>Последние записи:</b>\n\n" + "\n".join(lines)
    else:
        text = "📓 <b>Дневник пуст.</b>\nДобавь первую запись!"

    await message.answer(
        text + "\n\nЧто добавим?",
        reply_markup=diary_type_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("diary_"))
async def cb_diary_type(callback: CallbackQuery, state: FSMContext):
    entry_type = callback.data.replace("diary_", "")
    type_names = {"success": "успех", "mistake": "ошибку", "note": "заметку"}
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        f"✍️ Напиши свой {type_names.get(entry_type, 'запись')}:"
    )
    await state.update_data(diary_type=entry_type)
    await state.set_state(MentorStates.adding_diary)


@router.message(MentorStates.adding_diary)
async def handle_add_diary(message: Message, state: FSMContext):
    data = await state.get_data()
    entry_type = data.get("diary_type", "note")
    text = message.text.strip()
    user_id = message.from_user.id

    await add_diary_entry(user_id, entry_type, text)
    # Добавляем в базу знаний
    await add_text_to_kb(
        user_id,
        f"Запись в дневнике [{entry_type}]: {text}",
        source="diary"
    )
    await state.clear()

    icon = {"success": "✅", "mistake": "❌", "note": "📝"}.get(entry_type, "📝")
    await message.answer(
        f"{icon} <b>Записано в дневник.</b>\n\n<i>{text}</i>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ─── KNOWLEDGE BASE ────────────────────────────────────────────────────────────

@router.message(F.text == "📚 База знаний")
async def handle_kb(message: Message):
    docs = await get_documents(message.from_user.id)
    if docs:
        lines = [f"📄 {d['filename']} ({d['chunk_count']} фрагментов)" for d in docs]
        text = "📚 <b>Загруженные документы:</b>\n\n" + "\n".join(lines)
    else:
        text = "📚 <b>База знаний пуста.</b>\nЗагрузи PDF или добавь текст вручную."

    await message.answer(text, reply_markup=kb_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "kb_pdf")
async def cb_kb_pdf(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "📄 <b>Отправь PDF файл</b>\n\n"
        "<i>Книга, статья, конспект — всё что хочешь чтобы я знал.</i>",
        parse_mode="HTML"
    )


@router.message(F.document)
async def handle_pdf_upload(message: Message):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await message.answer("⚠️ Поддерживаются только PDF файлы.")
        return

    processing = await message.answer("⏳ <i>Обрабатываю PDF...</i>", parse_mode="HTML")

    file = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    pdf_bytes = file_bytes.read()

    chunk_count = await add_pdf_to_kb(message.from_user.id, pdf_bytes, doc.file_name)

    if chunk_count > 0:
        await add_document(message.from_user.id, doc.file_name, chunk_count)
        await processing.delete()
        await message.answer(
            f"✅ <b>PDF добавлен в базу знаний!</b>\n\n"
            f"📄 {doc.file_name}\n"
            f"🔍 Создано {chunk_count} фрагментов для поиска.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await processing.delete()
        await message.answer(
            "⚠️ Не удалось обработать PDF. Попробуй другой файл.",
            reply_markup=main_menu_kb()
        )


@router.callback_query(F.data == "kb_text")
async def cb_kb_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "✍️ <b>Напиши текст для добавления в базу знаний:</b>\n\n"
        "<i>Это могут быть твои планы, заметки, идеи — всё что хочешь "
        "чтобы я мог использовать в ответах.</i>",
        parse_mode="HTML"
    )
    await state.set_state(MentorStates.adding_text_kb)


@router.message(MentorStates.adding_text_kb)
async def handle_add_text_kb(message: Message, state: FSMContext):
    text = message.text.strip()
    chunk_count = await add_text_to_kb(message.from_user.id, text, source="manual_text")
    await add_document(message.from_user.id, "Текст вручную", chunk_count)
    await state.clear()
    await message.answer(
        f"✅ <b>Текст добавлен в базу знаний!</b>\n"
        f"🔍 Создано {chunk_count} фрагментов.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "kb_clear")
async def cb_kb_clear(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "⚠️ Очистить всю базу знаний? Это удалит все PDF и тексты.",
        reply_markup=confirm_kb("kb_clear")
    )


@router.callback_query(F.data == "confirm_kb_clear")
async def cb_confirm_kb_clear(callback: CallbackQuery):
    await delete_user_kb(callback.from_user.id)
    await callback.message.edit_text("✅ База знаний очищена.")
    await callback.message.answer("Используй меню:", reply_markup=main_menu_kb())


# ─── WEEKLY ANALYSIS ───────────────────────────────────────────────────────────

@router.message(F.text == "📊 Анализ недели")
async def handle_week_analysis(message: Message):
    thinking = await message.answer("📊 <i>Анализирую твою неделю...</i>", parse_mode="HTML")

    user = await get_user(message.from_user.id)
    goals = await get_goals(message.from_user.id)
    diary = await get_diary_entries(message.from_user.id, limit=30)

    analysis = await analyze_week_progress(
        goals=list(goals),
        diary_entries=list(diary),
        system_prompt=user["system_prompt"] if user else "",
    )

    await thinking.delete()
    await message.answer(
        f"📊 <b>Анализ недели</b>\n\n{analysis}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── SETTINGS ──────────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Настройки")
async def handle_settings(message: Message):
    user = await get_user(message.from_user.id)
    name = _name(user)
    prompt_preview = (user["system_prompt"][:80] + "...") if user and len(user["system_prompt"]) > 80 else (user["system_prompt"] if user else "стандартный")
    prompt_display = prompt_preview or "стандартный"

    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"🤖 Промпт: <i>{prompt_display}</i>",
        reply_markup=settings_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_name")
async def cb_settings_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("👤 Введи новое имя:")
    await state.set_state(MentorStates.entering_name)


@router.callback_query(F.data == "settings_prompt")
async def cb_settings_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "🤖 <b>Напиши новый системный промпт:</b>\n\n"
        "<i>Это инструкция для ИИ — как себя вести, на чём фокусироваться, "
        "каким тоном отвечать.</i>\n\n"
        "Напиши /skip для стандартного промпта.",
        parse_mode="HTML"
    )
    await state.set_state(MentorStates.editing_system_prompt)


@router.message(MentorStates.editing_system_prompt)
async def handle_edit_prompt(message: Message, state: FSMContext):
    prompt = "" if message.text.strip() == "/skip" else message.text.strip()
    await update_user(message.from_user.id, system_prompt=prompt)
    await state.clear()
    await message.answer(
        "✅ <b>Системный промпт обновлён!</b>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_clear_history")
async def cb_clear_history(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "⚠️ Очистить историю чата?",
        reply_markup=confirm_kb("clear_history")
    )


@router.callback_query(F.data == "confirm_clear_history")
async def cb_confirm_clear_history(callback: CallbackQuery):
    await clear_history(callback.from_user.id)
    await callback.message.edit_text("✅ История чата очищена.")


# ─── CANCEL ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup()
    await callback.message.answer("Отменено.", reply_markup=main_menu_kb())
