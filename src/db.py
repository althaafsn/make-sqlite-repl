import sys
import os
from enum import Enum
from dataclasses import dataclass

# =============================================================================
# Row schema
# =============================================================================

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

def serialize_row(source: Row, destination: bytearray, offset: int):
    destination[offset+ID_OFFSET:offset+ID_OFFSET+ID_SIZE] = source.id.to_bytes(ID_SIZE, "little").ljust(ID_SIZE, b"\x00")
    destination[offset+USERNAME_OFFSET:offset+USERNAME_OFFSET+USERNAME_SIZE] = source.username.encode("utf-8").ljust(USERNAME_SIZE, b"\x00")
    destination[offset+EMAIL_OFFSET:offset+EMAIL_OFFSET+EMAIL_SIZE] = source.email.encode("utf-8").ljust(EMAIL_SIZE, b"\x00")
    # print("destination after serialize_row: ", destination)
    return

def deserialize_row(source: bytearray, destination: Row):
    destination.id = int.from_bytes(source[ID_OFFSET:ID_OFFSET+ID_SIZE].strip(b"\x00"), "little")
    destination.username = source[USERNAME_OFFSET:USERNAME_OFFSET+USERNAME_SIZE].strip(b"\x00").decode("utf-8")
    destination.email = source[EMAIL_OFFSET:EMAIL_OFFSET+EMAIL_SIZE].strip(b"\x00").decode("utf-8")
    return 

# =============================================================================
# Layout constants
# =============================================================================


PAGE_SIZE = 4096
TABLE_MAX_PAGES = 100


# Common Node Header Layout
NODE_TYPE_SIZE = 1
NODE_TYPE_OFFSET = 0
IS_ROOT_SIZE = 1
IS_ROOT_OFFSET = NODE_TYPE_OFFSET + NODE_TYPE_SIZE
PARENT_POINTER_SIZE = 4
PARENT_POINTER_OFFSET = IS_ROOT_OFFSET + IS_ROOT_SIZE
COMMON_NODE_HEADER_SIZE = NODE_TYPE_SIZE + IS_ROOT_SIZE + PARENT_POINTER_SIZE

# Leaf Node Header Layout
LEAF_NODE_NUM_CELLS_SIZE = 4
LEAF_NODE_NUM_CELLS_OFFSET = COMMON_NODE_HEADER_SIZE
LEAF_NODE_NEXT_LEAF_SIZE = 4
LEAF_NODE_NEXT_LEAF_OFFSET = LEAF_NODE_NUM_CELLS_OFFSET + LEAF_NODE_NUM_CELLS_SIZE
LEAF_NODE_HEADER_SIZE = COMMON_NODE_HEADER_SIZE + LEAF_NODE_NUM_CELLS_SIZE + LEAF_NODE_NEXT_LEAF_SIZE

# Leaf Node Body Layout
LEAF_NODE_KEY_SIZE = 4
LEAF_NODE_KEY_OFFSET = 0
LEAF_NODE_VALUE_SIZE = ROW_SIZE
LEAF_NODE_VALUE_OFFSET = LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE
LEAF_NODE_CELL_SIZE = LEAF_NODE_KEY_SIZE + LEAF_NODE_VALUE_SIZE
LEAF_NODE_SPACE_FOR_CELLS = PAGE_SIZE - LEAF_NODE_HEADER_SIZE
LEAF_NODE_MAX_CELLS = LEAF_NODE_SPACE_FOR_CELLS // LEAF_NODE_CELL_SIZE

# Internal Node Header Layout
INTERNAL_NODE_NUM_KEYS_SIZE = 4
INTERNAL_NODE_NUM_KEYS_OFFSET = COMMON_NODE_HEADER_SIZE
INTERNAL_NODE_RIGHT_CHILD_SIZE = 4
INTERNAL_NODE_RIGHT_CHILD_OFFSET = INTERNAL_NODE_NUM_KEYS_OFFSET + INTERNAL_NODE_NUM_KEYS_SIZE
INTERNAL_NODE_HEADER_SIZE = INTERNAL_NODE_NUM_KEYS_SIZE + INTERNAL_NODE_RIGHT_CHILD_SIZE + COMMON_NODE_HEADER_SIZE

