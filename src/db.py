import sys
import os
from enum import Enum
from dataclasses import dataclass

from numpy import byte

@dataclass
class Row:
    id: int = 0
    username: str = ""
    email: str = ""

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
class Pager:
    file_descriptor: int
    file_length: int
    pages: list[bytearray | None]

@dataclass
class Table:
    num_rows: int
    pager: Pager

@dataclass
class Cursor:
    table: Table
    row_num: int
    end_of_table: bool

class MetaCommandResult(Enum):
    META_COMMAND_SUCCESS = 0
    META_COMMAND_UNRECOGNIZED_COMMAND = 1

class PrepareResult(Enum):
    PREPARE_SUCCESS = 0
    PREPARE_UNRECOGNIZED_STATEMENT = 1
    PREPARE_SYNTAX_ERROR = 2
    PREPARE_STRING_TOO_LONG = 3
    PREPARE_NEGATIVE_ID = 4

class ExecuteResult(Enum):
    EXECUTE_SUCCESS = 0
    EXECUTE_TABLE_FULL = 1

class StatementType(Enum):
    STATEMENT_INSERT = 0
    STATEMENT_SELECT = 1

@dataclass
class Statement:
    statement_type: StatementType = None
    row_to_insert: Row = None

def table_start(table: Table):
    return Cursor(table=table, row_num=0, end_of_table=table.num_rows == 0)

def table_end(table: Table):
    return Cursor(table=table, row_num=table.num_rows, end_of_table=True)   

def cursor_advance(cursor: Cursor):
    cursor.row_num += 1
    if cursor.row_num >= cursor.table.num_rows:
        cursor.end_of_table = True
    return


def pager_open(filename: str):
    file_descriptor = os.open(filename, os.O_RDWR | os.O_CREAT, 0o600)
    if file_descriptor == -1:
        print(f"Error: Could not open file \'{filename}\'.")
        sys.exit(1)
    file_length = os.fstat(file_descriptor).st_size
    pager = Pager(file_descriptor=file_descriptor, file_length=file_length, pages=[None] * TABLE_MAX_PAGES)
    return pager

