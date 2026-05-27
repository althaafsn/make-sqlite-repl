import sys
from enum import Enum
from dataclasses import dataclass


class MetaCommandResult(Enum):
    META_COMMAND_SUCCESS = 0
    META_COMMAND_UNRECOGNIZED_COMMAND = 1


class PrepareResult(Enum):
    PREPARE_SUCCESS = 0
    PREPARE_UNRECOGNIZED_STATEMENT = 1

class StatementType(Enum):
    STATEMENT_INSERT = 0
    STATEMENT_SELECT = 1

@dataclass
class Statement:
    statement_type: StatementType
    

def do_meta_command(meta_command: str) -> None:
    if meta_command == ".exit":
        sys.exit(0)
    else:
        print(f"Unrecognized command \'{meta_command}\'.")
        return 

def prepare_statement(command: str, statement: Statement):
    if command == "insert":
        statement.statement_type = StatementType.STATEMENT_INSERT
        return PrepareResult.PREPARE_SUCCESS
    if command == "select":
        statement.statement_type = StatementType.STATEMENT_SELECT
        return PrepareResult.PREPARE_SUCCESS

    return PrepareResult.PREPARE_UNRECOGNIZED_STATEMENT

def execute_statement(statement: Statement):
    match statement.statement_type:
        case StatementType.STATEMENT_INSERT:
            print("This is where we would do an insert.")
        case StatementType.STATEMENT_SELECT:
            print("This is where we would do a select.")


def print_prompt():
    print("db > ", end="")

def main():
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
                    print(f"Unrecognized command \'.{command}\'.")
                    continue

        statement = Statement(statement_type=None)
        match prepare_statement(command, statement):
            case PrepareResult.PREPARE_SUCCESS:
                None
            case PrepareResult.PREPARE_UNRECOGNIZED_STATEMENT:
                print(f"Unrecognized keyword at start of \'{command} {str.join(" ", args)}\'.")
                continue
        
        execute_statement(statement)
        print("Executed.")
        
if __name__ == "__main__":
    main()