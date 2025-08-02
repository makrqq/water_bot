from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    daily_goal_default: int
    tz: str

    @staticmethod
    def load() -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Не задан BOT_TOKEN в переменных окружения")
        daily_goal = int(os.getenv("DAILY_GOAL_DEFAULT", "2000"))
        tz = os.getenv("TZ", "Europe/Moscow")
        return Settings(bot_token=token, daily_goal_default=daily_goal, tz=tz)


settings = Settings.load()