# Internal Node Body Layout
INTERNAL_NODE_KEY_SIZE = 4
INTERNAL_NODE_CHILD_SIZE = 4
INTERNAL_NODE_CELL_SIZE = INTERNAL_NODE_KEY_SIZE + INTERNAL_NODE_CHILD_SIZE

LEAF_NODE_RIGHT_SPLIT_COUNT = (LEAF_NODE_MAX_CELLS + 1) // 2
LEAF_NODE_LEFT_SPLIT_COUNT = LEAF_NODE_MAX_CELLS + 1 - LEAF_NODE_RIGHT_SPLIT_COUNT

# =============================================================================
# Types
# =============================================================================


@dataclass
class Pager:
    num_pages: int
    file_descriptor: int
    file_length: int
    pages: list[bytearray | None]

@dataclass
class Table:
    root_page_num: int
    pager: Pager

@dataclass
class Cursor:
    table: Table
    page_num: int
    cell_num: int
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
    EXECUTE_DUPLICATE_KEY = 2

class StatementType(Enum):
    STATEMENT_INSERT = 0
    STATEMENT_SELECT = 1

class NodeType(Enum):
    NODE_INTERNAL = 0
    NODE_LEAF = 1

@dataclass
class Statement:
    statement_type: StatementType = None
    row_to_insert: Row = None

# =============================================================================
# Pager
# =============================================================================


def pager_open(filename: str):
    file_descriptor = os.open(filename, os.O_RDWR | os.O_CREAT, 0o600)
    if file_descriptor == -1:
        print(f"Error: Could not open file \'{filename}\'.")
        sys.exit(1)
    file_length = os.fstat(file_descriptor).st_size
    if file_length % PAGE_SIZE != 0:
        print(f"Database file is not a whole number of pages. Corrupt file.")
        sys.exit(1)
    pager = Pager(num_pages=file_length // PAGE_SIZE, file_descriptor=file_descriptor, file_length=file_length, pages=[None] * TABLE_MAX_PAGES)
    return pager

def get_page(pager: Pager, page_num: int):

    # Convert page_num to 4 bytes little endian
    # Python only supports 8 byte integers, so we need to convert to 4 bytes
    page_num = int.from_bytes(int.to_bytes(page_num, 8, "little")[:4], "little")
    # print("page_num: ", page_num)
    
    if page_num > TABLE_MAX_PAGES:
        # print("Pager:", pager)
        # print("page_num: ", int.to_bytes(page_num, 8, "little"))
        # print("Page num:", int.from_bytes(int.to_bytes(page_num, 4, "little"), "little"))
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
            pager.pages[page_num] = bytearray(bytes_read).ljust(PAGE_SIZE, b"\x00")
            # print(f"pager.[page_num] after bytes_read: {pager.pages[page_num]}")

        if page_num >= pager.num_pages:
            pager.num_pages = page_num + 1

    return pager.pages[page_num]
    # return bytearray(PAGE_SIZE)

def pager_flush(pager: Pager, page_num: int):
    if pager.pages[page_num] is None:
        print(f"Tried to flush null page.")
        sys.exit(1)
    
    offset = os.lseek(pager.file_descriptor, page_num * PAGE_SIZE, os.SEEK_SET)
    if offset == -1:
        print(f"Error seeking. {os.strerror(os.errno)}")
        sys.exit(1)
        
    result = os.write(pager.file_descriptor, pager.pages[page_num][:PAGE_SIZE])
    if result == -1:
        print(f"Error writing. {os.strerror(os.errno)}")
        sys.exit(1)
    return

def get_unused_page_num(pager: Pager):
    return pager.num_pages

# =============================================================================
# Node accessors
# =============================================================================

def get_node_type(node: bytearray):
    return node[NODE_TYPE_OFFSET:NODE_TYPE_OFFSET+NODE_TYPE_SIZE]

def set_node_type(node: bytearray, node_type: NodeType):
    node[NODE_TYPE_OFFSET:NODE_TYPE_OFFSET+NODE_TYPE_SIZE] = node_type.value.to_bytes(NODE_TYPE_SIZE, "little")

def is_node_root(node: bytearray):
    return bool(int.from_bytes(node[IS_ROOT_OFFSET:IS_ROOT_OFFSET+IS_ROOT_SIZE], "little"))

def set_node_root(node: bytearray, is_root: bool):
    node[IS_ROOT_OFFSET:IS_ROOT_OFFSET+IS_ROOT_SIZE] = (int(is_root)).to_bytes(IS_ROOT_SIZE, "little")

def initialize_leaf_node(node: bytearray):
    set_node_type(node, NodeType.NODE_LEAF)
    set_node_root(node, False)
    node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = (0).to_bytes(LEAF_NODE_NEXT_LEAF_SIZE, "little")
    node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = (0).to_bytes(LEAF_NODE_NUM_CELLS_SIZE, "little")

def initialize_internal_node(node: bytearray):
    set_node_type(node, NodeType.NODE_INTERNAL)
    set_node_root(node, False)
    node[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE] = (0).to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")

def leaf_node_num_cells(node: bytearray):
    return node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE]

