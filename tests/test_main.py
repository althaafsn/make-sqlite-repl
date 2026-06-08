import subprocess
import sys
from pathlib import Path

import pytest

import src.db as db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DB_SCRIPT = PROJECT_ROOT / "src" / "db.py"
DB_PATH = PROJECT_ROOT / "db.db"

SEVEN_LEAF_INSERT_IDS = [
    58, 56, 8, 54, 77, 7, 25, 71, 13, 22, 53, 51, 59, 32, 36, 79, 10, 33, 20, 4,
    35, 76, 49, 24, 70, 48, 39, 15, 47, 30, 86, 31, 68, 37, 66, 63, 40, 78, 19, 46,
    14, 81, 72, 6, 50, 85, 67, 2, 55, 69, 5, 65, 52, 1, 29, 9, 43, 75, 21, 82, 12,
    18, 60, 44,
]

SEVEN_LEAF_TREE = [
    "db > Tree:",
    "- internal (size 2)",
    "  - internal (size 3)",
    "    - internal (size 1)",
    "      - leaf (size 3)",
    "        - 1",
    "        - 2",
    "        - 4",
    "      - key 4",
    "      - leaf (size 2)",
    "        - 5",
    "        - 6",
    "    - key 6",
    "    - internal (size 2)",
    "      - leaf (size 2)",
    "        - 7",
    "        - 8",
    "      - key 8",
    "      - leaf (size 2)",
    "        - 9",
    "        - 10",
    "      - key 10",
    "      - leaf (size 2)",
    "        - 12",
    "        - 13",
    "    - key 13",
    "    - internal (size 2)",
    "      - leaf (size 2)",
    "        - 14",
    "        - 15",
    "      - key 15",
    "      - leaf (size 2)",
    "        - 18",
    "        - 19",
    "      - key 19",
    "      - leaf (size 3)",
    "        - 20",
    "        - 21",
    "        - 22",
    "    - key 22",
    "    - internal (size 3)",
    "      - leaf (size 2)",
    "        - 24",
    "        - 25",
    "      - key 25",
    "      - leaf (size 2)",
    "        - 29",
    "        - 30",
    "      - key 30",
    "      - leaf (size 2)",
    "        - 31",
    "        - 32",
    "      - key 32",
    "      - leaf (size 2)",
    "        - 33",
    "        - 35",
    "  - key 35",
    "  - internal (size 1)",
    "    - internal (size 2)",
    "      - leaf (size 3)",
    "        - 36",
    "        - 37",
    "        - 39",
    "      - key 39",
    "      - leaf (size 2)",
    "        - 40",
    "        - 43",
    "      - key 43",
    "      - leaf (size 2)",
    "        - 44",
    "        - 46",
    "    - key 46",
    "    - internal (size 2)",
    "      - leaf (size 2)",
    "        - 47",
    "        - 48",
    "      - key 48",
    "      - leaf (size 3)",
    "        - 49",
    "        - 50",
    "        - 51",
    "      - key 51",
    "      - leaf (size 3)",
    "        - 52",
    "        - 53",
    "        - 54",
    "  - key 54",
    "  - internal (size 2)",
    "    - internal (size 3)",
    "      - leaf (size 3)",
    "        - 55",
    "        - 56",
    "        - 58",
    "      - key 58",
    "      - leaf (size 3)",
    "        - 59",
    "        - 60",
    "        - 63",
    "      - key 63",
    "      - leaf (size 2)",
    "        - 65",
    "        - 66",
    "      - key 66",
    "      - leaf (size 2)",
    "        - 67",
    "        - 68",
    "    - key 68",
    "    - internal (size 1)",
    "      - leaf (size 3)",
    "        - 69",
    "        - 70",
    "        - 71",
    "      - key 71",
    "      - leaf (size 2)",
    "        - 72",
    "        - 75",
    "    - key 75",
    "    - internal (size 3)",
    "      - leaf (size 2)",
    "        - 76",
    "        - 77",
    "      - key 77",
    "      - leaf (size 2)",
    "        - 78",
    "        - 79",
    "      - key 79",
    "      - leaf (size 2)",
    "        - 81",
    "        - 82",
    "      - key 82",
    "      - leaf (size 2)",
    "        - 85",
    "        - 86",
    "db > ",
]


