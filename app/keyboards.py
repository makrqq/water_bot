from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard() -> ReplyKeyboardMarkup:
    # Большие удобные кнопки быстрых добавлений
    rows = [
        [KeyboardButton(text="+100"), KeyboardButton(text="+200"), KeyboardButton(text="+300")],
        [KeyboardButton(text="+500"), KeyboardButton(text="+1000")],
        [KeyboardButton(text="Статистика"), KeyboardButton(text="Отменить")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите количество или команду",
        one_time_keyboard=False,
        selective=False,
    )