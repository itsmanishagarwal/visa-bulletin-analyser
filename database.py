import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "visa_bulletin.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bulletins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bulletin_month TEXT UNIQUE NOT NULL,
            fetched_at TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS priority_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bulletin_id INTEGER NOT NULL,
            table_type TEXT NOT NULL,
            visa_type TEXT NOT NULL,
            category TEXT NOT NULL,
            country TEXT NOT NULL,
            priority_date TEXT NOT NULL,
            FOREIGN KEY (bulletin_id) REFERENCES bulletins(id)
        );

        CREATE INDEX IF NOT EXISTS idx_priority_dates_bulletin
            ON priority_dates(bulletin_id);
        CREATE INDEX IF NOT EXISTS idx_priority_dates_lookup
            ON priority_dates(category, country, table_type, visa_type);
    """)
    conn.close()


def bulletin_exists(month_str):
    """Check if a bulletin month (YYYY-MM) is already stored."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM bulletins WHERE bulletin_month = ?", (month_str,)
    ).fetchone()
    conn.close()
    return row is not None


def save_bulletin(month_str, records):
    """Insert bulletin + priority date rows in a transaction.

    records: list of dicts with keys: table_type, visa_type, category, country, priority_date
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO bulletins (bulletin_month, fetched_at) VALUES (?, ?)",
            (month_str, datetime.utcnow().isoformat()),
        )
        bulletin_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO priority_dates
               (bulletin_id, table_type, visa_type, category, country, priority_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    bulletin_id,
                    r["table_type"],
                    r["visa_type"],
                    r["category"],
                    r["country"],
                    r["priority_date"],
                )
                for r in records
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_available_months():
    """List all stored bulletin months, most recent first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT bulletin_month FROM bulletins ORDER BY bulletin_month DESC"
    ).fetchall()
    conn.close()
    return [r["bulletin_month"] for r in rows]


def get_dates_for_month(month_str):
    """Return all priority date records for a bulletin month."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT pd.table_type, pd.visa_type, pd.category, pd.country, pd.priority_date
           FROM priority_dates pd
           JOIN bulletins b ON pd.bulletin_id = b.id
           WHERE b.bulletin_month = ?""",
        (month_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trend_data(category, country, table_type, visa_type):
    """Return time series of dates for charting, ordered by bulletin month."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT b.bulletin_month, pd.priority_date
           FROM priority_dates pd
           JOIN bulletins b ON pd.bulletin_id = b.id
           WHERE pd.category = ? AND pd.country = ?
             AND pd.table_type = ? AND pd.visa_type = ?
           ORDER BY b.bulletin_month ASC""",
        (category, country, table_type, visa_type),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_bulletin_month():
    """Return the most recent stored bulletin month, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT bulletin_month FROM bulletins ORDER BY bulletin_month DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["bulletin_month"] if row else None


def get_all_categories(visa_type=None):
    """Return distinct categories, optionally filtered by visa_type."""
    conn = get_connection()
    if visa_type:
        rows = conn.execute(
            "SELECT DISTINCT category FROM priority_dates WHERE visa_type = ? ORDER BY category",
            (visa_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT category FROM priority_dates ORDER BY category"
        ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_all_countries():
    """Return distinct countries."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT country FROM priority_dates ORDER BY country"
    ).fetchall()
    conn.close()
    return [r["country"] for r in rows]
