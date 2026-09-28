"""
Lists the Groq models currently available to your API key. Run this any
time you hit a 'model_not_found' error - Groq's model catalog changes
over time, so the hardcoded default in src/config.py can go stale.

Usage:
    python scripts/list_groq_models.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("GROQ_API_KEY is not set in your .env file.")
        return

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    models = client.models.list()

    print("Models available to your Groq API key:\n")
    for m in models.data:
        print(f"  - {m.id}")

    print(
        "\nCopy one of these exact IDs into GROQ_MODEL in src/config.py "
        "if the current default is returning a 404."
    )


if __name__ == "__main__":
    main()
