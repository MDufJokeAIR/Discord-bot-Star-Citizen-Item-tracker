import sqlite3
import os
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "inventory.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id           TEXT PRIMARY KEY,
                allowed_channel_id TEXT
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT    NOT NULL,
                user_id     TEXT    NOT NULL,
                item_name   TEXT    NOT NULL COLLATE NOCASE,
                quantity    INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
                location    TEXT,
                added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_guild_user
                ON inventory (guild_id, user_id);

            CREATE INDEX IF NOT EXISTS idx_guild_item
                ON inventory (guild_id, item_name);

            CREATE TRIGGER IF NOT EXISTS update_timestamp
                AFTER UPDATE ON inventory
                FOR EACH ROW
            BEGIN
                UPDATE inventory SET updated_at = CURRENT_TIMESTAMP
                WHERE id = OLD.id;
            END;

            CREATE TABLE IF NOT EXISTS resources (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id      TEXT    NOT NULL,
                user_id       TEXT    NOT NULL,
                resource_name TEXT    NOT NULL COLLATE NOCASE,
                quantity      REAL    NOT NULL CHECK(quantity > 0),
                unit          TEXT    NOT NULL CHECK(unit IN ('SCU','Units')),
                quality       INTEGER CHECK(quality BETWEEN 0 AND 1000),
                location      TEXT,
                added_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_res_guild_user
                ON resources (guild_id, user_id);

            CREATE INDEX IF NOT EXISTS idx_res_guild_name
                ON resources (guild_id, resource_name);

            CREATE TRIGGER IF NOT EXISTS update_res_timestamp
                AFTER UPDATE ON resources
                FOR EACH ROW
            BEGIN
                UPDATE resources SET updated_at = CURRENT_TIMESTAMP
                WHERE id = OLD.id;
            END;
        """)


# ── helpers ────────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    return name.strip()


# ── write operations ───────────────────────────────────────────────────────────

def upsert_item(
    guild_id: str,
    user_id: str,
    item_name: str,
    quantity: int,
    location: Optional[str],
) -> dict:
    """
    Add `quantity` of `item_name` for a user.
    If a row with the same (guild, user, item, location) already exists its
    quantity is increased; otherwise a new row is inserted.
    Returns the updated row as a dict.
    """
    item_name = _normalise(item_name)
    location = location.strip() if location else None

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id, quantity FROM inventory
            WHERE guild_id=? AND user_id=? AND item_name=? AND (location IS ? OR (location IS NULL AND ? IS NULL))
            """,
            (guild_id, user_id, item_name, location, location),
        ).fetchone()

        if existing:
            new_qty = existing["quantity"] + quantity
            conn.execute(
                "UPDATE inventory SET quantity=? WHERE id=?",
                (new_qty, existing["id"]),
            )
            row_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO inventory (guild_id, user_id, item_name, quantity, location)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, item_name, quantity, location),
            )
            row_id = cur.lastrowid

        return dict(
            conn.execute("SELECT * FROM inventory WHERE id=?", (row_id,)).fetchone()
        )


def remove_item(
    guild_id: str,
    user_id: str,
    item_name: str,
    quantity: int,
    location: Optional[str],
) -> tuple[bool, str]:
    """
    Remove `quantity` of `item_name` from a user's inventory.
    Returns (success, message).
    """
    item_name = _normalise(item_name)
    location = location.strip() if location else None

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, quantity, location FROM inventory
            WHERE guild_id=? AND user_id=? AND item_name=?
            ORDER BY
                CASE WHEN location IS ? THEN 0 ELSE 1 END,
                quantity DESC
            """,
            (guild_id, user_id, item_name, location),
        ).fetchall()

        if not rows:
            return False, f"No **{item_name}** found in that user's inventory."

        # If location specified, match exactly; otherwise sum all locations
        if location is not None:
            rows = [r for r in rows if r["location"] == location]
            if not rows:
                return False, f"No **{item_name}** found at **{location}**."

        total_available = sum(r["quantity"] for r in rows)
        if quantity > total_available:
            return (
                False,
                f"Cannot remove **{quantity}** — only **{total_available}** available.",
            )

        remaining = quantity
        for row in rows:
            if remaining <= 0:
                break
            if row["quantity"] <= remaining:
                remaining -= row["quantity"]
                conn.execute("DELETE FROM inventory WHERE id=?", (row["id"],))
            else:
                conn.execute(
                    "UPDATE inventory SET quantity=? WHERE id=?",
                    (row["quantity"] - remaining, row["id"]),
                )
                remaining = 0

        return True, f"Removed **{quantity}x {item_name}** successfully."


# ── read operations ────────────────────────────────────────────────────────────

def get_item_info(guild_id: str, item_name: str) -> list[dict]:
    """Return every row matching item_name across all users in a guild."""
    item_name = _normalise(item_name)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, item_name, SUM(quantity) as quantity, location
            FROM inventory
            WHERE guild_id=? AND item_name=?
            GROUP BY user_id, location
            ORDER BY quantity DESC
            """,
            (guild_id, item_name),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_inventory(guild_id: str, user_id: str) -> list[dict]:
    """Return all items owned by a user."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT item_name, SUM(quantity) as quantity, location
            FROM inventory
            WHERE guild_id=? AND user_id=?
            GROUP BY item_name, location
            ORDER BY item_name
            """,
            (guild_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


# ── guild config ───────────────────────────────────────────────────────────────

def set_allowed_channel(guild_id: str, channel_id: Optional[str]) -> None:
    """Persist the allowed channel for a guild (None = unrestricted)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO guild_config (guild_id, allowed_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET allowed_channel_id=excluded.allowed_channel_id
            """,
            (guild_id, channel_id),
        )


