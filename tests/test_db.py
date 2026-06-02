# import pytest

import src.db as main

class TestDB:
    def test_insert_and_select(self):
        table = main.Table()
        insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=1, username="John Doe", email="john.doe@example.com"))
        main.execute_statement(insert, table)
        select = main.Statement(statement_type=main.StatementType.STATEMENT_SELECT)
        main.execute_statement(select, table)
        assert table.num_rows == 1
        row = main.Row(id=0, username="", email="")
        page, byte_offset = main.row_slot(table, 0)
        main.deserialize_row(page, row, byte_offset)
        assert row.id == 1
        assert row.username.strip("\x00") == "John Doe"
        assert row.email.strip("\x00") == "john.doe@example.com"

    def test_insert_and_select_multiple(self):
        table = main.Table()
        for i in range(10):
            insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=i, username=f"John Doe {i}", email=f"john.doe{i}@example.com"))
            main.execute_statement(insert, table)
        select = main.Statement(statement_type=main.StatementType.STATEMENT_SELECT)
        main.execute_statement(select, table)
        assert table.num_rows == 10
        for i in range(10):
            row = main.Row(id=0, username="", email="")
            page, byte_offset = main.row_slot(table, i)
            main.deserialize_row(page, row, byte_offset)
            assert row.id == i
            assert row.username.strip("\x00") == f"John Doe {i}"
            assert row.email.strip("\x00") == f"john.doe{i}@example.com"

    def test_insert_and_select_overflow(self):
        table = main.Table()
        for i in range(main.TABLE_MAX_ROWS):
            insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=i, username=f"John Doe {i}", email=f"john.doe{i}@example.com"))
            main.execute_statement(insert, table)
        insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=main.TABLE_MAX_ROWS, username="John Doe", email="john.doe@example.com"))
        result = main.execute_statement(insert, table)
        assert result == main.ExecuteResult.EXECUTE_TABLE_FULL
        assert table.num_rows == main.TABLE_MAX_ROWS

    def test_insert_max_length_id(self):
        table = main.Table()
        insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=2**main.ID_SIZE - 1, username="John Doe", email="john.doe@example.com"))
        main.execute_statement(insert, table)
        assert table.num_rows == 1
        row = main.Row(id=0, username="", email="")
        page, byte_offset = main.row_slot(table, 0)
        main.deserialize_row(page, row, byte_offset)
        assert row.id == 2**main.ID_SIZE - 1
        assert row.username.strip("\x00") == "John Doe"
        assert row.email.strip("\x00") == "john.doe@example.com"

    def test_insert_max_length_username(self):
        table = main.Table()
        insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=1, username="a" * main.USERNAME_SIZE, email="john.doe@example.com"))
        main.execute_statement(insert, table)
        assert table.num_rows == 1
        row = main.Row(id=0, username="", email="")
        page, byte_offset = main.row_slot(table, 0)
        main.deserialize_row(page, row, byte_offset)
        assert row.id == 1
        assert row.username.strip("\x00") == "a" * main.USERNAME_SIZE
        assert row.email.strip("\x00") == "john.doe@example.com"

    def test_insert_max_length_email(self):
        table = main.Table()
        insert = main.Statement(statement_type=main.StatementType.STATEMENT_INSERT, row_to_insert=main.Row(id=1, username="a", email="a" * main.EMAIL_SIZE))
        main.execute_statement(insert, table)
        assert table.num_rows == 1
        row = main.Row(id=0, username="", email="")
        page, byte_offset = main.row_slot(table, 0)
        main.deserialize_row(page, row, byte_offset)
        assert row.id == 1
        assert row.username.strip("\x00") == "a"
        assert row.email.strip("\x00") == "a" * main.EMAIL_SIZE

    def test_insert_overflow_username(self):
        table = main.Table()
        command = "insert"
        args = ["1", "a" * (main.USERNAME_SIZE + 1), "a"]
        insert = main.Statement()
        result = main.prepare_statement(command, args, insert)
        assert result == main.PrepareResult.PREPARE_STRING_TOO_LONG
        assert table.num_rows == 0

    def test_insert_overflow_email(self):
        table = main.Table()
        command = "insert"
        args = ["1", "a", "a" * (main.EMAIL_SIZE + 1)]
        insert = main.Statement()
        result = main.prepare_statement(command, args, insert)
        assert result == main.PrepareResult.PREPARE_STRING_TOO_LONG
        assert table.num_rows == 0