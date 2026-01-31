import json
from datetime import datetime

from app.db.conn import get_connection
from app.domain.states import ConversationState


def get_session(phone: str) -> tuple[str, dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT state, data FROM sessions WHERE phone = ?", (phone,))
        row = cur.fetchone()
        if not row:
            return ConversationState.NEW, {}
        state = row["state"]
        data = json.loads(row["data"]) if row["data"] else {}
        return state, data
    finally:
        conn.close()


def upsert_session(phone: str, state: str, data: dict) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        data_json = json.dumps(data or {}, ensure_ascii=False)

        cur.execute(
            """
            INSERT INTO sessions (phone, state, data, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
              state = excluded.state,
              data = excluded.data,
              updated_at = excluded.updated_at
            """,
            (phone, state, data_json, now),
        )
        conn.commit()
    finally:
        conn.close()


def reset_session(phone: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE phone = ?", (phone,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
