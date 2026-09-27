"""SQLite persistence: requisitions, approval steps and an audit log."""
import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS requisitions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    TEXT UNIQUE,
    file_name     TEXT,
    sender        TEXT,
    subject       TEXT,
    email_text    TEXT,
    raw_email     BLOB,   -- original .eml, needed to retry
    status        TEXT,
    extraction    TEXT,   -- JSON from the LLM
    result        TEXT,   -- JSON from validation (supplier, totals, issues)
    fingerprint   TEXT,
    duplicate_of  INTEGER,
    po_number     TEXT,
    erp_response  TEXT,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    requisition_id INTEGER,
    step_no        INTEGER,
    role           TEXT,
    approver_id    TEXT,
    approver_name  TEXT,
    allowed_ids    TEXT,
    note           TEXT,
    status         TEXT DEFAULT 'pending',
    decided_by     TEXT,
    decided_at     TEXT,
    comment        TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    requisition_id INTEGER,
    ts             TEXT,
    message        TEXT
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _row(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    for key in ("extraction", "result", "erp_response", "allowed_ids"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d


def log(conn, req_id: int, message: str) -> None:
    conn.execute("INSERT INTO events (requisition_id, ts, message) VALUES (?, ?, ?)", (req_id, now(), message))
    conn.commit()


def insert_requisition(conn, **fields) -> int:
    for key in ("extraction", "result"):
        if fields.get(key) is not None:
            fields[key] = json.dumps(fields[key], ensure_ascii=False)
    fields["created_at"] = now()
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO requisitions ({cols}) VALUES ({marks})", list(fields.values()))
    conn.commit()
    return cur.lastrowid


def update_requisition(conn, req_id: int, **fields) -> None:
    for key in ("extraction", "result", "erp_response"):
        if fields.get(key) is not None:
            fields[key] = json.dumps(fields[key], ensure_ascii=False)
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE requisitions SET {sets} WHERE id = ?", [*fields.values(), req_id])
    conn.commit()


def get_requisition(conn, req_id: int) -> Optional[dict]:
    return _row(conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone())


def find_by_message_id(conn, message_id: str) -> Optional[dict]:
    return _row(conn.execute("SELECT * FROM requisitions WHERE message_id = ?", (message_id,)).fetchone())


def find_by_fingerprint(conn, fingerprint: str, exclude_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM requisitions WHERE fingerprint = ? AND id != ? "
        "AND status NOT IN ('REJECTED', 'DUPLICATE') ORDER BY id LIMIT 1",
        (fingerprint, exclude_id),
    ).fetchone()
    return _row(row)


def list_requisitions(conn) -> List[dict]:
    return [_row(r) for r in conn.execute("SELECT * FROM requisitions ORDER BY id").fetchall()]


def insert_approvals(conn, req_id: int, chain: List[dict]) -> None:
    for i, step in enumerate(chain, 1):
        conn.execute(
            "INSERT INTO approvals (requisition_id, step_no, role, approver_id, approver_name, allowed_ids, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (req_id, i, step["role"], step["approver_id"], step["approver_name"],
             json.dumps(step["allowed_ids"]), step["note"]),
        )
    conn.commit()


def get_approvals(conn, req_id: int) -> List[dict]:
    rows = conn.execute("SELECT * FROM approvals WHERE requisition_id = ? ORDER BY step_no", (req_id,)).fetchall()
    return [_row(r) for r in rows]


def decide_approval(conn, approval_id: int, status: str, decided_by: str, comment: str) -> None:
    conn.execute(
        "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, comment = ? WHERE id = ?",
        (status, decided_by, now(), comment, approval_id),
    )
    conn.commit()


def get_events(conn, req_id: int) -> List[dict]:
    rows = conn.execute("SELECT ts, message FROM events WHERE requisition_id = ? ORDER BY id", (req_id,)).fetchall()
    return [dict(r) for r in rows]


def reset(conn) -> None:
    conn.executescript("DELETE FROM requisitions; DELETE FROM approvals; DELETE FROM events;")
    conn.commit()