def leaf_node_cell(node: bytearray, cell_num: int):
    return node[LEAF_NODE_HEADER_SIZE + cell_num * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + (cell_num + 1) * LEAF_NODE_CELL_SIZE]

def leaf_node_key(node: bytearray, cell_num: int):
    return leaf_node_cell(node, cell_num)[LEAF_NODE_KEY_OFFSET:LEAF_NODE_KEY_OFFSET+LEAF_NODE_KEY_SIZE]

def leaf_node_value(node: bytearray, cell_num: int):
    return leaf_node_cell(node, cell_num)[LEAF_NODE_VALUE_OFFSET:LEAF_NODE_VALUE_OFFSET+LEAF_NODE_VALUE_SIZE]

def leaf_node_next_leaf(node: bytearray):
    return node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE]

def internal_node_num_keys(node: bytearray):
    return node[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE]

def internal_node_right_child(node: bytearray):
    return node[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET+INTERNAL_NODE_RIGHT_CHILD_SIZE]

def internal_node_cell(node: bytearray, cell_num: int):
    return node[INTERNAL_NODE_HEADER_SIZE + cell_num * INTERNAL_NODE_CELL_SIZE:INTERNAL_NODE_HEADER_SIZE + (cell_num + 1) * INTERNAL_NODE_CELL_SIZE]

def internal_node_child(node: bytearray, child_num: int):
    num_keys = int.from_bytes(internal_node_num_keys(node), "little")
    # print(f"num_keys: {num_keys}")
    if child_num > num_keys:
        print(f"Tried to access child_num {child_num} in internal node with {num_keys} keys.")
        sys.exit(1)
    elif child_num == num_keys:
        return internal_node_right_child(node)
    else:
        return internal_node_cell(node, child_num)

def internal_node_key(node: bytearray, key_num: int):
    return internal_node_cell(node, key_num)[INTERNAL_NODE_CHILD_SIZE:INTERNAL_NODE_CHILD_SIZE+INTERNAL_NODE_KEY_SIZE]

def get_node_max_key(node: bytearray):
    match int.from_bytes(get_node_type(node), "little"):
        case NodeType.NODE_INTERNAL.value:
            return int.from_bytes(internal_node_key(node, int.from_bytes(internal_node_num_keys(node), "little") - 1), "little")
        case NodeType.NODE_LEAF.value:
            return int.from_bytes(leaf_node_key(node, int.from_bytes(leaf_node_num_cells(node), "little") - 1), "little")

# =============================================================================
# B-Tree operations
# =============================================================================

def create_new_root(table: Table, right_child_page_num: int):
    # +  /*
    #   Handle splitting the root.
    #   Old root copied to new page, becomes left child.
    #   Address of right child passed in.
    #   Re-initialize root page to contain the new root node.
    #   New root node points to two children.
    #   */
    root = get_page(table.pager, table.root_page_num)
    right_child = get_page(table.pager, right_child_page_num)
    left_child_page_num = get_unused_page_num(table.pager)
    left_child = get_page(table.pager, left_child_page_num)

    # Left child has data copy of old root
    left_child[:PAGE_SIZE] = root[:PAGE_SIZE]
    set_node_root(left_child, False)

    # Root node is a new node with one key and two children
    initialize_internal_node(root)
    set_node_root(root, True)
    root[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE] = (1).to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")
    root[INTERNAL_NODE_HEADER_SIZE:INTERNAL_NODE_HEADER_SIZE+INTERNAL_NODE_RIGHT_CHILD_SIZE] = left_child_page_num.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")
    left_child_max_key = get_node_max_key(left_child)
    root[INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_CHILD_SIZE:INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_CHILD_SIZE + INTERNAL_NODE_KEY_SIZE] = left_child_max_key.to_bytes(INTERNAL_NODE_KEY_SIZE, "little")
    root[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET+INTERNAL_NODE_RIGHT_CHILD_SIZE] = right_child_page_num.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")