def db_open(filename: str):
    pager = pager_open(filename)
    num_rows = (pager.file_length // PAGE_SIZE) * ROWS_PER_PAGE + (pager.file_length % PAGE_SIZE) // ROW_SIZE

    table = Table(pager=pager, num_rows=num_rows)
    # print(f"table.num_rows: {table.num_rows}")
    return table

def get_page(pager: Pager, page_num: int):
    if page_num > TABLE_MAX_PAGES:
        print(f"Tried to fetch page number out of bounds. {page_num} > {TABLE_MAX_PAGES}")
        sys.exit(1)

    if pager.pages[page_num] is None:
        pager.pages[page_num] = bytearray(PAGE_SIZE)
        # print(f"pager.pages[page_num]: {pager.pages[page_num]}")
        num_pages = pager.file_length // PAGE_SIZE
        # print("num_pages: ", num_pages)
        if pager.file_length % PAGE_SIZE:
            num_pages += 1
        if page_num <= num_pages:
            os.lseek(pager.file_descriptor, page_num * PAGE_SIZE, os.SEEK_SET)
            
            bytes_read = os.read(pager.file_descriptor, PAGE_SIZE)
            if bytes_read == -1:
                print(f"Error reading file. {os.strerror(os.errno)}")
                sys.exit(1)
            pager.pages[page_num] = bytearray(bytes_read)
            # print(f"pager.[page_num] after bytes_read: {pager.pages[page_num]}")

    return pager.pages[page_num]

def pager_flush(pager: Pager, page_num: int, size: int):
    if pager.pages[page_num] is None:
        print(f"Tried to flush null page.")
        sys.exit(1)
    
    offset = os.lseek(pager.file_descriptor, page_num * PAGE_SIZE, os.SEEK_SET)
    if offset == -1:
        print(f"Error seeking. {os.strerror(os.errno)}")
        sys.exit(1)
        
    result = os.write(pager.file_descriptor, pager.pages[page_num][:size])
    if result == -1:
        print(f"Error writing. {os.strerror(os.errno)}")
        sys.exit(1)
    return


def db_close(table: Table):
    pager = table.pager
    num_full_pages = table.num_rows // ROWS_PER_PAGE
    # print(f"num_full_pages: {num_full_pages}")

    for i in range(num_full_pages):
        if pager.pages[i] is None:
            continue
        pager_flush(pager, i, PAGE_SIZE)
        pager.pages[i] = None

    num_additional_rows = table.num_rows % ROWS_PER_PAGE
    # print(f"num_additional_rows: {num_additional_rows}")
    if num_additional_rows > 0:
        page_num = num_full_pages
        if pager.pages[page_num] is not None:
            pager_flush(pager, page_num, num_additional_rows * ROW_SIZE)
            pager.pages[page_num] = None
    
    result = os.close(pager.file_descriptor)
    if result == -1:
        print(f"Error closing file. {os.strerror(os.errno)}")
        sys.exit(1)
    
    return


def serialize_row(source: Row, destination: bytearray, byte_offset: int):
    base = byte_offset
    destination[base+ID_OFFSET:base+ID_OFFSET+ID_SIZE] = source.id.to_bytes(ID_SIZE, "little").ljust(ID_SIZE, b"\x00")
    destination[base+USERNAME_OFFSET:base+USERNAME_OFFSET+USERNAME_SIZE] = source.username.encode("utf-8").ljust(USERNAME_SIZE, b"\x00")
    destination[base+EMAIL_OFFSET:base+EMAIL_OFFSET+EMAIL_SIZE] = source.email.encode("utf-8").ljust(EMAIL_SIZE, b"\x00")
    return

def deserialize_row(source: bytearray, destination: Row, byte_offset: int):
    base = byte_offset
    destination.id = int.from_bytes(source[base+ID_OFFSET:base+ID_OFFSET+ID_SIZE].strip(b"\x00"), "little")
    destination.username = source[base+USERNAME_OFFSET:base+USERNAME_OFFSET+USERNAME_SIZE].strip(b"\x00").decode("utf-8")
    destination.email = source[base+EMAIL_OFFSET:base+EMAIL_OFFSET+EMAIL_SIZE].strip(b"\x00").decode("utf-8")
    return 

def cursor_value(cursor: Cursor):
    row_num = cursor.row_num
    page_num = row_num // ROWS_PER_PAGE
    page = get_page(cursor.table.pager, page_num)
    offset = row_num % ROWS_PER_PAGE
    byte_offset = offset * ROW_SIZE
    return page, byte_offset

def do_meta_command(meta_command: str, table: Table) -> None:
    if meta_command == ".exit":
        db_close(table)
        sys.exit(0)
    else:
        return MetaCommandResult.META_COMMAND_UNRECOGNIZED_COMMAND

def prepare_statement(command: str, args: list[str], statement: Statement):
    if command == "insert":
        statement.statement_type = StatementType.STATEMENT_INSERT
        if not args[0].isdigit():
            return PrepareResult.PREPARE_SYNTAX_ERROR
        if int(args[0]) < 0:
            return PrepareResult.PREPARE_NEGATIVE_ID
        if len(args[1]) > USERNAME_SIZE:
            return PrepareResult.PREPARE_STRING_TOO_LONG
        if len(args[2]) > EMAIL_SIZE:
            return PrepareResult.PREPARE_STRING_TOO_LONG
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
    cursor = table_end(table)
    page, byte_offset = cursor_value(cursor)
    serialize_row(row_to_insert, page, byte_offset)
    table.num_rows += 1
    return ExecuteResult.EXECUTE_SUCCESS

def execute_select(statement: Statement, table: Table):
    cursor = table_start(table)
    while not cursor.end_of_table:
        row = Row(id=0, username="", email="")
        page, byte_offset = cursor_value(cursor)
        deserialize_row(page, row, byte_offset)
        print(f"({row.id}, {row.username}, {row.email})")
        cursor_advance(cursor)
    return ExecuteResult.EXECUTE_SUCCESS

def execute_statement(statement: Statement, table: Table):
    match statement.statement_type:
        case StatementType.STATEMENT_INSERT:
            return execute_insert(statement, table)
        case StatementType.STATEMENT_SELECT:
            return execute_select(statement, table)

def print_prompt():
    print("db > ", end="")

def main(args: list[str]):
    if len(args) == 0:
        print("Must supply a database filename.")
        sys.exit(1)
    filename = args[0]
    table = db_open(filename)

    while True:
        print_prompt()
        arg = input()

        command = arg.split(" ")[0]
        args = arg.split(" ")[1:]

        if command[0] == ".":
            match do_meta_command(command, table):
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
            case PrepareResult.PREPARE_STRING_TOO_LONG:
                print(f"String is too long.")
                continue
            case PrepareResult.PREPARE_NEGATIVE_ID:
                print(f"ID must be positive.")
                continue
        
        match execute_statement(statement, table):
            case ExecuteResult.EXECUTE_SUCCESS:
                print("Executed.")
            case ExecuteResult.EXECUTE_TABLE_FULL:
                print("Error: Table full.")
        
if __name__ == "__main__":
    main(sys.argv[1:])