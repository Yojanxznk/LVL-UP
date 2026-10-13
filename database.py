# database.py
import os
import sqlite3
from datetime import datetime, timedelta

# Prioridad:
# 1. Variable de entorno DB_PATH (Railway, Docker, etc.)
# 2. /data/ffbot.db (volumen persistente en Railway)
# 3. Mismo directorio del script (Termux/local)
DB_PATH = os.environ.get("DB_PATH")

if not DB_PATH:
    if os.path.isdir("/data"):
        DB_PATH = "/data/ffbot.db"
    else:
        _HERE = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(_HERE, "ffbot.db")

# Asegurar que el directorio existe
try:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
except Exception:
    pass


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            password TEXT,
            region TEXT,
            account_id TEXT,
            nickname TEXT,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            status TEXT DEFAULT 'offline',
            matches_played INTEGER DEFAULT 0,
            matches_won INTEGER DEFAULT 0,
            max_matches INTEGER DEFAULT 0,
            bot_enabled INTEGER DEFAULT 0,
            last_match_at TEXT,
            last_seen TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_uid TEXT,
            level TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_uid TEXT,
            match_index INTEGER,
            server TEXT,
            started_at TEXT,
            ended_at TEXT,
            status TEXT,
            duration INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS exp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_uid TEXT,
            exp INTEGER,
            timestamp TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_exp_history_uid_ts ON exp_history (account_uid, id DESC)")
    for col, definition in [
        ("max_matches", "INTEGER DEFAULT 0"),
        ("bot_enabled", "INTEGER DEFAULT 0"),
    ]:
        try:
            c.execute(f"ALTER TABLE accounts ADD COLUMN {col} {definition}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def add_log(account_uid, level, message):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO logs (account_uid, level, message, timestamp) VALUES (?, ?, ?, ?)",
            (str(account_uid), level, message, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def update_account_status(uid, status):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE accounts SET status=?, last_seen=? WHERE uid=?",
            (status, datetime.now().isoformat(), str(uid))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def update_account_profile(uid, account_id=None, nickname=None, level=None, exp=None, region=None):
    try:
        conn = get_conn()
        fields, values = [], []
        if account_id is not None:
            fields.append("account_id=?"); values.append(str(account_id))
        if nickname is not None:
            fields.append("nickname=?"); values.append(nickname)
        if level is not None:
            fields.append("level=?"); values.append(int(level))
        if exp is not None:
            fields.append("exp=?"); values.append(int(exp))
        if region is not None:
            fields.append("region=?"); values.append(region)
        fields.append("last_seen=?"); values.append(datetime.now().isoformat())
        values.append(str(uid))
        sql = f"UPDATE accounts SET {', '.join(fields)} WHERE uid=?"
        conn.execute(sql, values)
        conn.commit()
        conn.close()
    except Exception:
        pass


def increment_matches(uid, won=False):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE accounts SET matches_played = matches_played + 1, "
            "matches_won = matches_won + ?, last_match_at=? WHERE uid=?",
            (1 if won else 0, datetime.now().isoformat(), str(uid))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def start_match(uid, match_index, server):
    try:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO matches (account_uid, match_index, server, started_at, status) "
            "VALUES (?, ?, ?, ?, 'playing')",
            (str(uid), match_index, server, datetime.now().isoformat())
        )
        conn.commit()
        mid = cur.lastrowid
        conn.close()
        return mid
    except Exception:
        return None


def end_match(match_id, status='finished'):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE matches SET ended_at=?, status=? WHERE id=?",
            (datetime.now().isoformat(), status, match_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_all_accounts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_by_uid(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM accounts WHERE uid=?", (str(uid),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_logs(limit=200, uid=None):
    conn = get_conn()
    if uid:
        rows = conn.execute(
            "SELECT * FROM logs WHERE account_uid=? ORDER BY id DESC LIMIT ?",
            (str(uid), limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"]
    online = conn.execute("SELECT COUNT(*) c FROM accounts WHERE status='online'").fetchone()["c"]
    playing = conn.execute("SELECT COUNT(*) c FROM accounts WHERE status='playing'").fetchone()["c"]
    total_matches = conn.execute("SELECT COALESCE(SUM(matches_played),0) c FROM accounts").fetchone()["c"]
    avg_level = conn.execute("SELECT COALESCE(AVG(level),0) c FROM accounts").fetchone()["c"]
    conn.close()
    return {
        "total_accounts": total,
        "online": online,
        "playing": playing,
        "total_matches": total_matches,
        "avg_level": round(avg_level, 2)
    }


def update_max_matches(uid, max_matches):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE accounts SET max_matches=? WHERE uid=?",
            (int(max_matches), str(uid))
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def set_bot_enabled(uid, enabled):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE accounts SET bot_enabled=? WHERE uid=?",
            (1 if enabled else 0, str(uid))
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ------------------------- EXP 24H -------------------------

def init_exp_history():
    try:
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_uid TEXT,
                exp INTEGER,
                timestamp TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_history_uid_ts ON exp_history (account_uid, id DESC)")
        conn.commit()
        conn.close()
    except Exception:
        pass


def register_exp_snapshot(uid: str, exp: int):
    """Guarda un snapshot de EXP y limpia registros con más de 48h."""
    try:
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_uid TEXT,
                exp INTEGER,
                timestamp TEXT
            )
        """)
        conn.execute(
            "INSERT INTO exp_history (account_uid, exp, timestamp) VALUES (?, ?, ?)",
            (str(uid), int(exp), datetime.now().isoformat())
        )
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
        conn.execute("DELETE FROM exp_history WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_exp_last_24h(uid: str) -> int:
    """Devuelve la EXP ganada en las últimas 24 horas para un UID."""
    try:
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_uid TEXT,
                exp INTEGER,
                timestamp TEXT
            )
        """)
        now = datetime.now()
        cutoff_24h = (now - timedelta(hours=24)).isoformat()

        latest = conn.execute(
            "SELECT exp FROM exp_history WHERE account_uid=? ORDER BY id DESC LIMIT 1",
            (str(uid),)
        ).fetchone()

        baseline = conn.execute(
            "SELECT exp FROM exp_history WHERE account_uid=? AND timestamp >= ? ORDER BY id ASC LIMIT 1",
            (str(uid), cutoff_24h)
        ).fetchone()
        if not baseline:
            baseline = conn.execute(
                "SELECT exp FROM exp_history WHERE account_uid=? ORDER BY id ASC LIMIT 1",
                (str(uid),)
            ).fetchone()

        conn.close()
        if not latest or not baseline:
            return 0
        diff = int(latest["exp"]) - int(baseline["exp"])
        return max(0, diff)
    except Exception:
        return 0


def get_all_exp_last_24h() -> dict:
    """Devuelve {uid: exp_24h} para todas las cuentas."""
    try:
        conn = get_conn()
        uids = [r["uid"] for r in conn.execute("SELECT uid FROM accounts").fetchall()]
        conn.close()
        return {uid: get_exp_last_24h(uid) for uid in uids}
    except Exception:
        return {}
