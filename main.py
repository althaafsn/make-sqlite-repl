import sys
from enum import Enum
from dataclasses import dataclass

from numpy import byte

@dataclass
class Row:
    id: int
    username: str
    email: str

@dataclass
class Statement:
    statement_type: StatementType
    row_to_insert: Row

    def __init__(self):
        self.statement_type = None
        self.row_to_insert = None

ID_SIZE = 4
USERNAME_SIZE = 32
EMAIL_SIZE = 255
ID_OFFSET = 0
USERNAME_OFFSET = ID_OFFSET + ID_SIZE
EMAIL_OFFSET = USERNAME_OFFSET + USERNAME_SIZE
ROW_SIZE = ID_SIZE + USERNAME_SIZE + EMAIL_SIZE

ENTRY_SIZE = ID_SIZE + USERNAME_SIZE + EMAIL_SIZE

PAGE_SIZE = 4096
TABLE_MAX_PAGES = 100
ROWS_PER_PAGE = PAGE_SIZE // ROW_SIZE
TABLE_MAX_ROWS = ROWS_PER_PAGE * TABLE_MAX_PAGES

@dataclass
class Table:
    num_rows: int
    pages: list[bytearray | None]

    def __init__(self):
        self.num_rows = 0
        self.pages = [None] * TABLE_MAX_PAGES
    
    def free_table(self):
        self.pages = [None] * TABLE_MAX_PAGES
        self.num_rows = 0
        return

class MetaCommandResult(Enum):
    META_COMMAND_SUCCESS = 0
    META_COMMAND_UNRECOGNIZED_COMMAND = 1

class PrepareResult(Enum):
    PREPARE_SUCCESS = 0
    PREPARE_UNRECOGNIZED_STATEMENT = 1
    PREPARE_SYNTAX_ERROR = 2

class ExecuteResult(Enum):
    EXECUTE_SUCCESS = 0
    EXECUTE_TABLE_FULL = 1

class StatementType(Enum):
    STATEMENT_INSERT = 0
    STATEMENT_SELECT = 1

def serialize_row(source: Row, destination: bytearray, byte_offset: int):
    offset = byte_offset
    destination[offset+ID_OFFSET:offset+ID_OFFSET+ID_SIZE] = source.id.to_bytes(ID_SIZE, "little")
    offset += ID_SIZE
    destination[offset+USERNAME_OFFSET:offset+USERNAME_OFFSET+USERNAME_SIZE] = source.username.encode("utf-8")
    offset += USERNAME_SIZE
    destination[offset+EMAIL_OFFSET:offset+EMAIL_OFFSET+EMAIL_SIZE] = source.email.encode("utf-8")
    offset += EMAIL_SIZE
    return

def deserialize_row(source: bytearray, destination: Row, byte_offset: int):
    offset = byte_offset
    destination.id = int.from_bytes(source[offset+ID_OFFSET:offset+ID_OFFSET+ID_SIZE], "little")
    offset += ID_SIZE
    destination.username = source[offset+USERNAME_OFFSET:offset+USERNAME_OFFSET+USERNAME_SIZE].decode("utf-8")
    offset += USERNAME_SIZE
    destination.email = source[offset+EMAIL_OFFSET:offset+EMAIL_OFFSET+EMAIL_SIZE].decode("utf-8")
    offset += EMAIL_SIZE
    return 

def row_slot(table: Table, row_num: int):
    page_num = row_num // ROWS_PER_PAGE
    page = table.pages[page_num]
    if page is None:
        page = bytearray(PAGE_SIZE)
        table.pages[page_num] = page
    offset = row_num % ROWS_PER_PAGE
    byte_offset = offset * ROW_SIZE
    return page, byte_offset

def do_meta_command(meta_command: str) -> None:
    if meta_command == ".exit":
        sys.exit(0)
    else:
        return MetaCommandResult.META_COMMAND_UNRECOGNIZED_COMMAND

def prepare_statement(command: str, args: list[str], statement: Statement):
    if command == "insert":
        statement.statement_type = StatementType.STATEMENT_INSERT
        if not args[0].isdigit():
            return PrepareResult.PREPARE_SYNTAX_ERROR
        statement.row_to_insert = Row(id=int(args[0]), username=args[1], email=args[2])
        if len(args) != 3:
            return PrepareResult.PREPARE_SYNTAX_ERROR
        return PrepareResult.PREPARE_SUCCESS
    if command == "select":
        statement.statement_type = StatementType.STATEMENT_SELECT
        return PrepareResult.PREPARE_SUCCESS

    return PrepareResult.PREPARE_UNRECOGNIZED_STATEMENT

def execute_insert(statement: Statement, table: Table):
    if table.num_rows >= TABLE_MAX_ROWS:
        return ExecuteResult.EXECUTE_TABLE_FULL
    row_to_insert = statement.row_to_insert
    page, byte_offset = row_slot(table, table.num_rows)
    serialize_row(row_to_insert, page, byte_offset)
    table.num_rows += 1
    return ExecuteResult.EXECUTE_SUCCESS

def execute_select(statement: Statement, table: Table):
    for row_num in range(table.num_rows):
        page, byte_offset = row_slot(table, row_num)
        row = Row(id=0, username="", email="")
        deserialize_row(page, row, byte_offset)
        print(f"({row_num}: {row.id}, {row.username}, {row.email})")
    return ExecuteResult.EXECUTE_SUCCESS

def execute_statement(statement: Statement, table: Table):
    match statement.statement_type:
        case StatementType.STATEMENT_INSERT:
            return execute_insert(statement, table)
        case StatementType.STATEMENT_SELECT:
            return execute_select(statement, table)

def print_prompt():
    print("db > ", end="")

def main():
    table = Table()
    while True:
        print_prompt()
        arg = input()

        command = arg.split(" ")[0]
        args = arg.split(" ")[1:]

        if command[0] == ".":
            match do_meta_command(command):
                case MetaCommandResult.META_COMMAND_SUCCESS:
                    continue
                case MetaCommandResult.META_COMMAND_UNRECOGNIZED_COMMAND:
                    print(f"Unrecognized command \'{command}\'.")
                    continue

        statement = Statement()
        match prepare_statement(command, args, statement):
            case PrepareResult.PREPARE_SUCCESS:
                None
            case PrepareResult.PREPARE_SYNTAX_ERROR:
                print(f"Syntax error. Could not parse statement.")
                continue
            case PrepareResult.PREPARE_UNRECOGNIZED_STATEMENT:
                print(f"Unrecognized keyword at start of \'{command} {str.join(" ", args)}\'.")
                continue
        
        match execute_statement(statement, table):
            case ExecuteResult.EXECUTE_SUCCESS:
                print("Executed.")
            case ExecuteResult.EXECUTE_TABLE_FULL:
                print("Error: Table full.")
        
if __name__ == "__main__":
    main()