"""
CLI demo for the Secure Enterprise RAG system.

Usage:
    python main.py                     # interactive username/password login
    python main.py --user aisha.hr     # pre-fill username (still asks for password)
"""

import argparse
import getpass

from src.auth import UserDirectory
from src.rag_pipeline import SecureRAGPipeline

MAX_LOGIN_ATTEMPTS = 3


def print_header(user):
    print("=" * 70)
    print(f"Logged in as: {user.full_name}  ({user.username})")
    print(f"Role: {user.role.name}  |  Department: {user.department}")
    print(f"Allowed departments: {sorted(user.role.allowed_departments)}")
    print(f"Max confidentiality level: {user.role.max_confidentiality}")
    print("=" * 70)


def run_query(pipeline, user, question):
    result = pipeline.ask(question, user)
    print(f"\nQ: {question}")
    print("-" * 70)
    print(result.answer)
    if result.sources:
        print("\nSources used:")
        for s in result.sources:
            print(f"  - {s.title}  [{s.department}, level {s.confidentiality_level}]")
    if result.denied_count:
        print(f"\n(Note: {result.denied_count} matching chunk(s) were withheld "
              f"due to your access level.)")
    print()


def login(directory, prefill_username=None):
    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        username = prefill_username or input("Username: ").strip()
        password = getpass.getpass("Password: ")
        try:
            return directory.login(username, password)
        except PermissionError as e:
            print(f"{e} ({attempt}/{MAX_LOGIN_ATTEMPTS} attempts)")
            prefill_username = None  # don't keep retrying a bad prefilled user silently
    print("Too many failed login attempts. Exiting.")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="username to pre-fill (password still required)")
    args = parser.parse_args()

    directory = UserDirectory()
    user = login(directory, prefill_username=args.user)
    print_header(user)

    pipeline = SecureRAGPipeline()

    print("Type a question, or 'exit' to quit.\n")
    while True:
        question = input("> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        run_query(pipeline, user, question)


if __name__ == "__main__":
    main()
