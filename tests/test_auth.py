"""
Unit tests for password hashing and login logic. Runs against a temporary
users.json so it never touches the real data/users.json.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auth import hash_password
import src.config as config


class TestAuth(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self._users_path = os.path.join(self._tmp_dir, "users.json")

        salt = "aa" * 16  # fixed fake hex salt for test determinism
        good_hash = hash_password("CorrectHorse@123", salt)

        with open(self._users_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "test.user": {
                        "role": "employee",
                        "full_name": "Test User",
                        "department": "Engineering",
                        "password_salt": salt,
                        "password_hash": good_hash,
                    }
                },
                f,
            )

        self._orig_users_path = config.USERS_PATH
        config.USERS_PATH = self._users_path

        # Re-import after patching config so UserDirectory picks up the path
        import importlib
        import src.auth as auth_module
        importlib.reload(auth_module)
        self.auth_module = auth_module

    def tearDown(self):
        config.USERS_PATH = self._orig_users_path

    def test_correct_password_logs_in(self):
        directory = self.auth_module.UserDirectory()
        user = directory.login("test.user", "CorrectHorse@123")
        self.assertEqual(user.username, "test.user")
        self.assertEqual(user.role.name, "employee")

    def test_wrong_password_rejected(self):
        directory = self.auth_module.UserDirectory()
        with self.assertRaises(PermissionError):
            directory.login("test.user", "WrongPassword")

    def test_unknown_user_rejected(self):
        directory = self.auth_module.UserDirectory()
        with self.assertRaises(PermissionError):
            directory.login("nobody", "whatever")

    def test_add_user_then_login(self):
        directory = self.auth_module.UserDirectory()
        directory.add_user(
            username="new.hire",
            full_name="New Hire",
            department="Sales",
            role="employee",
            password="FreshPass@123",
        )
        # Re-open to prove it was persisted to disk, not just in-memory.
        directory2 = self.auth_module.UserDirectory()
        user = directory2.login("new.hire", "FreshPass@123")
        self.assertEqual(user.username, "new.hire")
        self.assertEqual(user.role.name, "employee")

    def test_add_duplicate_user_rejected(self):
        directory = self.auth_module.UserDirectory()
        with self.assertRaises(ValueError):
            directory.add_user(
                username="test.user",  # already exists from setUp
                full_name="Dupe",
                department="Sales",
                role="employee",
                password="FreshPass@123",
            )

    def test_add_user_unknown_role_rejected(self):
        directory = self.auth_module.UserDirectory()
        with self.assertRaises(ValueError):
            directory.add_user(
                username="bad.role",
                full_name="Bad Role",
                department="Sales",
                role="not_a_real_role",
                password="FreshPass@123",
            )

    def test_remove_user(self):
        directory = self.auth_module.UserDirectory()
        directory.remove_user("test.user")
        directory2 = self.auth_module.UserDirectory()
        with self.assertRaises(PermissionError):
            directory2.login("test.user", "CorrectHorse@123")

    def test_remove_unknown_user_rejected(self):
        directory = self.auth_module.UserDirectory()
        with self.assertRaises(KeyError):
            directory.remove_user("nobody")

    def test_list_users_excludes_password_fields(self):
        directory = self.auth_module.UserDirectory()
        users = directory.list_users()
        self.assertEqual(len(users), 1)
        self.assertNotIn("password_hash", users[0])
        self.assertNotIn("password_salt", users[0])
        self.assertEqual(users[0]["username"], "test.user")


if __name__ == "__main__":
    unittest.main()
