"""
Quick CLI test for the Observatory agent.
Usage: python -m src.agent.test_agent

Requires:
  - GROQ_API_KEY set in environment or .env file
  - Observatory API running on localhost:8003
"""

import os
import sys

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

from src.agent.graph import ask


TEST_QUESTIONS = [
    "¿Cuántas empresas activas hay en Bogotá?",
    "¿Cuál es la localidad con más empresas?",
    "¿Cuál es la tasa de desempleo más reciente?",
]


def main():
    # Use CLI argument or default test questions
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]
    else:
        questions = TEST_QUESTIONS

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")

        result = ask(q)

        print(f"\nA: {result['answer']}")
        print(f"\nTools used: {result['tools_used']}")
        print(f"Steps: {result['steps']}")


if __name__ == "__main__":
    main()
