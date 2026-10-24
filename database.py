
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash


DB_PATH = Path(__file__).resolve().parent / "foodbridge.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def log_event(db, donation_id, event_type, message):
    db.execute(
        """
        INSERT INTO events
            (donation_id, event_type, message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            donation_id,
            event_type,
            message,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def create_users_table(db):
    """
    Create users table and migrate older schemas to support reviewer role.
    Preserve existing accounts and their IDs where possible.
    """
    existing = db.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = 'users'
        """
    ).fetchone()

    if not existing:
        db.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('restaurant', 'ngo', 'reviewer')),
                restaurant_name TEXT,
                ngo_id INTEGER,
                FOREIGN KEY (ngo_id) REFERENCES ngos(id)
            )
            """
        )
        return

    table_sql = (existing["sql"] or "").lower()

    if "reviewer" in table_sql:
        return

    old_columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(users)").fetchall()
    }

    db.execute("PRAGMA foreign_keys = OFF")

    try:
        db.execute("BEGIN")

        db.execute(
            "ALTER TABLE users RENAME TO users_old_migration"
        )

        db.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('restaurant', 'ngo', 'reviewer')),
                restaurant_name TEXT,
                ngo_id INTEGER,
                FOREIGN KEY (ngo_id) REFERENCES ngos(id)
            )
            """
        )

        if {
            "id",
            "username",
            "password_hash",
            "role",
            "restaurant_name",
            "ngo_id",
        }.issubset(old_columns):
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role,
                    restaurant_name, ngo_id
                )
                SELECT
                    id, username, password_hash, role,
                    restaurant_name, ngo_id
                FROM users_old_migration
                """
            )
        elif {
            "username",
            "password_hash",
            "role",
        }.issubset(old_columns):
            db.execute(
                """
                INSERT INTO users (
                    username, password_hash, role
                )
                SELECT username, password_hash, role
                FROM users_old_migration
                """
            )

        db.execute("DROP TABLE users_old_migration")
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.execute("PRAGMA foreign_keys = ON")


def migrate_pickup_evidence_columns(db):
    """
    Add pickup evidence and location confirmation fields to older databases.
    Existing pickup records are preserved.
    """
    table_exists = db.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'pickups'
        """
    ).fetchone()

    if not table_exists:
        return

    existing_columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(pickups)"
        ).fetchall()
    }

    required_columns = {
        "evidence_filename": "TEXT",
        "collected_at": "TEXT",
        "collected_by": "TEXT",
        "collection_notes": "TEXT",
        "location_confirmed": (
            "INTEGER NOT NULL DEFAULT 0"
        ),
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            db.execute(
                f"ALTER TABLE pickups ADD COLUMN "
                f"{column_name} {column_type}"
            )


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS ngos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                categories TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant TEXT NOT NULL,
                food_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                city TEXT NOT NULL,
                prepared_at TEXT NOT NULL,
                pickup_deadline TEXT NOT NULL,
                dropoff_location TEXT NOT NULL,
                status TEXT NOT NULL,
                matched_ngo_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (matched_ngo_id) REFERENCES ngos(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id INTEGER,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (donation_id) REFERENCES donations(id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id INTEGER NOT NULL UNIQUE,
                approved_by TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                FOREIGN KEY (donation_id) REFERENCES donations(id)
            );

            CREATE TABLE IF NOT EXISTS pickups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL,
                location TEXT NOT NULL,
                location_confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                evidence_filename TEXT,
                collected_at TEXT,
                collected_by TEXT,
                collection_notes TEXT,
                FOREIGN KEY (donation_id) REFERENCES donations(id)
            );
            """
        )

        # Migrate older pickup tables without deleting existing records.
        migrate_pickup_evidence_columns(db)

        demo_ngos = [
            (
                "HOPE001",
                "Hope Foundation",
                "Kurnool",
                "Cooked Meals, Bakery, Fruits",
                100,
                1,
            ),
            (
                "AKSH001",
                "Akshaya Trust",
                "Kurnool",
                "Cooked Meals, Vegetables",
                80,
                1,
            ),
            (
                "HELP001",
                "Helping Hands",
                "Kurnool",
                "Cooked Meals, Bakery, Fruits, Vegetables",
                60,
                1,
            ),
            (
                "CARE001",
                "Care & Share",
                "Kurnool",
                "Bakery, Fruits, Vegetables",
                50,
                1,
            ),
            (
                "MEAL001",
                "Meal Support Network",
                "Kurnool",
                "Cooked Meals",
                120,
                1,
            ),
        ]

        for ngo in demo_ngos:
            db.execute(
                """
                INSERT OR IGNORE INTO ngos
                    (code, name, city, categories, capacity, available)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ngo,
            )

        # Create or migrate users after the NGOs table exists.
        create_users_table(db)

        demo_users = [
            (
                "REST001",
                "demo123",
                "restaurant",
                "Green Leaf Kitchen",
                None,
            ),
            ("HOPE001", "hope123", "ngo", None, "HOPE001"),
            ("AKSH001", "akshaya123", "ngo", None, "AKSH001"),
            ("HELP001", "help123", "ngo", None, "HELP001"),
            ("CARE001", "care123", "ngo", None, "CARE001"),
            ("MEAL001", "meal123", "ngo", None, "MEAL001"),
            ("REVIEW001", "review123", "reviewer", None, None),
        ]

        for username, password, role, restaurant_name, ngo_code in demo_users:
            ngo_id = None

            if ngo_code:
                ngo_row = db.execute(
                    "SELECT id FROM ngos WHERE code = ?",
                    (ngo_code,),
                ).fetchone()

                if ngo_row is None:
                    continue

                ngo_id = ngo_row["id"]

            existing_user = db.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing_user is None:
                db.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, role,
                        restaurant_name, ngo_id
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        generate_password_hash(password),
                        role,
                        restaurant_name,
                        ngo_id,
                    ),
                )


if __name__ == "__main__":
    init_db()
    print("FoodBridge database initialized successfully.")
    print("Pickup evidence and location confirmation columns are ready.")
