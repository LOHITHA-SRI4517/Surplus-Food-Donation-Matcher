
import unittest
from services.workflow import can_create_pickup


class TestPickupWorkflow(unittest.TestCase):

    def test_all_conditions_satisfied(self):
        self.assertTrue(
            can_create_pickup("NGO_ACCEPTED", True, True)
        )

    def test_ngo_not_accepted(self):
        self.assertFalse(
            can_create_pickup("NGO_ACCEPTED", False, True)
        )

    def test_location_not_confirmed(self):
        self.assertFalse(
            can_create_pickup("NGO_ACCEPTED", True, False)
        )

    def test_wrong_donation_status(self):
        self.assertFalse(
            can_create_pickup("NGO_PENDING", True, True)
        )


if __name__ == "__main__":
    unittest.main()
