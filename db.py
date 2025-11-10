import sqlite3
import json
import time
from typing import Any
from contextlib import contextmanager

DB_PATH = "votebot.db"


def get_connection():
    """Get a database connection.

    Creates a new connection each time to avoid threading issues.
    SQLite connections are lightweight enough for this approach.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction():
    """Context manager for database transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS elections (
            election_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            method_class TEXT NOT NULL,
            method_params TEXT NOT NULL,
            candidates TEXT NOT NULL,
            open INTEGER NOT NULL,
            message_id INTEGER,
            UNIQUE(channel_id, title)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ballots (
            ballot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ballot_type TEXT NOT NULL,
            ballot_data TEXT NOT NULL,
            is_submitted INTEGER NOT NULL,
            UNIQUE(election_id, user_id, is_submitted),
            FOREIGN KEY (election_id) REFERENCES elections(election_id) ON DELETE CASCADE
        )
    """)

    # Create indices for better query performance
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_elections_channel_title
        ON elections(channel_id, title)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ballots_election_user
        ON ballots(election_id, user_id, is_submitted)
    """)

    conn.commit()
    conn.close()


def save_election(election: Any) -> int:
    """Save an election to the database. Returns election_id."""
    conn = get_connection()

    try:
        data = (
            election.channel_id,
            election.title,
            election.description,
            election.method_class,
            json.dumps(election.method_params),
            json.dumps(election.candidates),
            1 if election.open else 0,
            election.message_id,
        )

        if election.election_id is None:
            # Insert new election
            cursor = conn.execute(
                """
                INSERT INTO elections (channel_id, title, description, method_class,
                                     method_params, candidates, open, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )
            conn.commit()
            election.election_id = cursor.lastrowid
            return cursor.lastrowid
        else:
            # Update existing election
            conn.execute(
                """
                UPDATE elections
                SET channel_id=?, title=?, description=?, method_class=?,
                    method_params=?, candidates=?, open=?, message_id=?
                WHERE election_id=?
                """,
                data + (election.election_id,),
            )
            conn.commit()
            return election.election_id
    finally:
        conn.close()


def load_election(election_id: int) -> dict[str, Any] | None:
    """Load election data by ID. Returns dict of election data or None."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM elections WHERE election_id=?", (election_id,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "election_id": row["election_id"],
            "channel_id": row["channel_id"],
            "title": row["title"],
            "description": row["description"],
            "method_class": row["method_class"],
            "method_params": json.loads(row["method_params"]),
            "candidates": json.loads(row["candidates"]),
            "open": bool(row["open"]),
            "message_id": row["message_id"],
        }
    finally:
        conn.close()


def load_election_by_natural_key(channel_id: int, title: str) -> dict[str, Any] | None:
    """Load election data by channel_id and title. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM elections WHERE channel_id=? AND title=?", (channel_id, title)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "election_id": row["election_id"],
            "channel_id": row["channel_id"],
            "title": row["title"],
            "description": row["description"],
            "method_class": row["method_class"],
            "method_params": json.loads(row["method_params"]),
            "candidates": json.loads(row["candidates"]),
            "open": bool(row["open"]),
            "message_id": row["message_id"],
        }
    finally:
        conn.close()


def load_all_elections() -> list[dict[str, Any]]:
    """Load all elections from database."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM elections WHERE open=1")

        elections = []
        for row in cursor.fetchall():
            elections.append({
                "election_id": row["election_id"],
                "channel_id": row["channel_id"],
                "title": row["title"],
                "description": row["description"],
                "method_class": row["method_class"],
                "method_params": json.loads(row["method_params"]),
                "candidates": json.loads(row["candidates"]),
                "open": bool(row["open"]),
                "message_id": row["message_id"],
            })

        return elections
    finally:
        conn.close()


def mark_election_closed(election_id: int):
    """Mark an election as closed."""
    conn = get_connection()
    try:
        conn.execute("UPDATE elections SET open=0 WHERE election_id=?", (election_id,))
        conn.commit()
    finally:
        conn.close()


