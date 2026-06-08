import json
import os
from collections import defaultdict
from contextlib import redirect_stdout
from dataclasses import dataclass
from enum import Enum
from io import StringIO


class DbFatalError(Exception):
    """Raised instead of sys.exit so the browser tab never freezes."""

# =============================================================================
# Row schema
# =============================================================================

@dataclass
class Row:
    id: int = 0
    username: str = ""
    email: str = ""

UINT32_SIZE = 4  # sizeof(uint32_t) in C

COLUMN_USERNAME_SIZE = 32
COLUMN_EMAIL_SIZE = 255

ID_SIZE = UINT32_SIZE
USERNAME_SIZE = COLUMN_USERNAME_SIZE + 1
EMAIL_SIZE = COLUMN_EMAIL_SIZE + 1
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
INVALID_PAGE_NUM = 4294967295


# Common Node Header Layout
NODE_TYPE_SIZE = 1
NODE_TYPE_OFFSET = 0
IS_ROOT_SIZE = 1
IS_ROOT_OFFSET = NODE_TYPE_OFFSET + NODE_TYPE_SIZE
PARENT_POINTER_SIZE = UINT32_SIZE
PARENT_POINTER_OFFSET = IS_ROOT_OFFSET + IS_ROOT_SIZE
COMMON_NODE_HEADER_SIZE = NODE_TYPE_SIZE + IS_ROOT_SIZE + PARENT_POINTER_SIZE

# Leaf Node Header Layout
LEAF_NODE_NUM_CELLS_SIZE = UINT32_SIZE
LEAF_NODE_NUM_CELLS_OFFSET = COMMON_NODE_HEADER_SIZE
LEAF_NODE_NEXT_LEAF_SIZE = UINT32_SIZE
LEAF_NODE_NEXT_LEAF_OFFSET = LEAF_NODE_NUM_CELLS_OFFSET + LEAF_NODE_NUM_CELLS_SIZE
LEAF_NODE_HEADER_SIZE = COMMON_NODE_HEADER_SIZE + LEAF_NODE_NUM_CELLS_SIZE + LEAF_NODE_NEXT_LEAF_SIZE

# Leaf Node Body Layout
LEAF_NODE_KEY_SIZE = UINT32_SIZE
LEAF_NODE_KEY_OFFSET = 0
LEAF_NODE_VALUE_SIZE = ROW_SIZE
LEAF_NODE_VALUE_OFFSET = LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE
LEAF_NODE_CELL_SIZE = LEAF_NODE_KEY_SIZE + LEAF_NODE_VALUE_SIZE
LEAF_NODE_SPACE_FOR_CELLS = PAGE_SIZE - LEAF_NODE_HEADER_SIZE
LEAF_NODE_MAX_CELLS = 3

# Internal Node Header Layout
INTERNAL_NODE_NUM_KEYS_SIZE = UINT32_SIZE
INTERNAL_NODE_NUM_KEYS_OFFSET = COMMON_NODE_HEADER_SIZE
INTERNAL_NODE_RIGHT_CHILD_SIZE = UINT32_SIZE
INTERNAL_NODE_RIGHT_CHILD_OFFSET = INTERNAL_NODE_NUM_KEYS_OFFSET + INTERNAL_NODE_NUM_KEYS_SIZE
INTERNAL_NODE_HEADER_SIZE = INTERNAL_NODE_NUM_KEYS_SIZE + INTERNAL_NODE_RIGHT_CHILD_SIZE + COMMON_NODE_HEADER_SIZE


# Internal Node Body Layout
INTERNAL_NODE_CHILD_SIZE = UINT32_SIZE
INTERNAL_NODE_KEY_SIZE = UINT32_SIZE
INTERNAL_NODE_CHILD_OFFSET = 0
INTERNAL_NODE_KEY_OFFSET = INTERNAL_NODE_CHILD_SIZE
INTERNAL_NODE_CELL_SIZE = INTERNAL_NODE_CHILD_SIZE + INTERNAL_NODE_KEY_SIZE
INTERNAL_NODE_MAX_CELLS = 3

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
    META_COMMAND_EXIT = 2

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
        raise DbFatalError(f"Could not open file '{filename}'.")
    file_length = os.fstat(file_descriptor).st_size
    if file_length % PAGE_SIZE != 0:
        raise DbFatalError("Database file is not a whole number of pages. Corrupt file.")
    pager = Pager(num_pages=file_length // PAGE_SIZE, file_descriptor=file_descriptor, file_length=file_length, pages=[None] * TABLE_MAX_PAGES)
    return pager

def get_page(pager: Pager, page_num: int):
    if page_num > TABLE_MAX_PAGES:
        # print("Pager:", pager)
        # print("page_num: ", int.to_bytes(page_num, 8, "little"))
        # print("Page num:", int.from_bytes(int.to_bytes(page_num, 4, "little"), "little"))
        raise DbFatalError(f"Tried to fetch page number out of bounds. {page_num} > {TABLE_MAX_PAGES}")

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
                raise DbFatalError(f"Error reading file. {os.strerror(os.errno)}")
            pager.pages[page_num] = bytearray(bytes_read).ljust(PAGE_SIZE, b"\x00")
            # print(f"pager.[page_num] after bytes_read: {pager.pages[page_num]}")

        if page_num >= pager.num_pages:
            pager.num_pages = page_num + 1

    return pager.pages[page_num]
    # return bytearray(PAGE_SIZE)

def pager_flush(pager: Pager, page_num: int):
    if pager.pages[page_num] is None:
        raise DbFatalError("Tried to flush null page.")

    offset = os.lseek(pager.file_descriptor, page_num * PAGE_SIZE, os.SEEK_SET)
    if offset == -1:
        raise DbFatalError(f"Error seeking. {os.strerror(os.errno)}")

    result = os.write(pager.file_descriptor, pager.pages[page_num][:PAGE_SIZE])
    if result == -1:
        raise DbFatalError(f"Error writing. {os.strerror(os.errno)}")
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

def node_parent(node: bytearray):
    return node[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET+PARENT_POINTER_SIZE]

def initialize_leaf_node(node: bytearray):
    set_node_type(node, NodeType.NODE_LEAF)
    set_node_root(node, False)
    node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = (0).to_bytes(LEAF_NODE_NEXT_LEAF_SIZE, "little")
    node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = (0).to_bytes(LEAF_NODE_NUM_CELLS_SIZE, "little")

def initialize_internal_node(node: bytearray):
    set_node_type(node, NodeType.NODE_INTERNAL)
    set_node_root(node, False)
    node[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE] = (0).to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")
    node[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET+INTERNAL_NODE_RIGHT_CHILD_SIZE] = INVALID_PAGE_NUM.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")

def leaf_node_num_cells(node: bytearray):
    return node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE]

