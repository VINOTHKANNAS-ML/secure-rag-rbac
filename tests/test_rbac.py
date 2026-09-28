"""
Unit tests for RBAC access logic. These don't touch the vector DB, so they
run instantly with no dependencies beyond stdlib + src/rbac.py.

Run:
    python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rbac import get_role


class TestRBAC(unittest.TestCase):
    def test_intern_only_sees_public_general(self):
        role = get_role("intern")
        self.assertTrue(role.can_access("General", 0))
        self.assertFalse(role.can_access("General", 1))
        self.assertFalse(role.can_access("Finance", 0))

    def test_employee_internal_level(self):
        role = get_role("employee")
        self.assertTrue(role.can_access("Engineering", 1))
        self.assertFalse(role.can_access("Engineering", 2))
        self.assertFalse(role.can_access("Finance", 0))

    def test_hr_manager_confidential_hr_only(self):
        role = get_role("hr_manager")
        self.assertTrue(role.can_access("HR", 2))
        self.assertFalse(role.can_access("HR", 3))
        self.assertFalse(role.can_access("Finance", 0))

    def test_legal_counsel_cross_department(self):
        role = get_role("legal_counsel")
        self.assertTrue(role.can_access("Legal", 3))
        self.assertTrue(role.can_access("Finance", 2))
        self.assertFalse(role.can_access("Engineering", 1))

    def test_executive_sees_everything(self):
        role = get_role("executive")
        self.assertTrue(role.can_access("Finance", 3))
        self.assertTrue(role.can_access("Engineering", 3))
        self.assertTrue(role.can_access("HR", 3))

    def test_unknown_role_raises(self):
        with self.assertRaises(ValueError):
            get_role("nonexistent_role")


if __name__ == "__main__":
    unittest.main()