def leaf_node_find(table: Table, page_num: int, key: int):
    node = get_page(table.pager, page_num)
    # print(f"node: {node}")
    num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
    # print(f"num_cells: {num_cells}")
    min_index = 0
    one_past_max_index = num_cells
    while one_past_max_index > min_index:
        index = (min_index + one_past_max_index) // 2
        # print(f"index: {index}")
        key_at_index = int.from_bytes(leaf_node_key(node, index), "little")
        # print(f"key_at_index: {key_at_index}")
        if key_at_index == key:
            # print(f"Found key {key} at index {index}.")
            return Cursor(table=table, page_num=page_num, cell_num=index, end_of_table=index + 1 == num_cells)
        elif key_at_index < key:
            min_index = index + 1
        else:
            one_past_max_index = index
        
        # print(f"min_index: {min_index}")
        # print(f"one_past_max_index: {one_past_max_index}")
    # print(f"Key {key} not found, should be inserted at index {min_index}.")
    return Cursor(table=table, page_num=page_num, cell_num=min_index, end_of_table=min_index + 1 == num_cells)

def internal_node_find(table: Table, page_num: int, key: int):
    node = get_page(table.pager, page_num)
    num_keys = int.from_bytes(internal_node_num_keys(node), "little")

    # Binary search to find index of child to search
    min_index = 0
    max_index = num_keys
    
    while max_index > min_index:
        index = (min_index + max_index) // 2
        key_to_right = int.from_bytes(internal_node_key(node, index), "little")
        if key_to_right >= key:
            max_index = index
        else:
            min_index = index + 1
    
    child_num = internal_node_child(node, min_index)
    # print("child_num: ", int.from_bytes(child_num[:INTERNAL_NODE_CHILD_SIZE], "little"))
    child = get_page(table.pager, int.from_bytes(child_num[:INTERNAL_NODE_CHILD_SIZE], "little"))
    match int.from_bytes(get_node_type(child), "little"):
        case NodeType.NODE_INTERNAL.value:
            return internal_node_find(table, int.from_bytes(child_num, "little"), key)
        case NodeType.NODE_LEAF.value:
            return leaf_node_find(table, int.from_bytes(child_num, "little"), key)


def leaf_node_split_and_insert(cursor: Cursor, key: int, value: Row):
    #   Create a new node and move half the cells over.
    #   Insert the new value in one of the two nodes.
    #   Update parent or create a new parent.
    # print("Cursor: ", cursor)
    old_node = get_page(cursor.table.pager, cursor.page_num)
    # print("Page num:", cursor.page_num)
    new_page_num = get_unused_page_num(cursor.table.pager)
    # print("New page num: ", new_page_num)
    new_node = get_page(cursor.table.pager, new_page_num)
    # print("New node: ", new_node)
    initialize_leaf_node(new_node)
    new_node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = leaf_node_next_leaf(old_node)
    old_node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = new_page_num.to_bytes(LEAF_NODE_NEXT_LEAF_SIZE, "little")
    #   All existing keys plus new key should be divided
    #   evenly between old (left) and new (right) nodes.
    #   Starting from the right, move each key to correct position.
    for i in range(LEAF_NODE_MAX_CELLS, -1, -1):
        destination_node = None
        if i >= LEAF_NODE_LEFT_SPLIT_COUNT:
            destination_node = new_node
        else:
            destination_node = old_node

        index_within_node = i % LEAF_NODE_LEFT_SPLIT_COUNT

        if i == cursor.cell_num:
            serialize_row(value, destination_node, LEAF_NODE_HEADER_SIZE + index_within_node * LEAF_NODE_CELL_SIZE + LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE)
        elif i > cursor.cell_num:
            destination_node[LEAF_NODE_HEADER_SIZE + (index_within_node) * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + (index_within_node + 1) * LEAF_NODE_CELL_SIZE] = leaf_node_cell(old_node, i - 1)
        else:
            destination_node[LEAF_NODE_HEADER_SIZE + (index_within_node) * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + (index_within_node + 1) * LEAF_NODE_CELL_SIZE] = leaf_node_cell(old_node, i)

        # if i == LEAF_NODE_MAX_CELLS - 1:
        #     print(f"destination_node at index {i}: {destination_node}")

    # Update cell count on both leaf nodes
    old_node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = LEAF_NODE_LEFT_SPLIT_COUNT.to_bytes(LEAF_NODE_NUM_CELLS_SIZE, "little")
    new_node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = LEAF_NODE_RIGHT_SPLIT_COUNT.to_bytes(LEAF_NODE_NUM_CELLS_SIZE, "little")

    if is_node_root(old_node):
        create_new_root(cursor.table, new_page_num)
    else:
        print(f"Need to implement updating parent after splitting a leaf node.")
        sys.exit(1)
            