def leaf_node_cell(node: bytearray, cell_num: int):
    return node[LEAF_NODE_HEADER_SIZE + cell_num * LEAF_NODE_CELL_SIZE:LEAF_NODE_HEADER_SIZE + (cell_num + 1) * LEAF_NODE_CELL_SIZE]

def leaf_node_key(node: bytearray, cell_num: int):
    return node[LEAF_NODE_HEADER_SIZE + cell_num * LEAF_NODE_CELL_SIZE + LEAF_NODE_KEY_OFFSET:LEAF_NODE_HEADER_SIZE + (cell_num) * LEAF_NODE_CELL_SIZE + LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE]

def leaf_node_value(node: bytearray, cell_num: int):
    return node[LEAF_NODE_HEADER_SIZE + cell_num * LEAF_NODE_CELL_SIZE + LEAF_NODE_VALUE_OFFSET:LEAF_NODE_HEADER_SIZE + (cell_num) * LEAF_NODE_CELL_SIZE + LEAF_NODE_VALUE_OFFSET + LEAF_NODE_VALUE_SIZE]

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
        raise DbFatalError(f"Tried to access child_num {child_num} in internal node with {num_keys} keys.")
    elif child_num == num_keys:
        return internal_node_right_child(node)
    else:
        return internal_node_cell(node, child_num)

def internal_node_key(node: bytearray, key_num: int):
    offset = INTERNAL_NODE_HEADER_SIZE + key_num * INTERNAL_NODE_CELL_SIZE + INTERNAL_NODE_KEY_OFFSET
    return node[offset:offset + INTERNAL_NODE_KEY_SIZE]

def update_internal_node_key(node: bytearray, old_key: int, new_key: int):
    num_keys = int.from_bytes(internal_node_num_keys(node), "little")
    old_child_index = internal_node_find_child(node, old_key)
    if old_child_index >= num_keys:
        return
    offset = INTERNAL_NODE_HEADER_SIZE + old_child_index * INTERNAL_NODE_CELL_SIZE + INTERNAL_NODE_KEY_OFFSET
    node[offset:offset + INTERNAL_NODE_KEY_SIZE] = new_key.to_bytes(INTERNAL_NODE_KEY_SIZE, "little")

