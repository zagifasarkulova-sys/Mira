from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Спросить ментора"), KeyboardButton(text="🎨 Создать изображение")],
            [KeyboardButton(text="🎯 Мои цели"), KeyboardButton(text="📓 Дневник")],
            [KeyboardButton(text="📚 База знаний"), KeyboardButton(text="📊 Анализ недели")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        persistent=True
    )


def goals_kb(goals: list) -> InlineKeyboardMarkup:
    buttons = []
    for g in goals:
        short = g["text"][:35] + "..." if len(g["text"]) > 35 else g["text"]
        buttons.append([
            InlineKeyboardButton(text=f"🎯 {short}", callback_data=f"goal_view_{g['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"goal_del_{g['id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить цель", callback_data="goal_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def diary_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Успех", callback_data="diary_success"),
            InlineKeyboardButton(text="❌ Ошибка", callback_data="diary_mistake"),
            InlineKeyboardButton(text="📝 Заметка", callback_data="diary_note"),
        ]
    ])


def kb_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Загрузить PDF", callback_data="kb_pdf")],
        [InlineKeyboardButton(text="✍️ Добавить текст вручную", callback_data="kb_text")],
        [InlineKeyboardButton(text="🗑 Очистить базу знаний", callback_data="kb_clear")],
    ])


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Изменить имя", callback_data="settings_name")],
        [InlineKeyboardButton(text="🤖 Системный промпт", callback_data="settings_prompt")],
        [InlineKeyboardButton(text="🗑 Очистить историю чата", callback_data="settings_clear_history")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel"),
        ]
    ])