def leaf_node_insert(cursor: Cursor, key: int, value: Row):
    node = get_page(cursor.table.pager, cursor.page_num)
    # print("node: ", node)

    num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
    # print(f"num_cells: {num_cells}")
    if num_cells >= LEAF_NODE_MAX_CELLS:
        print("Leaf node is full. Splitting and inserting.")
        leaf_node_split_and_insert(cursor, key, value)
        # print("Table after splitting:", cursor.table)
        return
    
    # print("cursor before: ", cursor)
    # print("num_cells: ", num_cells)
    if cursor.cell_num < num_cells:
        for i in range(num_cells, cursor.cell_num, -1):
            node[LEAF_NODE_HEADER_SIZE + i * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + (i + 1) * LEAF_NODE_CELL_SIZE] = node[LEAF_NODE_HEADER_SIZE + (i - 1) * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + i * LEAF_NODE_CELL_SIZE]
    node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = (int.from_bytes(leaf_node_num_cells(node), "little") + 1).to_bytes(LEAF_NODE_NUM_CELLS_SIZE, "little")
    node[LEAF_NODE_HEADER_SIZE + LEAF_NODE_KEY_OFFSET + cursor.cell_num * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + LEAF_NODE_KEY_OFFSET + cursor.cell_num * LEAF_NODE_CELL_SIZE + LEAF_NODE_KEY_SIZE] = key.to_bytes(LEAF_NODE_KEY_SIZE, "little")
    serialize_row(value, node, LEAF_NODE_HEADER_SIZE + LEAF_NODE_VALUE_OFFSET + cursor.cell_num * LEAF_NODE_CELL_SIZE)
    # print("node: ", node)
    return

# Return the position of the given key.
# If the key is not found, return the position where it should be inserted.
def table_find(table: Table, key: int):
    root_page_num = table.root_page_num
    # print("Root page num:", root_page_num)
    root_node = get_page(table.pager, root_page_num)

    if int.from_bytes(get_node_type(root_node), "little") == NodeType.NODE_LEAF.value:
        return leaf_node_find(table, root_page_num, key)
    else:
        return internal_node_find(table, root_page_num, key)

def table_start(table: Table):
    # print(f"table: {table}")
    cursor = table_find(table, 0)
    # print(f"cursor: {cursor}")
    node = get_page(table.pager, cursor.page_num)
    num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
    cursor.end_of_table = num_cells == 0

    return cursor

def cursor_value(cursor: Cursor):
    page_num = cursor.page_num
    page = get_page(cursor.table.pager, page_num)
    return leaf_node_value(page, cursor.cell_num)

def cursor_advance(cursor: Cursor):
    page_num = cursor.page_num
    node = get_page(cursor.table.pager, page_num)
    cursor.cell_num += 1
    if cursor.cell_num >= int.from_bytes(leaf_node_num_cells(node), "little"):
        next_page_num = int.from_bytes(leaf_node_next_leaf(node), "little")
        if next_page_num == 0:
            cursor.end_of_table = True
        else:
            cursor.page_num = next_page_num
            cursor.cell_num = 0
    return

