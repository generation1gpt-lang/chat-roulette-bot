from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_kb(in_chat: bool = False, searching: bool = False) -> ReplyKeyboardMarkup:
    if in_chat:
        buttons = [
            [KeyboardButton(text="⏭ Следующий"), KeyboardButton(text="🚪 Выйти из чата")]
        ]
    elif searching:
        buttons = [
            [KeyboardButton(text="🛑 Остановить поиск")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="🎲 Найти собеседника")]
        ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def report_kb(reported_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report:{reported_user_id}"),
            InlineKeyboardButton(text="Пропустить", callback_data="report:skip"),
        ]
    ])
