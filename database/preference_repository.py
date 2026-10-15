import sqlite3

from config.settings import Settings


class PreferenceRepository:
    """Small choices the page remembers between sessions.

    A session ends on every reload, and with it everything
    in session state: the selected repository went back to
    the first one each time. Key and value, both text.
    """

    def __init__(
        self,
        db_name: str = Settings.DATABASE_NAME,
    ) -> None:

        self.connection = sqlite3.connect(
            db_name,
            check_same_thread=False,
            timeout=30,
        )

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
            """
        )

        self.connection.commit()

    def get(self, key: str, default: str = "") -> str:

        row = self.connection.execute(
            "SELECT value FROM preferences WHERE key = ?",
            (key,),
        ).fetchone()

        return row[0] if row else default

    def set(self, key: str, value: str) -> None:

        self.connection.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value),
        )

        self.connection.commit()
