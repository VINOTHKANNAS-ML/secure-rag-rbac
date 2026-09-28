"""
Create or reset a user account in data/users.json with a securely hashed
password. Run this to add new demo users or rotate passwords - never edit
password hashes by hand.

Usage:
    python scripts/create_user.py

Or non-interactively:
    python scripts/create_user.py --username jane.doe --full-name "Jane Doe" \\
        --department Finance --role finance_manager --password "SomePass@123"
"""

import argparse
import binascii
import getpass
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import USERS_PATH
from src.rbac import ROLES

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username")
    parser.add_argument("--full-name")
    parser.add_argument("--department")
    parser.add_argument("--role", choices=list(ROLES.keys()))
    parser.add_argument("--password", help="If omitted, you'll be prompted securely.")
    args = parser.parse_args()

    username = args.username or input("Username: ").strip()
    full_name = args.full_name or input("Full name: ").strip()
    department = args.department or input("Department: ").strip()

    print(f"Available roles: {list(ROLES.keys())}")
    role = args.role or input("Role: ").strip()
    if role not in ROLES:
        print(f"Unknown role '{role}'. Must be one of {list(ROLES.keys())}.")
        return

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return

    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}

    salt_hex, hash_hex = hash_password(password)
    users[username] = {
        "role": role,
        "full_name": full_name,
        "department": department,
        "password_salt": salt_hex,
        "password_hash": hash_hex,
    }

    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

    print(f"Saved user '{username}' with role '{role}'.")


if __name__ == "__main__":
    main()
