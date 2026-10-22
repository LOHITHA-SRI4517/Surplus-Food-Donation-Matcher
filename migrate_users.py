
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / "foodbridge.db"


def migrate():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN IMMEDIATE")

        result = db.execute("""
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'users'
        """).fetchone()

        if result is None:
            raise RuntimeError("Users table not found. Migration stopped.")

        schema = result["sql"]

        if "'reviewer'" not in schema:
            old_table = db.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                AND name = 'users_before_reviewer_migration'
            """).fetchone()

            if old_table:
                raise RuntimeError(
                    "Migration backup table already exists. "
                    "No changes were made; ask for help before retrying."
                )

            db.execute("""
                ALTER TABLE users
                RENAME TO users_before_reviewer_migration
            """)

            db.execute("""
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
            """)

            db.execute("""
                INSERT INTO users
                    (id, username, password_hash, role,
                     restaurant_name, ngo_id)
                SELECT id, username, password_hash, role,
                       restaurant_name, ngo_id
                FROM users_before_reviewer_migration
            """)

            db.execute("DROP TABLE users_before_reviewer_migration")
            print("Users table updated; existing accounts preserved.")
        else:
            print("Reviewer role is already supported.")

        reviewer = db.execute(
            "SELECT id FROM users WHERE username = ?",
            ("REVIEW001",)
        ).fetchone()

        if not reviewer:
            db.execute("""
                INSERT INTO users
                    (username, password_hash, role, restaurant_name, ngo_id)
                VALUES (?, ?, ?, NULL, NULL)
            """, (
                "REVIEW001",
                generate_password_hash("review123"),
                "reviewer"
            ))
            print("Reviewer account created.")
        else:
            print("Reviewer account already exists; its password was not changed.")

        db.commit()

        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print("Migration successful.")
        print("Total user accounts:", count)
        print("Reviewer username: REVIEW001")
        print("Reviewer password: review123")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
