import sqlite3
import logging
from datetime import datetime, date
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """إنشاء الجداول."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT    DEFAULT '',
                    full_name   TEXT    DEFAULT '',
                    downloads   INTEGER DEFAULT 0,
                    joined_date TEXT    DEFAULT (DATE('now')),
                    is_blocked  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS downloads_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER,
                    url         TEXT,
                    platform    TEXT,
                    file_size   REAL,
                    downloaded_at TEXT DEFAULT (DATETIME('now'))
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id  TEXT    UNIQUE,
                    name        TEXT,
                    invite_link TEXT    DEFAULT '',
                    added_at    TEXT    DEFAULT (DATETIME('now'))
                );
            """)
        logger.info("✅ قاعدة البيانات جاهزة")

    # ─── المستخدمون ───────────────────────────────────────

    def add_user(self, user_id: int, username: str, full_name: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username  = excluded.username,
                    full_name = excluded.full_name
                """,
                (user_id, username, full_name),
            )

    def get_all_users(self) -> list[int]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id FROM users WHERE is_blocked = 0"
            ).fetchall()
        return [r["user_id"] for r in rows]

    def increment_downloads(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET downloads = downloads + 1 WHERE user_id = ?",
                (user_id,),
            )

    def get_user_stats(self, user_id: int) -> dict:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT downloads, joined_date FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row:
            return {"downloads": row["downloads"], "joined_date": row["joined_date"]}
        return {"downloads": 0, "joined_date": "غير معروف"}

    def block_user(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,)
            )

    def unblock_user(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,)
            )

    # ─── سجل التحميلات ────────────────────────────────────

    def log_download(self, user_id: int, url: str, platform: str, file_size: float):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO downloads_log (user_id, url, platform, file_size)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, url, platform, file_size),
            )

    # ─── القنوات ──────────────────────────────────────────

    def add_channel(self, channel_id: str, name: str, invite_link: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO channels (channel_id, name, invite_link)
                VALUES (?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    name        = excluded.name,
                    invite_link = excluded.invite_link
                """,
                (channel_id, name, invite_link),
            )

    def remove_channel(self, channel_id: str):
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM channels WHERE channel_id = ?", (channel_id,)
            )

    def get_channels(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT channel_id, name, invite_link FROM channels"
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── الإحصائيات ───────────────────────────────────────

    def get_stats(self) -> dict:
        today = date.today().isoformat()
        with self._get_conn() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_downloads = conn.execute(
                "SELECT COALESCE(SUM(downloads), 0) FROM users"
            ).fetchone()[0]
            today_downloads = conn.execute(
                "SELECT COUNT(*) FROM downloads_log WHERE DATE(downloaded_at) = ?",
                (today,),
            ).fetchone()[0]
            total_channels = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "today_downloads": today_downloads,
            "total_channels": total_channels,
        }

    def get_platform_stats(self) -> dict:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT platform, COUNT(*) as cnt
                FROM downloads_log
                GROUP BY platform
                ORDER BY cnt DESC
                """
            ).fetchall()
        return {r["platform"]: r["cnt"] for r in rows}
