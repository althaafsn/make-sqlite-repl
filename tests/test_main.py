import pytest
import subprocess
import sys
import os
from pathlib import Path

import src.db as db

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DB_SCRIPT = PROJECT_ROOT / "src" / "db.py"

class TestDB:

    def run_script(self, commands: list[str]) -> str[str]:
        proc = subprocess.Popen(
            [PYTHON, str(DB_SCRIPT), "db.db"],
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
        os.remove("test.db")
        

    def test_insert_and_select_multiple(self):
        result = self.run_script([
                "insert 1 user1 person1@example.com",
                "insert 2 user2 person2@example.com",
                "insert 3 user3 person3@example.com",
                "select",
                ".exit",
            ])
        print(result)
        os.remove("test.db")

    def test_insert_and_select_overflow(self):
        input = []

        for i in range(1400):
            input.append(f"insert {i} user{i} person{i}@example.com")
        input.append(f"insert {1400} user{1400} person{1400}@example.com")
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        # os.remove("test.db")

    def test_insert_overflow_username(self):
        input = []
        input.append(f"insert 1 {"a" * (db.COLUMN_USERNAME_SIZE + 1)} person1@example.com")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_insert_overflow_email(self):
        input = []
        input.append(f"insert 1 user1 {"a" * (db.COLUMN_EMAIL_SIZE + 1)}")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_insert_persistence(self):
        input = []
        input.append("insert 1 foo bar")
        input.append("insert 2 foo bar")
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        input = []
        input.append("select")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        fd = os.open("test.db", os.O_RDONLY)
        print(os.read(fd, os.fstat(fd).st_size))

    def test_constants(self):
        input = []
        input.append(".constants")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_btree(self):
        input = []
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_btree_insert(self):
        input = []
        input.append("insert 3 foo bar")
        input.append("insert 2 foo bar")
        input.append("insert 1 foo bar")
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_insert_duplicate_key(self):
        input = []
        input.append("insert 1 foo bar")
        input.append("insert 1 foo bar")
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        os.remove("test.db")

    def test_three_leaf_nodes(self):
        # os.remove("db.db")
        input = []
        for i in range(13):
            input.append(f"insert {i} user{i} person{i}@example.com")
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        # os.remove("test.db")

    def test_internal_node_find(self):
        os.remove("db.db")
        input = []
        for i in range(30):
            input.append(f"insert {i} user{i} person{i}@example.com")
        # input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)
        print(result)
        # os.remove("db.db")

    def test_seven_leaf_nodes(self):
        db_path = PROJECT_ROOT / "db.db"
        if db_path.exists():
            db_path.unlink()
        input = []
        input.append("insert 58 user58 person58@example.com")
        input.append("insert 56 user56 person56@example.com")
        input.append("insert 8 user8 person8@example.com")
        input.append("insert 54 user54 person54@example.com")
        input.append("insert 77 user77 person77@example.com")
        input.append("insert 7 user7 person7@example.com")
        input.append("insert 25 user25 person25@example.com")
        input.append("insert 71 user71 person71@example.com")
        input.append("insert 13 user13 person13@example.com")
        input.append("insert 22 user22 person22@example.com")
        input.append("insert 53 user53 person53@example.com")
        input.append("insert 51 user51 person51@example.com")
        input.append("insert 59 user59 person59@example.com")
        input.append("insert 32 user32 person32@example.com")
        input.append("insert 36 user36 person36@example.com")
        input.append("insert 79 user79 person79@example.com")
        input.append("insert 10 user10 person10@example.com")
        input.append("insert 33 user33 person33@example.com")
        input.append("insert 20 user20 person20@example.com")
        input.append("insert 4 user4 person4@example.com")
        input.append("insert 35 user35 person35@example.com")
        input.append("insert 76 user76 person76@example.com")
        input.append("insert 49 user49 person49@example.com")
        input.append("insert 24 user24 person24@example.com")
        input.append("insert 70 user70 person70@example.com")
        input.append("insert 48 user48 person48@example.com")
        input.append("insert 39 user39 person39@example.com")
        input.append("insert 15 user15 person15@example.com")
        input.append("insert 47 user47 person47@example.com")
        input.append("insert 30 user30 person30@example.com")
        input.append("insert 86 user86 person86@example.com")
        input.append("insert 31 user31 person31@example.com")
        input.append("insert 68 user68 person68@example.com")
        input.append("insert 37 user37 person37@example.com")
        input.append("insert 66 user66 person66@example.com")
        input.append("insert 63 user63 person63@example.com")
        input.append("insert 40 user40 person40@example.com")
        input.append("insert 78 user78 person78@example.com")
        input.append("insert 19 user19 person19@example.com")
        input.append("insert 46 user46 person46@example.com")
        input.append("insert 14 user14 person14@example.com")
        input.append("insert 81 user81 person81@example.com")
        input.append("insert 72 user72 person72@example.com")
        input.append("insert 6 user6 person6@example.com")
        input.append("insert 50 user50 person50@example.com")
        input.append("insert 85 user85 person85@example.com")
        input.append("insert 67 user67 person67@example.com")
        input.append("insert 2 user2 person2@example.com")
        input.append("insert 55 user55 person55@example.com")
        input.append("insert 69 user69 person69@example.com")
        input.append("insert 5 user5 person5@example.com")
        input.append("insert 65 user65 person65@example.com")
        input.append("insert 52 user52 person52@example.com")
        input.append("insert 1 user1 person1@example.com")
        input.append("insert 29 user29 person29@example.com")
        input.append("insert 9 user9 person9@example.com")
        input.append("insert 43 user43 person43@example.com")
        input.append("insert 75 user75 person75@example.com")
        input.append("insert 21 user21 person21@example.com")
        input.append("insert 82 user82 person82@example.com")
        input.append("insert 12 user12 person12@example.com")
        input.append("insert 18 user18 person18@example.com")
        input.append("insert 60 user60 person60@example.com")
        input.append("insert 44 user44 person44@example.com")
        input.append(".btree")
        input.append(".exit")
        result = self.run_script(input)

        tree_start = result.index("db > Tree:")
        assert result[tree_start:] == [
            "db > Tree:",
            "- internal (size 1)",
            "  - internal (size 2)",
            "    - leaf (size 7)",
            "      - 1",
            "      - 2",
            "      - 4",
            "      - 5",
            "      - 6",
            "      - 7",
            "      - 8",
            "    - key 8",
            "    - leaf (size 11)",
            "      - 9",
            "      - 10",
            "      - 12",
            "      - 13",
            "      - 14",
            "      - 15",
            "      - 18",
            "      - 19",
            "      - 20",
            "      - 21",
            "      - 22",
            "    - key 22",
            "    - leaf (size 8)",
            "      - 24",
            "      - 25",
            "      - 29",
            "      - 30",
            "      - 31",
            "      - 32",
            "      - 33",
            "      - 35",
            "  - key 35",
            "  - internal (size 3)",
            "    - leaf (size 12)",
            "      - 36",
            "      - 37",
            "      - 39",
            "      - 40",
            "      - 43",
            "      - 44",
            "      - 46",
            "      - 47",
            "      - 48",
            "      - 49",
            "      - 50",
            "      - 51",
            "    - key 51",
            "    - leaf (size 11)",
            "      - 52",
            "      - 53",
            "      - 54",
            "      - 55",
            "      - 56",
            "      - 58",
            "      - 59",
            "      - 60",
            "      - 63",
            "      - 65",
            "      - 66",
            "    - key 66",
            "    - leaf (size 7)",
            "      - 67",
            "      - 68",
            "      - 69",
            "      - 70",
            "      - 71",
            "      - 72",
            "      - 75",
            "    - key 75",
            "    - leaf (size 8)",
            "      - 76",
            "      - 77",
            "      - 78",
            "      - 79",
            "      - 81",
            "      - 82",
            "      - 85",
            "      - 86",
            "db > ",
        ]