# =============================================================================
# Database lifecycle
# =============================================================================

def db_open(filename: str):
    pager = pager_open(filename)

    table = Table(pager=pager, root_page_num=0)
    if pager.num_pages == 0:
        root_node = get_page(pager, 0)
        initialize_leaf_node(root_node)
        set_node_root(root_node, True)

    return table

def db_close(table: Table):
    pager = table.pager
    for i in range(pager.num_pages):
        if pager.pages[i] is None:
            continue
        pager_flush(pager, i)
        pager.pages[i] = None
    
    result = os.close(pager.file_descriptor)
    if result == -1:
        print(f"Error closing file. {os.strerror(os.errno)}")
        sys.exit(1)
    
    return

# =============================================================================
# REPL
# =============================================================================

def print_constants():
    print("ROW_SIZE: ", ROW_SIZE)
    print("COMMON_NODE_HEADER_SIZE: ", COMMON_NODE_HEADER_SIZE)
    print("LEAF_NODE_HEADER_SIZE: ", LEAF_NODE_HEADER_SIZE)
    print("LEAF_NODE_CELL_SIZE: ", LEAF_NODE_CELL_SIZE)
    print("LEAF_NODE_SPACE_FOR_CELLS: ", LEAF_NODE_SPACE_FOR_CELLS)
    print("LEAF_NODE_MAX_CELLS: ", LEAF_NODE_MAX_CELLS)

def indent(level: int):
    for i in range(level):
        print("  ", end="")
    return

def print_tree(pager: Pager, page_num: int, indentation_level: int):
    node = get_page(pager, page_num)
    num_keys = None
    child = None

    match int.from_bytes(get_node_type(node), "little"):
        case NodeType.NODE_LEAF.value:
            num_keys = int.from_bytes(leaf_node_num_cells(node), "little")
            indent(indentation_level)
            print(f"- leaf (size {num_keys})")
            for i in range(num_keys):
                indent(indentation_level + 1)
                print(f"- {int.from_bytes(leaf_node_key(node, i), "little")}")
        case NodeType.NODE_INTERNAL.value:
            num_keys = int.from_bytes(internal_node_num_keys(node), "little")
            indent(indentation_level)
            print(f"- internal (size {num_keys})")
            for i in range(num_keys):
                child = int.from_bytes(internal_node_child(node, i)[:INTERNAL_NODE_CHILD_SIZE], "little")
                print_tree(pager, child, indentation_level + 1)
                indent(indentation_level + 1)
                print(f"- key {int.from_bytes(internal_node_key(node, i), "little")}")
            child = int.from_bytes(internal_node_right_child(node), "little")
            print_tree(pager, child, indentation_level + 1)
    return


def do_meta_command(meta_command: str, table: Table) -> None:
    if meta_command == ".exit":
        db_close(table)
        sys.exit(0)
    elif meta_command == ".constants":
        print_constants()
        return MetaCommandResult.META_COMMAND_SUCCESS
    elif meta_command == ".btree":
        print_tree(table.pager, 0, 0)
        return MetaCommandResult.META_COMMAND_SUCCESS
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
    node = get_page(table.pager, table.root_page_num)
    num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
    row_to_insert = statement.row_to_insert
    key_to_insert = row_to_insert.id
    cursor = table_find(table, key_to_insert)
    if cursor.cell_num < num_cells:
        key_at_index = int.from_bytes(leaf_node_key(node, cursor.cell_num), "little")
        if key_at_index == key_to_insert:
            return ExecuteResult.EXECUTE_DUPLICATE_KEY
    leaf_node_insert(cursor, row_to_insert.id, row_to_insert)
    return ExecuteResult.EXECUTE_SUCCESS

def execute_select(statement: Statement, table: Table):
    cursor = table_start(table)
    while not cursor.end_of_table:
        row = Row(id=0, username="", email="")
        deserialize_row(cursor_value(cursor), row)
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
    # if len(args) == 0:
    #     print("Must supply a database filename.")
    #     sys.exit(1)
    # filename = args[0]
    filename = "db.db"
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
            case ExecuteResult.EXECUTE_DUPLICATE_KEY:
                print("Error: Duplicate key.")
        
if __name__ == "__main__":
    main(sys.argv[1:])