def get_node_max_key(table: Table, page_num: int):
    node = get_page(table.pager, page_num)
    match int.from_bytes(get_node_type(node), "little"):
        case NodeType.NODE_INTERNAL.value:
            right_child_page_num = int.from_bytes(internal_node_right_child(node), "little")
            if right_child_page_num == INVALID_PAGE_NUM:
                num_keys = int.from_bytes(internal_node_num_keys(node), "little")
                return int.from_bytes(internal_node_key(node, num_keys - 1), "little")
            return get_node_max_key(table, right_child_page_num)
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

    if int.from_bytes(get_node_type(root), "little") == NodeType.NODE_INTERNAL.value:
        initialize_internal_node(right_child)
        initialize_internal_node(left_child)

    # Left child has data copy of old root
    left_child[:PAGE_SIZE] = root[:PAGE_SIZE]
    set_node_root(left_child, False)

    if int.from_bytes(get_node_type(root), "little") == NodeType.NODE_INTERNAL.value:
        child = None
        for i in range(int.from_bytes(internal_node_num_keys(left_child), "little")):
            child = get_page(table.pager, int.from_bytes(internal_node_child(left_child, i)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little"))
            child[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = left_child_page_num.to_bytes(PARENT_POINTER_SIZE, "little")
        child = get_page(table.pager, int.from_bytes(internal_node_right_child(left_child), "little"))
        child[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = left_child_page_num.to_bytes(PARENT_POINTER_SIZE, "little")

    # Root node is a new node with one key and two children
    initialize_internal_node(root)
    set_node_root(root, True)
    root[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE] = (1).to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")
    root[INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE] = left_child_page_num.to_bytes(INTERNAL_NODE_CHILD_SIZE, "little")
    left_child_max_key = get_node_max_key(table, left_child_page_num)
    root[INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_KEY_OFFSET:INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_KEY_OFFSET + INTERNAL_NODE_KEY_SIZE] = left_child_max_key.to_bytes(INTERNAL_NODE_KEY_SIZE, "little")
    root[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET+INTERNAL_NODE_RIGHT_CHILD_SIZE] = right_child_page_num.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")
    left_child[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = table.root_page_num.to_bytes(PARENT_POINTER_SIZE, "little")
    right_child[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = table.root_page_num.to_bytes(PARENT_POINTER_SIZE, "little")


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

def internal_node_find_child(node: bytearray, key: int):
    # Return the index of the child node that should contain the given key.
    num_keys = int.from_bytes(internal_node_num_keys(node), "little")

    # Binary search
    min_index = 0
    max_index = num_keys
    
    while max_index != min_index:
        index = (min_index + max_index) // 2
        key_to_right = int.from_bytes(internal_node_key(node, index), "little")
        if key_to_right >= key:
            max_index = index
        else:
            min_index = index + 1

    return min_index


def internal_node_find(table: Table, page_num: int, key: int):
    node = get_page(table.pager, page_num)
    
    child_index = internal_node_find_child(node, key)
    child_num = internal_node_child(node, child_index)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE]
    # print("child_num: ", int.from_bytes(child_num[:INTERNAL_NODE_CHILD_SIZE], "little"))
    child = get_page(table.pager, int.from_bytes(child_num, "little"))
    # print("child num: ", child_num[:INTERNAL_NODE_CHILD_SIZE])
    match int.from_bytes(get_node_type(child), "little"):
        case NodeType.NODE_INTERNAL.value:
            return internal_node_find(table, int.from_bytes(child_num, "little"), key)
        case NodeType.NODE_LEAF.value:
            return leaf_node_find(table, int.from_bytes(child_num, "little"), key)

def internal_node_split_and_insert(table: Table, parent_page_num: int, child_page_num: int):
    old_page_num = parent_page_num
    old_node = get_page(table.pager, old_page_num)
    old_max = get_node_max_key(table, old_page_num)

    child = get_page(table.pager, child_page_num)
    child_max = get_node_max_key(table, child_page_num)

    new_page_num = get_unused_page_num(table.pager)

    """
    Declaring a flag before updating pointers which
    records whether this operation involves splitting the root -
    if it does, we will insert our newly created node during
    the step where the table's new root is created. If it does
    not, we have to insert the newly created node into its parent
    after the old node's keys have been transferred over. We are not
    able to do this if the newly created node's parent is not a newly
    initialized root node, because in that case its parent may have existing
    keys aside from our old node which we are splitting. If that is true, we
    need to find a place for our newly created node in its parent, and we
    cannot insert it at the correct index if it does not yet have any keys
    """

    splitting_root = is_node_root(old_node)

    parent = None
    new_node = None

    if splitting_root:
        create_new_root(table, new_page_num)
        parent = get_page(table.pager, table.root_page_num)

        # If we are splitting the root, we need to update old_node to point
        # to the new root's left child, new_page_num will already point to
        # the new root's right child
        old_page_num = int.from_bytes(internal_node_child(parent, 0)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little")
        old_node = get_page(table.pager, old_page_num)
    else:
        parent = get_page(table.pager, int.from_bytes(node_parent(old_node), "little"))
        new_node = get_page(table.pager, new_page_num)
        initialize_internal_node(new_node)

    old_num_keys = int.from_bytes(internal_node_num_keys(old_node), "little")

    cur_page_num = int.from_bytes(internal_node_right_child(old_node), "little")
    cur = get_page(table.pager, cur_page_num)

    # First put right child into new node and set right child of old node to invalid page number
    internal_node_insert(table, new_page_num, cur_page_num)
    cur[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = new_page_num.to_bytes(PARENT_POINTER_SIZE, "little")
    old_node[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET + INTERNAL_NODE_RIGHT_CHILD_SIZE] = INVALID_PAGE_NUM.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")

    # For each key until you get to the middle key, move the key and the child to the new node
    for i in range(INTERNAL_NODE_MAX_CELLS - 1, INTERNAL_NODE_MAX_CELLS // 2, -1):
        cur_page_num = int.from_bytes(internal_node_child(old_node, i)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little")
        cur = get_page(table.pager, cur_page_num)

        internal_node_insert(table, new_page_num, cur_page_num)
        cur[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = new_page_num.to_bytes(PARENT_POINTER_SIZE, "little")

        old_num_keys -= 1
        old_node[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET + INTERNAL_NODE_NUM_KEYS_SIZE] = old_num_keys.to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")

    """
    Set child before middle key, which is now the highest key, to be node's right child,
    and decrement number of keys
    """
    old_node[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET + INTERNAL_NODE_RIGHT_CHILD_SIZE] = int.from_bytes(internal_node_child(old_node, old_num_keys - 1)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little").to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")
    old_num_keys -= 1
    old_node[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET + INTERNAL_NODE_NUM_KEYS_SIZE] = old_num_keys.to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")

    """
    Determine which of the two nodes after the split should contain the child to be inserted,
    and insert the child
    """

    max_after_split = get_node_max_key(table, old_page_num)

    destination_page_num = None
    if child_max < max_after_split:
        destination_page_num = old_page_num
    else:
        destination_page_num = new_page_num

    internal_node_insert(table, destination_page_num, child_page_num)
    child[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = destination_page_num.to_bytes(PARENT_POINTER_SIZE, "little")

    update_internal_node_key(parent, old_max, get_node_max_key(table, old_page_num))

    if not splitting_root:
        internal_node_insert(table, int.from_bytes(node_parent(old_node), "little"), new_page_num)
        new_node[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = int.from_bytes(node_parent(old_node), "little").to_bytes(PARENT_POINTER_SIZE, "little")


def internal_node_insert(table: Table, parent_page_num: int, child_page_num: int):
    # Add a new child/key pair to parent that corresponds to the child

    parent = get_page(table.pager, parent_page_num)
    child = get_page(table.pager, child_page_num)
    child_max_key = get_node_max_key(table, child_page_num)
    index = internal_node_find_child(parent, child_max_key)

    original_num_keys = int.from_bytes(internal_node_num_keys(parent), "little")

    if original_num_keys >= INTERNAL_NODE_MAX_CELLS:
        internal_node_split_and_insert(table, parent_page_num, child_page_num)
        return

    right_child_page_num = int.from_bytes(internal_node_right_child(parent), "little")
    
    # An internal node with a right child of INVALID_PAGE_NUM is empty
    if right_child_page_num == INVALID_PAGE_NUM:
        parent[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET + INTERNAL_NODE_RIGHT_CHILD_SIZE] = child_page_num.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")
        return
    
    right_child = get_page(table.pager, right_child_page_num)

    # If we are already +  If we are already at the max number of cells for a node, we cannot increment
    # before splitting. Incrementing without inserting a new key/child pair
    # and immediately calling internal_node_split_and_insert has the effect
    # of creating a new key at (max_cells + 1) with an uninitialized value
    parent[INTERNAL_NODE_NUM_KEYS_OFFSET:INTERNAL_NODE_NUM_KEYS_OFFSET+INTERNAL_NODE_NUM_KEYS_SIZE] = (original_num_keys + 1).to_bytes(INTERNAL_NODE_NUM_KEYS_SIZE, "little")

    if child_max_key > get_node_max_key(table, right_child_page_num):
        # Replace right child
        offset = INTERNAL_NODE_HEADER_SIZE + original_num_keys * INTERNAL_NODE_CELL_SIZE
        parent[offset + INTERNAL_NODE_CHILD_OFFSET:offset + INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE] = right_child_page_num.to_bytes(INTERNAL_NODE_CHILD_SIZE, "little")
        parent[offset + INTERNAL_NODE_KEY_OFFSET:offset + INTERNAL_NODE_KEY_OFFSET + INTERNAL_NODE_KEY_SIZE] = get_node_max_key(table, right_child_page_num).to_bytes(INTERNAL_NODE_KEY_SIZE, "little")
        parent[INTERNAL_NODE_RIGHT_CHILD_OFFSET:INTERNAL_NODE_RIGHT_CHILD_OFFSET + INTERNAL_NODE_RIGHT_CHILD_SIZE] = child_page_num.to_bytes(INTERNAL_NODE_RIGHT_CHILD_SIZE, "little")
    else:
        # Make room for the new cell
        for i in range(original_num_keys, index, -1):
            parent[INTERNAL_NODE_HEADER_SIZE + i * INTERNAL_NODE_CELL_SIZE:INTERNAL_NODE_HEADER_SIZE + (i + 1) * INTERNAL_NODE_CELL_SIZE] = parent[INTERNAL_NODE_HEADER_SIZE + (i - 1) * INTERNAL_NODE_CELL_SIZE:INTERNAL_NODE_HEADER_SIZE + i * INTERNAL_NODE_CELL_SIZE]
        offset = INTERNAL_NODE_HEADER_SIZE + index * INTERNAL_NODE_CELL_SIZE
        parent[offset + INTERNAL_NODE_CHILD_OFFSET:offset + INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE] = child_page_num.to_bytes(INTERNAL_NODE_CHILD_SIZE, "little")
        parent[offset + INTERNAL_NODE_KEY_OFFSET:offset + INTERNAL_NODE_KEY_OFFSET + INTERNAL_NODE_KEY_SIZE] = child_max_key.to_bytes(INTERNAL_NODE_KEY_SIZE, "little")
        
def leaf_node_split_and_insert(cursor: Cursor, key: int, value: Row):
    #   Create a new node and move half the cells over.
    #   Insert the new value in one of the two nodes.
    #   Update parent or create a new parent.
    # print("Cursor: ", cursor)
    old_node = get_page(cursor.table.pager, cursor.page_num)
    old_max = get_node_max_key(cursor.table, cursor.page_num)
    # print("Page num:", cursor.page_num)
    new_page_num = get_unused_page_num(cursor.table.pager)
    # print("New page num: ", new_page_num)
    new_node = get_page(cursor.table.pager, new_page_num)
    # print("New node: ", new_node)
    initialize_leaf_node(new_node)
    new_node[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE] = old_node[PARENT_POINTER_OFFSET:PARENT_POINTER_OFFSET + PARENT_POINTER_SIZE]
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
            cell_offset = LEAF_NODE_HEADER_SIZE + index_within_node * LEAF_NODE_CELL_SIZE
            destination_node[cell_offset + LEAF_NODE_KEY_OFFSET:cell_offset + LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE] = key.to_bytes(LEAF_NODE_KEY_SIZE, "little")
            serialize_row(value, destination_node, cell_offset + LEAF_NODE_VALUE_OFFSET)
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
        parent_page_num = int.from_bytes(node_parent(old_node), "little")
        new_max = get_node_max_key(cursor.table, cursor.page_num)
        parent = get_page(cursor.table.pager, parent_page_num)

        update_internal_node_key(parent, old_max, new_max)
        internal_node_insert(cursor.table, parent_page_num, new_page_num)
        return
            


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
        raise DbFatalError(f"Error closing file. {os.strerror(os.errno)}")
    
    return

# =============================================================================
# REPL
# =============================================================================

def print_help():
    print("B-Tree Database — command reference")
    print("─────────────────────────────────")
    print("  insert <id> <username> <email>   Add a row (id is the B-Tree key)")
    print("  select                           Print all rows in key order")
    print("")
    print("  .btree                           Print tree + refresh visualizer")
    print("  .constants                       Show page layout constants")
    print("  .help                            Show this guide")
    print("  .exit                            Close the database")
    print("")
    print("Tips:")
    print("  • Click a node in the visualizer to inspect its memory map")
    print("  • Each leaf page holds up to 3 keys — more inserts cause splits")
    print("  • Use Import / Export .db in the header to save your work")
    print("")
    print("Example:  insert 1 alice alice@example.com")

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
                print(f"- {int.from_bytes(leaf_node_key(node, i), 'little')}")
        case NodeType.NODE_INTERNAL.value:
            num_keys = int.from_bytes(internal_node_num_keys(node), "little")
            indent(indentation_level)
            print(f"- internal (size {num_keys})")
            for i in range(num_keys):
                child = int.from_bytes(internal_node_child(node, i)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little")
                print_tree(pager, child, indentation_level + 1)
                indent(indentation_level + 1)
                print(f"- key {int.from_bytes(internal_node_key(node, i), 'little')}")
            child = int.from_bytes(internal_node_right_child(node), "little")
            print_tree(pager, child, indentation_level + 1)
            
    return

def print_pager(pager: Pager):
    # print("Pages in pager: ", pager.pages)
    for page in pager.pages:
        if page is None:
            continue
        # Print leaf page
        if int.from_bytes(get_node_type(page), "little") == NodeType.NODE_LEAF.value:
            # Print common Node Header Data
            print(page[:COMMON_NODE_HEADER_SIZE])

            # Print leaf node header
            print(page[COMMON_NODE_HEADER_SIZE:LEAF_NODE_HEADER_SIZE])

            # Print leaf node cells
            for i in range(LEAF_NODE_MAX_CELLS):
                offset = LEAF_NODE_HEADER_SIZE + i * LEAF_NODE_CELL_SIZE
                # Print key
                print("THIS IS THE KEY: ", page[offset + LEAF_NODE_KEY_OFFSET - 4:offset + LEAF_NODE_KEY_OFFSET + LEAF_NODE_KEY_SIZE + 4])
                # Print row, id
                # print("THIS IS THE ID: ", page[offset + LEAF_NODE_VALUE_OFFSET:offset + LEAF_NODE_VALUE_OFFSET + ID_SIZE])
                print("THIS IS THE USERNAME: ", page[offset + LEAF_NODE_VALUE_OFFSET + ID_SIZE:offset + LEAF_NODE_VALUE_OFFSET + ID_SIZE + 8])
                # print("THIS IS THE EMAIL: ", page[offset + LEAF_NODE_VALUE_OFFSET + ID_SIZE + USERNAME_SIZE:offset + LEAF_NODE_VALUE_OFFSET + ID_SIZE + USERNAME_SIZE + 32])

        # # Print internal page
        # if int.from_bytes(get_node_type(page), "little") == NodeType.NODE_INTERNAL.value:
        #     num_keys = int.from_bytes(internal_node_num_keys(page), "little")
        #     print(f"Internal page {page_num}: {page}")
        #     for i in range(num_keys):
        #         child = int.from_bytes(internal_node_child(page, i)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE], "little")
        #         print_tree(pager, child, indentation_level + 1)
        #         indent(indentation_level + 1)
        #         print(f"  Key {int.from_bytes(internal_node_key(page, i), "little")}")
        #     return

    return


def do_meta_command(meta_command: str, table: Table):
    if meta_command == ".exit":
        db_close(table)
        print("Goodbye.")
        return MetaCommandResult.META_COMMAND_EXIT
    elif meta_command == ".constants":
        print_constants()
        return MetaCommandResult.META_COMMAND_SUCCESS
    elif meta_command == ".help":
        print_help()
        return MetaCommandResult.META_COMMAND_SUCCESS
    elif meta_command == ".btree":
        print("Tree:")
        print_tree(table.pager, 0, 0)
        # print_pager(table.pager)
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
        if len(args[1]) > COLUMN_USERNAME_SIZE:
            return PrepareResult.PREPARE_STRING_TOO_LONG
        if len(args[2]) > COLUMN_EMAIL_SIZE:
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
    row_to_insert = statement.row_to_insert
    key_to_insert = row_to_insert.id
    cursor = table_find(table, key_to_insert)
    node = get_page(table.pager, cursor.page_num)
    num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
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

# =============================================================================
# Browser / Pyodide API
# =============================================================================

_table: Table | None = None
_database_path = "/db.db"
H_SPACING = 280
V_SPACING = 180


def init_database(path: str = "/db.db") -> str:
    """Open or create the database at the given Pyodide virtual-FS path."""
    global _table, _database_path
    _database_path = path
    _table = db_open(path)
    return ""


def flush_database() -> str:
    """Persist dirty pages without closing the file descriptor."""
    if _table is None:
        return ""
    pager = _table.pager
    for i in range(pager.num_pages):
        if pager.pages[i] is not None:
            pager_flush(pager, i)
    return ""


def _run_command(table: Table, arg: str) -> MetaCommandResult | None:
    command = arg.split(" ")[0]
    args = arg.split(" ")[1:]

    if command.startswith("."):
        match do_meta_command(command, table):
            case MetaCommandResult.META_COMMAND_SUCCESS:
                return None
            case MetaCommandResult.META_COMMAND_EXIT:
                return MetaCommandResult.META_COMMAND_EXIT
            case MetaCommandResult.META_COMMAND_UNRECOGNIZED_COMMAND:
                print(f"Unrecognized command '{command}'.")
                return None

    statement = Statement()
    match prepare_statement(command, args, statement):
        case PrepareResult.PREPARE_SUCCESS:
            pass
        case PrepareResult.PREPARE_SYNTAX_ERROR:
            print("Syntax error. Could not parse statement.")
            return None
        case PrepareResult.PREPARE_UNRECOGNIZED_STATEMENT:
            print(f"Unrecognized keyword at start of '{command} {' '.join(args)}'.")
            return None
        case PrepareResult.PREPARE_STRING_TOO_LONG:
            print("String is too long.")
            return None
        case PrepareResult.PREPARE_NEGATIVE_ID:
            print("ID must be positive.")
            return None

    match execute_statement(statement, table):
        case ExecuteResult.EXECUTE_SUCCESS:
            print("Executed.")
        case ExecuteResult.EXECUTE_TABLE_FULL:
            print("Error: Table full.")
        case ExecuteResult.EXECUTE_DUPLICATE_KEY:
            print("Error: Duplicate key.")
    return None


def execute_command(cmd: str) -> str:
    """Parse and run one SQL or meta-command; return captured stdout as a string."""
    global _table
    buffer = StringIO()
    try:
        with redirect_stdout(buffer):
            if _table is None:
                print("Database not open. Call init_database() first.")
                return buffer.getvalue()

            arg = cmd.strip()
            if not arg:
                return ""

            result = _run_command(_table, arg)
            if result == MetaCommandResult.META_COMMAND_EXIT:
                _table = None
    except DbFatalError as exc:
        buffer.write(str(exc))
        if not str(exc).endswith("\n"):
            buffer.write("\n")
    return buffer.getvalue()


def _child_page_num(node: bytearray, child_num: int) -> int:
    child = internal_node_child(node, child_num)
    return int.from_bytes(
        child[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE],
        "little",
    )


def _collect_tree_nodes(pager: Pager, page_num: int, depth: int, nodes: list, edges: list) -> None:
    node_id = f"page-{page_num}"
    node = get_page(pager, page_num)
    node_type = int.from_bytes(get_node_type(node), "little")

    if node_type == NodeType.NODE_LEAF.value:
        num_keys = int.from_bytes(leaf_node_num_cells(node), "little")
        keys = [int.from_bytes(leaf_node_key(node, i), "little") for i in range(num_keys)]
        key_text = ", ".join(str(key) for key in keys) if keys else "(empty)"
        nodes.append({
            "id": node_id,
            "type": "customNode",
            "data": {
                "label": f"Leaf p{page_num} (size {num_keys})\n{key_text}",
                "page": page_num,
                "depth": depth,
                "nodeKind": "leaf",
                "keys": keys,
            },
            "position": {"x": 0, "y": 0},
        })
        return

    num_keys = int.from_bytes(internal_node_num_keys(node), "little")
    keys = [int.from_bytes(internal_node_key(node, i), "little") for i in range(num_keys)]
    key_text = ", ".join(f"key {key}" for key in keys) if keys else "(no keys)"
    nodes.append({
        "id": node_id,
        "type": "customNode",
        "data": {
            "label": f"Internal p{page_num} (size {num_keys})\n{key_text}",
            "page": page_num,
            "depth": depth,
            "nodeKind": "internal",
            "keys": keys,
        },
        "position": {"x": 0, "y": 0},
    })

    for child_index in range(num_keys + 1):
        child_page = _child_page_num(node, child_index)
        if child_page == INVALID_PAGE_NUM:
            continue
        child_id = f"page-{child_page}"
        edges.append({
            "id": f"e-{node_id}-{child_id}-{child_index}",
            "source": node_id,
            "target": child_id,
        })
        _collect_tree_nodes(pager, child_page, depth + 1, nodes, edges)


def _layout_tree_nodes(nodes: list) -> None:
    levels: dict[int, list] = defaultdict(list)
    for node in nodes:
        levels[node["data"]["depth"]].append(node)

    for depth, level_nodes in sorted(levels.items()):
        level_nodes.sort(key=lambda node: node["data"]["page"])
        count = len(level_nodes)
        for index, node in enumerate(level_nodes):
            node["position"] = {
                "x": (index - (count - 1) / 2) * H_SPACING + 400,
                "y": depth * V_SPACING + 50,
            }


def get_tree_json() -> str:
    """Return a React Flow graph as a JSON string with nodes and edges arrays."""
    if _table is None:
        return json.dumps({"nodes": [], "edges": []})

    nodes: list = []
    edges: list = []
    _collect_tree_nodes(_table.pager, _table.root_page_num, 0, nodes, edges)
    _layout_tree_nodes(nodes)

    for node in nodes:
        node["data"].pop("depth", None)

    return json.dumps({"nodes": nodes, "edges": edges})


def _memory_field(name: str, label: str, description: str, offset: int, size: int, raw: bytearray, value: str) -> dict:
    return {
        "name": name,
        "label": label,
        "description": description,
        "offset": offset,
        "size": size,
        "rawHex": raw.hex(),
        "value": value,
    }


def _format_page_num(page_num: int) -> str:
    if page_num == INVALID_PAGE_NUM:
        return f"{page_num} (INVALID — no page)"
    return str(page_num)


def _byte_range(start: int, size: int) -> str:
    end = start + size - 1
    if start == end:
        return f"byte {start}"
    return f"bytes {start}-{end}"


def _memory_block(start: int, size: int, label: str, kind: str, cell_index=None, value: str = "", used: bool = True) -> dict:
    end = start + size - 1
    return {
        "start": start,
        "end": end,
        "size": size,
        "byteRange": _byte_range(start, size),
        "label": label,
        "kind": kind,
        "cellIndex": cell_index,
        "value": value,
        "used": used,
    }


def _build_leaf_memory_layout(node: bytearray, num_cells: int) -> list:
    rows: list = []

    header_blocks = [
        _memory_block(NODE_TYPE_OFFSET, NODE_TYPE_SIZE, "node_type", "header", value="leaf"),
        _memory_block(IS_ROOT_OFFSET, IS_ROOT_SIZE, "is_root", "header", value="true" if is_node_root(node) else "false"),
        _memory_block(PARENT_POINTER_OFFSET, PARENT_POINTER_SIZE, "parent_pointer", "header", value=_format_page_num(int.from_bytes(node_parent(node), "little"))),
        _memory_block(LEAF_NODE_NUM_CELLS_OFFSET, LEAF_NODE_NUM_CELLS_SIZE, "num_cells", "header", value=str(num_cells)),
        _memory_block(LEAF_NODE_NEXT_LEAF_OFFSET, LEAF_NODE_NEXT_LEAF_SIZE, "next_leaf", "header", value=_format_page_num(int.from_bytes(leaf_node_next_leaf(node), "little"))),
    ]
    rows.append({"type": "header", "blocks": header_blocks})

    visible_cells: list = list(range(LEAF_NODE_MAX_CELLS))
    if LEAF_NODE_MAX_CELLS > 5:
        visible_cells = [0, 1, 2, "ellipsis", LEAF_NODE_MAX_CELLS - 1]

    for item in visible_cells:
        if item == "ellipsis":
            skip_start = LEAF_NODE_HEADER_SIZE + 3 * LEAF_NODE_CELL_SIZE
            skip_end = LEAF_NODE_HEADER_SIZE + (LEAF_NODE_MAX_CELLS - 1) * LEAF_NODE_CELL_SIZE - 1
            rows.append({
                "type": "ellipsis",
                "start": skip_start,
                "end": skip_end,
                "byteRange": _byte_range(skip_start, skip_end - skip_start + 1),
                "label": f"cells 3–{LEAF_NODE_MAX_CELLS - 2}",
            })
            continue

        cell_index = item
        cell_offset = LEAF_NODE_HEADER_SIZE + cell_index * LEAF_NODE_CELL_SIZE
        used = cell_index < num_cells
        if used:
            key = int.from_bytes(leaf_node_key(node, cell_index), "little")
            value_bytes = leaf_node_value(node, cell_index)
            row = Row()
            deserialize_row(value_bytes, row)
            key_value = str(key)
            value_summary = f"id={row.id}, user={row.username or '(empty)'}"
        else:
            key_value = ""
            value_summary = "(unused slot)"

        rows.append({
            "type": "cell",
            "cellIndex": cell_index,
            "blocks": [
                _memory_block(cell_offset + LEAF_NODE_KEY_OFFSET, LEAF_NODE_KEY_SIZE, f"key {cell_index}", "key", cell_index, key_value, used),
                _memory_block(cell_offset + LEAF_NODE_VALUE_OFFSET, LEAF_NODE_VALUE_SIZE, f"value {cell_index}", "value", cell_index, value_summary, used),
            ],
        })

    waste_start = LEAF_NODE_HEADER_SIZE + LEAF_NODE_MAX_CELLS * LEAF_NODE_CELL_SIZE
    if waste_start < PAGE_SIZE:
        rows.append({
            "type": "waste",
            "blocks": [_memory_block(waste_start, PAGE_SIZE - waste_start, "wasted space", "waste")],
        })

    return rows


def _build_internal_memory_layout(node: bytearray, num_keys: int) -> list:
    rows: list = []
    right_child = int.from_bytes(internal_node_right_child(node), "little")

    header_blocks = [
        _memory_block(NODE_TYPE_OFFSET, NODE_TYPE_SIZE, "node_type", "header", value="internal"),
        _memory_block(IS_ROOT_OFFSET, IS_ROOT_SIZE, "is_root", "header", value="true" if is_node_root(node) else "false"),
        _memory_block(PARENT_POINTER_OFFSET, PARENT_POINTER_SIZE, "parent_pointer", "header", value=_format_page_num(int.from_bytes(node_parent(node), "little"))),
        _memory_block(INTERNAL_NODE_NUM_KEYS_OFFSET, INTERNAL_NODE_NUM_KEYS_SIZE, "num_keys", "header", value=str(num_keys)),
        _memory_block(INTERNAL_NODE_RIGHT_CHILD_OFFSET, INTERNAL_NODE_RIGHT_CHILD_SIZE, "right_child", "header", value=_format_page_num(right_child)),
    ]
    rows.append({"type": "header", "blocks": header_blocks})

    for cell_index in range(INTERNAL_NODE_MAX_CELLS):
        cell_offset = INTERNAL_NODE_HEADER_SIZE + cell_index * INTERNAL_NODE_CELL_SIZE
        used = cell_index < num_keys
        if used:
            child_page = int.from_bytes(
                internal_node_child(node, cell_index)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE],
                "little",
            )
            separator_key = int.from_bytes(internal_node_key(node, cell_index), "little")
            child_value = _format_page_num(child_page)
            key_value = str(separator_key)
        else:
            child_value = ""
            key_value = ""

        rows.append({
            "type": "cell",
            "cellIndex": cell_index,
            "blocks": [
                _memory_block(cell_offset + INTERNAL_NODE_CHILD_OFFSET, INTERNAL_NODE_CHILD_SIZE, f"child {cell_index}", "child", cell_index, child_value, used),
                _memory_block(cell_offset + INTERNAL_NODE_KEY_OFFSET, INTERNAL_NODE_KEY_SIZE, f"key {cell_index}", "key", cell_index, key_value, used),
            ],
        })

    waste_start = INTERNAL_NODE_HEADER_SIZE + INTERNAL_NODE_MAX_CELLS * INTERNAL_NODE_CELL_SIZE
    if waste_start < PAGE_SIZE:
        rows.append({
            "type": "waste",
            "blocks": [_memory_block(waste_start, PAGE_SIZE - waste_start, "wasted space", "waste")],
        })

    return rows


def get_page_memory_json(page_num: int) -> str:
    """Return labeled memory layout for a single B-Tree page."""
    if _table is None:
        return json.dumps({"error": "Database not open."})

    node = get_page(_table.pager, page_num)
    node_type_val = int.from_bytes(get_node_type(node), "little")
    node_kind = "leaf" if node_type_val == NodeType.NODE_LEAF.value else "internal"

    sections: list = []

    common_fields = [
        _memory_field(
            "node_type",
            "Node Type",
            "0 = NODE_INTERNAL, 1 = NODE_LEAF",
            NODE_TYPE_OFFSET,
            NODE_TYPE_SIZE,
            get_node_type(node),
            "NODE_LEAF (1)" if node_kind == "leaf" else "NODE_INTERNAL (0)",
        ),
        _memory_field(
            "is_root",
            "Is Root",
            "1 if this page is the B-Tree root",
            IS_ROOT_OFFSET,
            IS_ROOT_SIZE,
            node[IS_ROOT_OFFSET:IS_ROOT_OFFSET + IS_ROOT_SIZE],
            "true" if is_node_root(node) else "false",
        ),
        _memory_field(
            "parent_pointer",
            "Parent Page",
            "Page number of the parent internal node",
            PARENT_POINTER_OFFSET,
            PARENT_POINTER_SIZE,
            node_parent(node),
            _format_page_num(int.from_bytes(node_parent(node), "little")),
        ),
    ]
    sections.append({
        "title": "Common Node Header",
        "offset": 0,
        "size": COMMON_NODE_HEADER_SIZE,
        "fields": common_fields,
    })

    if node_kind == "leaf":
        num_cells = int.from_bytes(leaf_node_num_cells(node), "little")
        next_leaf = int.from_bytes(leaf_node_next_leaf(node), "little")
        leaf_header_fields = [
            _memory_field(
                "num_cells",
                "Num Cells",
                f"Number of key/value pairs stored (max {LEAF_NODE_MAX_CELLS})",
                LEAF_NODE_NUM_CELLS_OFFSET,
                LEAF_NODE_NUM_CELLS_SIZE,
                leaf_node_num_cells(node),
                str(num_cells),
            ),
            _memory_field(
                "next_leaf",
                "Next Leaf Page",
                "Linked-list pointer to the next leaf page (0 = end of table)",
                LEAF_NODE_NEXT_LEAF_OFFSET,
                LEAF_NODE_NEXT_LEAF_SIZE,
                leaf_node_next_leaf(node),
                _format_page_num(next_leaf) if next_leaf != 0 else "0 (end of table)",
            ),
        ]
        sections.append({
            "title": "Leaf Node Header",
            "offset": COMMON_NODE_HEADER_SIZE,
            "size": LEAF_NODE_HEADER_SIZE - COMMON_NODE_HEADER_SIZE,
            "fields": leaf_header_fields,
        })

        for cell_index in range(num_cells):
            cell_offset = LEAF_NODE_HEADER_SIZE + cell_index * LEAF_NODE_CELL_SIZE
            key = int.from_bytes(leaf_node_key(node, cell_index), "little")
            value_bytes = leaf_node_value(node, cell_index)
            row = Row()
            deserialize_row(value_bytes, row)
            cell_fields = [
                _memory_field(
                    f"cell_{cell_index}_key",
                    "Key (ID)",
                    "B-Tree search key for this cell",
                    cell_offset + LEAF_NODE_KEY_OFFSET,
                    LEAF_NODE_KEY_SIZE,
                    leaf_node_key(node, cell_index),
                    str(key),
                ),
                _memory_field(
                    f"cell_{cell_index}_row_id",
                    "Row ID",
                    "User row primary key stored in the cell value",
                    cell_offset + LEAF_NODE_VALUE_OFFSET + ID_OFFSET,
                    ID_SIZE,
                    value_bytes[ID_OFFSET:ID_OFFSET + ID_SIZE],
                    str(row.id),
                ),
                _memory_field(
                    f"cell_{cell_index}_username",
                    "Username",
                    "Fixed-width username string",
                    cell_offset + LEAF_NODE_VALUE_OFFSET + USERNAME_OFFSET,
                    USERNAME_SIZE,
                    value_bytes[USERNAME_OFFSET:USERNAME_OFFSET + USERNAME_SIZE],
                    row.username or "(empty)",
                ),
                _memory_field(
                    f"cell_{cell_index}_email",
                    "Email",
                    "Fixed-width email string",
                    cell_offset + LEAF_NODE_VALUE_OFFSET + EMAIL_OFFSET,
                    EMAIL_SIZE,
                    value_bytes[EMAIL_OFFSET:EMAIL_OFFSET + EMAIL_SIZE],
                    row.email or "(empty)",
                ),
            ]
            sections.append({
                "title": f"Leaf Cell {cell_index}",
                "offset": cell_offset,
                "size": LEAF_NODE_CELL_SIZE,
                "fields": cell_fields,
            })
    else:
        num_keys = int.from_bytes(internal_node_num_keys(node), "little")
        right_child = int.from_bytes(internal_node_right_child(node), "little")
        internal_header_fields = [
            _memory_field(
                "num_keys",
                "Num Keys",
                f"Number of separator keys (max {INTERNAL_NODE_MAX_CELLS})",
                INTERNAL_NODE_NUM_KEYS_OFFSET,
                INTERNAL_NODE_NUM_KEYS_SIZE,
                internal_node_num_keys(node),
                str(num_keys),
            ),
            _memory_field(
                "right_child",
                "Right Child Page",
                "Page pointer to the rightmost child",
                INTERNAL_NODE_RIGHT_CHILD_OFFSET,
                INTERNAL_NODE_RIGHT_CHILD_SIZE,
                internal_node_right_child(node),
                _format_page_num(right_child),
            ),
        ]
        sections.append({
            "title": "Internal Node Header",
            "offset": COMMON_NODE_HEADER_SIZE,
            "size": INTERNAL_NODE_HEADER_SIZE - COMMON_NODE_HEADER_SIZE,
            "fields": internal_header_fields,
        })

        for key_index in range(num_keys):
            cell_offset = INTERNAL_NODE_HEADER_SIZE + key_index * INTERNAL_NODE_CELL_SIZE
            child_page = int.from_bytes(
                internal_node_child(node, key_index)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE],
                "little",
            )
            separator_key = int.from_bytes(internal_node_key(node, key_index), "little")
            cell_fields = [
                _memory_field(
                    f"cell_{key_index}_child",
                    "Left Child Page",
                    f"Child page to the left of separator key {key_index}",
                    cell_offset + INTERNAL_NODE_CHILD_OFFSET,
                    INTERNAL_NODE_CHILD_SIZE,
                    internal_node_child(node, key_index)[INTERNAL_NODE_CHILD_OFFSET:INTERNAL_NODE_CHILD_OFFSET + INTERNAL_NODE_CHILD_SIZE],
                    _format_page_num(child_page),
                ),
                _memory_field(
                    f"cell_{key_index}_key",
                    "Separator Key",
                    "Routing key — all keys in left subtree are less than this value",
                    cell_offset + INTERNAL_NODE_KEY_OFFSET,
                    INTERNAL_NODE_KEY_SIZE,
                    internal_node_key(node, key_index),
                    str(separator_key),
                ),
            ]
            sections.append({
                "title": f"Internal Cell {key_index}",
                "offset": cell_offset,
                "size": INTERNAL_NODE_CELL_SIZE,
                "fields": cell_fields,
            })

    memory_layout = (
        _build_leaf_memory_layout(node, int.from_bytes(leaf_node_num_cells(node), "little"))
        if node_kind == "leaf"
        else _build_internal_memory_layout(node, int.from_bytes(internal_node_num_keys(node), "little"))
    )

    return json.dumps({
        "page": page_num,
        "pageSize": PAGE_SIZE,
        "nodeKind": node_kind,
        "headerSize": LEAF_NODE_HEADER_SIZE if node_kind == "leaf" else INTERNAL_NODE_HEADER_SIZE,
        "sections": sections,
        "memoryLayout": memory_layout,
    })