def insert(id_: int) -> str:
    return f"insert {id_} user{id_} person{id_}@example.com"


def inserts(ids: list[int]) -> list[str]:
    return [insert(id_) for id_ in ids]


def has_line(result: list[str], text: str) -> bool:
    return any(text in line for line in result)


def executed_count(result: list[str]) -> int:
    return sum("Executed." in line for line in result)


class TestDB:
    def setup_method(self):
        if DB_PATH.exists():
            DB_PATH.unlink()

    def run_script(self, commands: list[str]) -> list[str]:
        proc = subprocess.Popen(
            [PYTHON, str(DB_SCRIPT), "db.db"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
        )
        stdout, stderr = proc.communicate("\n".join(commands) + "\n")

        if stderr:
            raise RuntimeError(f"Error running script: {stderr}")

        return [line for line in stdout.splitlines() if line != ""]

    def test_basic_insert_and_select(self):
        result = self.run_script([
            "insert 1 user1 person1@example.com",
            "select",
            ".exit",
        ])
        assert has_line(result, "(1, user1, person1@example.com)")

    def test_insert_and_select_multiple(self):
        result = self.run_script([
            "insert 1 user1 person1@example.com",
            "insert 2 user2 person2@example.com",
            "insert 3 user3 person3@example.com",
            "select",
            ".exit",
        ])
        assert has_line(result, "(1, user1, person1@example.com)")
        assert has_line(result, "(2, user2, person2@example.com)")
        assert has_line(result, "(3, user3, person3@example.com)")

    def test_insert_overflow_username(self):
        username = "a" * (db.COLUMN_USERNAME_SIZE + 1)
        result = self.run_script([
            f"insert 1 {username} person1@example.com",
            "select",
            ".exit",
        ])
        assert has_line(result, "String is too long.")

    def test_insert_overflow_email(self):
        email = "a" * (db.COLUMN_EMAIL_SIZE + 1)
        result = self.run_script([
            f"insert 1 user1 {email}",
            "select",
            ".exit",
        ])
        assert has_line(result, "String is too long.")

    def test_insert_persistence(self):
        self.run_script([
            "insert 1 foo bar",
            "insert 2 foo bar",
            ".exit",
        ])
        result = self.run_script(["select", ".exit"])
        assert has_line(result, "(1, foo, bar)")
        assert has_line(result, "(2, foo, bar)")

    def test_constants(self):
        result = self.run_script([".constants", ".exit"])
        assert has_line(result, f"ROW_SIZE:  {db.ROW_SIZE}")
        assert has_line(result, f"LEAF_NODE_MAX_CELLS:  {db.LEAF_NODE_MAX_CELLS}")

    def test_btree(self):
        result = self.run_script([".btree", ".exit"])
        assert has_line(result, "Tree:")
        assert has_line(result, "- leaf (size 0)")

    def test_btree_insert(self):
        result = self.run_script([
            "insert 3 foo bar",
            "insert 2 foo bar",
            "insert 1 foo bar",
            ".btree",
            ".exit",
        ])
        assert has_line(result, "- leaf (size 3)")
        assert has_line(result, "- 1")
        assert has_line(result, "- 2")
        assert has_line(result, "- 3")

    def test_insert_duplicate_key(self):
        result = self.run_script([
            "insert 1 foo bar",
            "insert 1 foo bar",
            ".exit",
        ])
        assert has_line(result, "Error: Duplicate key.")

    def test_three_leaf_nodes(self):
        result = self.run_script(inserts(range(14)) + [".btree", ".exit"])
        assert has_line(result, "- internal (size 1)")

    def test_internal_node_find(self):
        result = self.run_script(inserts(range(30)) + [".exit"])
        assert executed_count(result) == 30
        assert not any("Error:" in line for line in result)

    def test_seven_leaf_nodes(self):
        result = self.run_script(inserts(SEVEN_LEAF_INSERT_IDS) + [".btree", ".exit"])
        tree_start = result.index("db > Tree:")
        assert result[tree_start:] == SEVEN_LEAF_TREE
