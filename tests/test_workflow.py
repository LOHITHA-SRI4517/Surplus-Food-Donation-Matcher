
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from services.safety_agent import check_food_safety
from services.matching_agent import find_best_match
from services.workflow import can_create_pickup


class FoodBridgeWorkflowTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("""
            CREATE TABLE ngos (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                city TEXT,
                categories TEXT,
                capacity INTEGER,
                available INTEGER
            )
        """)
        self.db.execute("""
            INSERT INTO ngos
            VALUES (1, 'HOPE001', 'Hope Foundation', 'Kurnool',
                    'Cooked Meals, Bakery', 100, 1)
        """)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.db.close()

    def test_tc1_fresh_food_matches_eligible_ngo(self):
        prepared = (self.now - timedelta(hours=1)).isoformat()
        safety = check_food_safety("Cooked Meals", prepared, self.now)
        matches = find_best_match(self.db, "Cooked Meals", "Kurnool", 20)

        self.assertTrue(safety["safe"])
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["code"], "HOPE001")

    def test_tc2_old_cooked_food_is_rejected(self):
        prepared = (self.now - timedelta(hours=5)).isoformat()
        safety = check_food_safety("Cooked Meals", prepared, self.now)

        self.assertFalse(safety["safe"])
        self.assertEqual(safety["status"], "REJECTED_SAFETY_EXPIRED")

    def test_tc3_collection_blocked_until_ngo_accepts(self):
        allowed = can_create_pickup(
            "APPROVED",
            ngo_accepted=False,
            location_confirmed=True
        )

        self.assertFalse(allowed)

    def test_tc4_location_change_blocks_collection(self):
        allowed = can_create_pickup(
            "APPROVED",
            ngo_accepted=True,
            location_confirmed=False
        )

        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