def delete_election(election_id: int):
    """Delete an election and all its ballots."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM elections WHERE election_id=?", (election_id,))
        conn.commit()
    finally:
        conn.close()


def save_ballot(
    ballot: Any, election_id: int, user_id: int, is_submitted: bool
) -> int:
    """Save a ballot to the database. Returns ballot_id."""
    conn = get_connection()

    try:
        ballot_dict = ballot.to_dict()

        data = (
            election_id,
            user_id,
            ballot.ballot_type,
            json.dumps(ballot_dict),
            1 if is_submitted else 0,
        )

        if ballot.ballot_id is None:
            # Insert new ballot
            cursor = conn.execute(
                """
                INSERT INTO ballots (election_id, user_id, ballot_type, ballot_data,
                                   is_submitted)
                VALUES (?, ?, ?, ?, ?)
                """,
                data,
            )
            conn.commit()
            ballot.ballot_id = cursor.lastrowid
            return cursor.lastrowid
        else:
            # Update existing ballot
            conn.execute(
                """
                UPDATE ballots
                SET election_id=?, user_id=?, ballot_type=?, ballot_data=?,
                    is_submitted=?
                WHERE ballot_id=?
                """,
                data + (ballot.ballot_id,),
            )
            conn.commit()
            return ballot.ballot_id
    finally:
        conn.close()


def load_ballot(ballot_id: int) -> dict[str, Any] | None:
    """Load ballot data by ID. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM ballots WHERE ballot_id=?", (ballot_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        ballot_data = json.loads(row["ballot_data"])
        return {
            "ballot_id": row["ballot_id"],
            "election_id": row["election_id"],
            "user_id": row["user_id"],
            "ballot_type": row["ballot_type"],
            "ballot_data": ballot_data,
            "is_submitted": bool(row["is_submitted"]),
            "session_id": ballot_data["session_id"],
        }
    finally:
        conn.close()


def load_user_ballot(
    election_id: int, user_id: int, is_submitted: bool
) -> dict[str, Any] | None:
    """Load a user's ballot for an election. Returns dict or None."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM ballots
            WHERE election_id=? AND user_id=? AND is_submitted=?
            """,
            (election_id, user_id, 1 if is_submitted else 0),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        ballot_data = json.loads(row["ballot_data"])
        return {
            "ballot_id": row["ballot_id"],
            "election_id": row["election_id"],
            "user_id": row["user_id"],
            "ballot_type": row["ballot_type"],
            "ballot_data": ballot_data,
            "is_submitted": bool(row["is_submitted"]),
            "session_id": ballot_data["session_id"],
        }
    finally:
        conn.close()


def load_all_ballots(election_id: int, is_submitted: bool) -> list[dict[str, Any]]:
    """Load all ballots for an election. Returns list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM ballots
            WHERE election_id=? AND is_submitted=?
            """,
            (election_id, 1 if is_submitted else 0),
        )

        ballots = []
        for row in cursor.fetchall():
            ballot_data = json.loads(row["ballot_data"])
            ballots.append({
                "ballot_id": row["ballot_id"],
                "election_id": row["election_id"],
                "user_id": row["user_id"],
                "ballot_type": row["ballot_type"],
                "ballot_data": ballot_data,
                "is_submitted": bool(row["is_submitted"]),
                "session_id": ballot_data["session_id"],
            })

        return ballots
    finally:
        conn.close()


def submit_ballot(election_id: int, user_id: int, ballot: Any):
    """Atomically move a ballot from interim to submitted."""
    with transaction() as conn:
        # Delete interim ballot
        conn.execute(
            """
            DELETE FROM ballots
            WHERE election_id=? AND user_id=? AND is_submitted=0
            """,
            (election_id, user_id),
        )

        # Insert submitted ballot
        ballot_dict = ballot.to_dict()
        conn.execute(
            """
            INSERT OR REPLACE INTO ballots
            (election_id, user_id, ballot_type, ballot_data, is_submitted)
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                election_id,
                user_id,
                ballot.ballot_type,
                json.dumps(ballot_dict),
            ),
        )


def get_vote_count(election_id: int) -> int:
    """Get the count of submitted ballots for an election."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM ballots WHERE election_id=? AND is_submitted=1",
            (election_id,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def new_session() -> int:
    """Generate a new session ID."""
    return time.monotonic_ns()
