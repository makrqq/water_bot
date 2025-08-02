from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from typing import Optional, Tuple, List
from datetime import datetime, timezone, timedelta
import zoneinfo


DB_PATH = "data/water.sqlite3"


CREATE_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL UNIQUE,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    daily_goal_ml INTEGER NOT NULL,
    timezone TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id);

CREATE TABLE IF NOT EXISTS water_intake (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount_ml INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_water_user_time ON water_intake(user_id, created_at_utc);
"""


@dataclass
class User:
    id: int
    tg_user_id: int
    created_at_utc: str


@dataclass
class UserSettings:
    user_id: int
    daily_goal_ml: int
    timezone: str
    updated_at_utc: str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def msk_day_bounds(dt_utc: datetime, tz_name: str) -> Tuple[datetime, datetime]:
    """
    Convert dt_utc into local day bounds [start, end) for provided timezone.
    """
    tz = zoneinfo.ZoneInfo(tz_name)
    local = dt_utc.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    # convert back to UTC bounds
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.executescript(CREATE_SQL)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "DB not connected"
        return self._conn

    # Users

    async def ensure_user(self, tg_user_id: int) -> User:
        cur = await self.conn.execute(
            "SELECT id, tg_user_id, created_at_utc FROM users WHERE tg_user_id = ?",
            (tg_user_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        if row:
            return User(id=row[0], tg_user_id=row[1], created_at_utc=row[2])

        now = _utcnow_iso()
        cur = await self.conn.execute(
            "INSERT INTO users (tg_user_id, created_at_utc) VALUES (?, ?)",
            (tg_user_id, now),
        )
        await self.conn.commit()
        user_id = cur.lastrowid
        return User(id=user_id, tg_user_id=tg_user_id, created_at_utc=now)

    async def get_user_by_tg(self, tg_user_id: int) -> Optional[User]:
        cur = await self.conn.execute(
            "SELECT id, tg_user_id, created_at_utc FROM users WHERE tg_user_id = ?",
            (tg_user_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return None
        return User(id=row[0], tg_user_id=row[1], created_at_utc=row[2])

    # Settings

    async def get_settings(self, user_id: int) -> Optional[UserSettings]:
        cur = await self.conn.execute(
            "SELECT user_id, daily_goal_ml, timezone, updated_at_utc FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return None
        return UserSettings(
            user_id=row[0],
            daily_goal_ml=row[1],
            timezone=row[2],
            updated_at_utc=row[3],
        )

    async def upsert_settings(self, user_id: int, daily_goal_ml: int, tz_name: str):
        now = _utcnow_iso()
        cur = await self.conn.execute(
            """
            INSERT INTO user_settings (user_id, daily_goal_ml, timezone, updated_at_utc)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET daily_goal_ml=excluded.daily_goal_ml,
                          timezone=excluded.timezone,
                          updated_at_utc=excluded.updated_at_utc
            """,
            (user_id, daily_goal_ml, tz_name, now),
        )
        await self.conn.commit()
        await cur.close()

    # Water intake

    async def add_intake(self, user_id: int, amount_ml: int):
        now = _utcnow_iso()
        cur = await self.conn.execute(
            "INSERT INTO water_intake (user_id, amount_ml, created_at_utc) VALUES (?, ?, ?)",
            (user_id, amount_ml, now),
        )
        await self.conn.commit()
        await cur.close()

    async def delete_last_today(self, user_id: int, tz_name: str) -> Optional[int]:
        """
        Delete last intake for today (local day) and return amount_ml deleted.
        """
        now_utc = datetime.now(timezone.utc)
        start_utc, end_utc = msk_day_bounds(now_utc, tz_name)
        cur = await self.conn.execute(
            """
            SELECT id, amount_ml FROM water_intake
            WHERE user_id = ? AND created_at_utc >= ? AND created_at_utc < ?
            ORDER BY created_at_utc DESC, id DESC
            LIMIT 1
            """,
            (user_id, start_utc.isoformat(), end_utc.isoformat()),
        )
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return None
        wid, amount = row[0], row[1]
        await self.conn.execute("DELETE FROM water_intake WHERE id = ?", (wid,))
        await self.conn.commit()
        return amount

    async def sum_today(self, user_id: int, tz_name: str) -> int:
        now_utc = datetime.now(timezone.utc)
        start_utc, end_utc = msk_day_bounds(now_utc, tz_name)
        cur = await self.conn.execute(
            """
            SELECT COALESCE(SUM(amount_ml), 0) FROM water_intake
            WHERE user_id = ? AND created_at_utc >= ? AND created_at_utc < ?
            """,
            (user_id, start_utc.isoformat(), end_utc.isoformat()),
        )
        row = await cur.fetchone()
        await cur.close()
        return int(row[0] or 0)

    async def last_n_today(self, user_id: int, tz_name: str, n: int = 3) -> List[int]:
        now_utc = datetime.now(timezone.utc)
        start_utc, end_utc = msk_day_bounds(now_utc, tz_name)
        cur = await self.conn.execute(
            """
            SELECT amount_ml FROM water_intake
            WHERE user_id = ? AND created_at_utc >= ? AND created_at_utc < ?
            ORDER BY created_at_utc DESC, id DESC
            LIMIT ?
            """,
            (user_id, start_utc.isoformat(), end_utc.isoformat(), n),
        )
        rows = await cur.fetchall()
        await cur.close()
        return [int(r[0]) for r in rows]