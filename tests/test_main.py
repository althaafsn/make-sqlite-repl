import pytest
import subprocess
import sys
from pathlib import Path

import src.db as db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DB_SCRIPT = PROJECT_ROOT / "src" / "db.py"

class TestDB:

    def run_script(self, commands: list[str]) -> str[str]:
        proc = subprocess.Popen(
            [PYTHON, str(DB_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
        )
        stdin = "\n".join(commands) + "\n"
        stdout, stderr = proc.communicate(stdin)

        if stderr:
            raise RuntimeError(f"Error running script: {stderr}")

        return [line for line in stdout.splitlines() if line != ""]

    def test_basic_insert_and_select(self):
        result = self.run_script([
                "insert 1 user1 person1@example.com",
                "select",
                ".exit",
            ])

        print(result)

    def test_insert_and_select_multiple(self):
        result = self.run_script([
                "insert 1 user1 person1@example.com",
                "insert 2 user2 person2@example.com",
                "insert 3 user3 person3@example.com",
                "select",
                ".exit",
            ])
        print(result)

    def test_insert_and_select_overflow(self):
        input = []

        for i in range(db.TABLE_MAX_ROWS + 1):
            input.append(f"insert {i} user{i} person{i}@example.com")
        input.append(f"insert {db.TABLE_MAX_ROWS + 1} user{db.TABLE_MAX_ROWS + 1} person{db.TABLE_MAX_ROWS + 1}@example.com")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)

    def test_insert_overflow_username(self):
        input = []
        input.append(f"insert 1 {"a" * (db.USERNAME_SIZE + 1)} person1@example.com")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)

    def test_insert_overflow_email(self):
        input = []
        input.append(f"insert 1 user1 {"a" * (db.EMAIL_SIZE + 1)}")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)