def get_allowed_channel(guild_id: str) -> Optional[str]:
    """Return the allowed channel ID for a guild, or None if unrestricted."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT allowed_channel_id FROM guild_config WHERE guild_id=?",
            (guild_id,),
        ).fetchone()
        return row["allowed_channel_id"] if row else None


# ── item search ─────────────────────────────────────────────────────────────────

def search_items(guild_id: str, partial: str) -> list[str]:
    """Return distinct item names matching a partial string (for autocomplete)."""
    partial = _normalise(partial)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT item_name FROM inventory
            WHERE guild_id=? AND item_name LIKE ?
            ORDER BY item_name
            LIMIT 25
            """,
            (guild_id, f"%{partial}%"),
        ).fetchall()
        return [r["item_name"] for r in rows]


# ── resource write operations ──────────────────────────────────────────────────

def upsert_resource(
    guild_id: str,
    user_id: str,
    resource_name: str,
    quantity: float,
    unit: str,
    quality: Optional[int],
    location: Optional[str],
) -> dict:
    """
    Add `quantity` of a resource for a user.
    SCU rows are matched by (guild, user, resource, quality, location).
    Unit rows are matched by (guild, user, resource, location) — no quality.
    Returns the updated row as a dict.
    """
    resource_name = _normalise(resource_name)
    location = location.strip() if location else None

    with get_connection() as conn:
        if unit == "SCU":
            existing = conn.execute(
                """
                SELECT id, quantity FROM resources
                WHERE guild_id=? AND user_id=? AND resource_name=? AND unit='SCU'
                  AND (quality IS ? OR (quality IS NULL AND ? IS NULL))
                  AND (location IS ? OR (location IS NULL AND ? IS NULL))
                """,
                (guild_id, user_id, resource_name, quality, quality, location, location),
            ).fetchone()
        else:
            existing = conn.execute(
                """
                SELECT id, quantity FROM resources
                WHERE guild_id=? AND user_id=? AND resource_name=? AND unit='Units'
                  AND (location IS ? OR (location IS NULL AND ? IS NULL))
                """,
                (guild_id, user_id, resource_name, location, location),
            ).fetchone()

        if existing:
            new_qty = round(existing["quantity"] + quantity, 4)
            conn.execute(
                "UPDATE resources SET quantity=? WHERE id=?",
                (new_qty, existing["id"]),
            )
            row_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO resources
                    (guild_id, user_id, resource_name, quantity, unit, quality, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, resource_name, quantity, unit, quality, location),
            )
            row_id = cur.lastrowid

        return dict(
            conn.execute("SELECT * FROM resources WHERE id=?", (row_id,)).fetchone()
        )


def remove_resource(
    guild_id: str,
    user_id: str,
    resource_name: str,
    quantity: float,
    unit: str,
    quality: Optional[int],
    location: Optional[str],
) -> tuple[bool, str]:
    """
    Remove `quantity` of a resource.
    If quality is given, only rows matching that quality are touched.
    Returns (success, message).
    """
    resource_name = _normalise(resource_name)
    location = location.strip() if location else None

    with get_connection() as conn:
        params: list = [guild_id, user_id, resource_name]
        qual_clause = ""
        if quality is not None:
            qual_clause = "AND quality=?"
            params.append(quality)
        loc_clause = ""
        if location is not None:
            loc_clause = "AND location=?"
            params.append(location)

        rows = conn.execute(
            f"""
            SELECT id, quantity FROM resources
            WHERE guild_id=? AND user_id=? AND resource_name=?
              {qual_clause} {loc_clause}
            ORDER BY quantity DESC
            """,
            params,
        ).fetchall()

        if not rows:
            hint = ""
            if quality is not None:
                hint += f" at quality **{quality}**"
            if location is not None:
                hint += f" in **{location}**"
            return False, f"No **{resource_name}**{hint} found in that user's stock."

        total_available = sum(r["quantity"] for r in rows)
        if quantity > total_available:
            return (
                False,
                f"Cannot remove **{quantity} {unit}** — only **{total_available:.4g}** available.",
            )

        remaining = quantity
        for row in rows:
            if remaining <= 0:
                break
            if row["quantity"] <= remaining:
                remaining = round(remaining - row["quantity"], 4)
                conn.execute("DELETE FROM resources WHERE id=?", (row["id"],))
            else:
                conn.execute(
                    "UPDATE resources SET quantity=? WHERE id=?",
                    (round(row["quantity"] - remaining, 4), row["id"]),
                )
                remaining = 0

        return True, f"Removed **{quantity} {unit}** of **{resource_name}** successfully."


# ── resource read operations ───────────────────────────────────────────────────

def get_resource_info(guild_id: str, resource_name: str) -> list[dict]:
    """Return all rows for a resource across the whole guild."""
    resource_name = _normalise(resource_name)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, resource_name, SUM(quantity) as quantity,
                   unit, quality, location
            FROM resources
            WHERE guild_id=? AND resource_name=?
            GROUP BY user_id, quality, location
            ORDER BY quality DESC, quantity DESC
            """,
            (guild_id, resource_name),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_resources(guild_id: str, user_id: str) -> list[dict]:
    """Return all resources owned by a user."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT resource_name, SUM(quantity) as quantity,
                   unit, quality, location
            FROM resources
            WHERE guild_id=? AND user_id=?
            GROUP BY resource_name, quality, location
            ORDER BY resource_name, quality DESC
            """,
            (guild_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]
