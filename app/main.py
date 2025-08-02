from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.settings import settings
from app.db import Database, User, UserSettings
from app.keyboards import main_keyboard


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("water-bot")


db = Database()


def progress_bar(current: int, goal: int, width: int = 20) -> str:
    goal = max(goal, 1)
    filled = min(width, int(round(current / goal * width)))
    empty = width - filled
    return "█" * filled + "░" * empty


async def ensure_profile(tg_user_id: int) -> tuple[User, UserSettings]:
    user = await db.ensure_user(tg_user_id)
    st = await db.get_settings(user.id)
    if st is None:
        await db.upsert_settings(user.id, daily_goal_ml=settings.daily_goal_default, tz_name=settings.tz)
        st = await db.get_settings(user.id)
        assert st is not None
    return user, st


async def handle_add_amount(msg: Message, amount_ml: int):
    user, st = await ensure_profile(msg.from_user.id)
    await db.add_intake(user.id, amount_ml)
    total = await db.sum_today(user.id, st.timezone)
    bar = progress_bar(total, st.daily_goal_ml)
    pct = min(100, int(round(total * 100 / max(1, st.daily_goal_ml))))
    await msg.answer(
        f"Добавлено: {amount_ml} мл.\n"
        f"Сегодня: {total} / {st.daily_goal_ml} мл ({pct}%)\n"
        f"[{bar}]",
        reply_markup=main_keyboard(),
    )


async def cmd_start(msg: Message):
    await ensure_profile(msg.from_user.id)
    await msg.answer(
        "Привет! Я считаю вашу выпитую воду.\n\n"
        "Быстрые кнопки ниже: выбирайте объем или используйте команду /goal <мл> для цели.\n"
        "Команды: /start, /help, /goal 2000, /stats, /undo",
        reply_markup=main_keyboard(),
    )


async def cmd_help(msg: Message):
    await msg.answer(
        "Как пользоваться:\n"
        "• Жмите на кнопки +100, +200, +300, +500, +1000 — я запишу объем.\n"
        "• /goal 2000 — установить дневную цель (в миллилитрах).\n"
        "• /stats — покажу статистику за сегодня.\n"
        "• Отменить — удалю последнюю запись за сегодня.\n"
        "Все время считается по часовому поясу Europe/Moscow.",
        reply_markup=main_keyboard(),
    )


async def cmd_goal(msg: Message, command: CommandObject):
    user, st = await ensure_profile(msg.from_user.id)
    text = (command.args or "").strip()
    if not re.fullmatch(r"\d{2,5}", text or ""):
        await msg.answer("Укажите цель в миллилитрах, например: /goal 2000", reply_markup=main_keyboard())
        return
    goal = int(text)
    goal = max(200, min(goal, 10000))
    await db.upsert_settings(user.id, daily_goal_ml=goal, tz_name=st.timezone)
    total = await db.sum_today(user.id, st.timezone)
    bar = progress_bar(total, goal)
    pct = min(100, int(round(total * 100 / max(1, goal))))
    await msg.answer(
        f"Новая дневная цель: {goal} мл.\n"
        f"Сегодня: {total} / {goal} мл ({pct}%)\n"
        f"[{bar}]",
        reply_markup=main_keyboard(),
    )


async def cmd_stats(msg: Message):
    user, st = await ensure_profile(msg.from_user.id)
    total = await db.sum_today(user.id, st.timezone)
    last = await db.last_n_today(user.id, st.timezone, n=3)
    bar = progress_bar(total, st.daily_goal_ml)
    pct = min(100, int(round(total * 100 / max(1, st.daily_goal_ml))))
    tail = " · ".join(f"{x} мл" for x in last) if last else "нет записей"
    await msg.answer(
        f"Статистика за сегодня:\n"
        f"Итого: {total} / {st.daily_goal_ml} мл ({pct}%)\n"
        f"[{bar}]\n"
        f"Последние: {tail}",
        reply_markup=main_keyboard(),
    )


async def cmd_undo(msg: Message):
    user, st = await ensure_profile(msg.from_user.id)
    removed = await db.delete_last_today(user.id, st.timezone)
    if removed is None:
        await msg.answer("За сегодня записей нет — нечего отменять.", reply_markup=main_keyboard())
        return
    total = await db.sum_today(user.id, st.timezone)
    bar = progress_bar(total, st.daily_goal_ml)
    pct = min(100, int(round(total * 100 / max(1, st.daily_goal_ml))))
    await msg.answer(
        f"Отменено: {removed} мл.\n"
        f"Сегодня: {total} / {st.daily_goal_ml} мл ({pct}%)\n"
        f"[{bar}]",
        reply_markup=main_keyboard(),
    )


async def on_text(msg: Message):
    text = (msg.text or "").strip()
    if text in {"+100", "+200", "+300", "+500", "+1000"}:
        await handle_add_amount(msg, int(text.replace("+", "")))
    elif text.lower() == "статистика":
        await cmd_stats(msg)
    elif text.lower() == "отменить":
        await cmd_undo(msg)
    else:
        await msg.answer("Не понял команду. Используйте кнопки или /help.", reply_markup=main_keyboard())


async def main():
    # Use DefaultBotProperties for aiogram >= 3.7
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Handlers
    dp.message.register(cmd_start, Command(commands={"start"}))
    dp.message.register(cmd_help, Command(commands={"help"}))
    dp.message.register(cmd_goal, Command(commands={"goal"}))
    dp.message.register(cmd_stats, Command(commands={"stats"}))
    dp.message.register(cmd_undo, Command(commands={"undo"}))
    dp.message.register(on_text, F.text)

    await db.connect()
    logger.info("Starting long polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
