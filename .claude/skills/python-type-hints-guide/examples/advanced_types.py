"""Examples of advanced type hint patterns.

This file demonstrates advanced type hint usage including generics, protocols,
TypedDict, Literal types, and other advanced features.
"""

from __future__ import annotations

from typing import (
    TypeVar,
    Generic,
    Protocol,
    TypedDict,
    NotRequired,
    Literal,
    Final,
    NewType,
    Callable,
    TypeAlias,
    TypeGuard,
    overload,
)
from functools import cached_property


# Generic types
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def first_item(items: list[T]) -> T | None:
    """Get first item from list with type preservation."""
    return items[0] if items else None


def last_item(items: list[T]) -> T | None:
    """Get last item from list with type preservation."""
    return items[-1] if items else None


class Stack(Generic[T]):
    """Generic stack implementation."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        """Push item onto stack."""
        self._items.append(item)

    def pop(self) -> T | None:
        """Pop item from stack."""
        return self._items.pop() if self._items else None


class Pair(Generic[K, V]):
    """Generic pair with two type parameters."""

    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

    def get_key(self) -> K:
        return self.key

    def get_value(self) -> V:
        return self.value


# Protocol (structural typing)
class Drawable(Protocol):
    """Protocol for objects that can be drawn."""

    def draw(self) -> None:
        """Draw the object."""
        ...


class Closeable(Protocol):
    """Protocol for objects that can be closed."""

    def close(self) -> None:
        """Close the resource."""
        ...


class Circle:
    """Circle satisfies Drawable without inheriting."""

    def __init__(self, radius: float) -> None:
        self.radius = radius

    def draw(self) -> None:
        print(f"Drawing circle with radius {self.radius}")


class Square:
    """Square also satisfies Drawable."""

    def __init__(self, side: float) -> None:
        self.side = side

    def draw(self) -> None:
        print(f"Drawing square with side {self.side}")


def render_shape(shape: Drawable) -> None:
    """Render any drawable shape."""
    shape.draw()


# TypedDict (structured dictionaries)
class User(TypedDict):
    """User dictionary with required fields."""

    name: str
    age: int
    email: str


class UserOptional(TypedDict):
    """User with some optional fields (Python 3.11+)."""

    name: str
    age: int
    email: NotRequired[str]
    phone: NotRequired[str]


class Employee(User):
    """Employee extends User TypedDict."""

    employee_id: int
    department: str


def create_user(name: str, age: int, email: str) -> User:
    """Create a typed user dictionary."""
    return {"name": name, "age": age, "email": email}


def process_user(user: User) -> str:
    """Process a user dictionary."""
    return f"{user['name']} ({user['age']})"


# Literal types
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def set_log_level(level: LogLevel) -> None:
    """Set log level to specific allowed value."""
    print(f"Log level set to {level}")


FileMode = Literal["r", "w", "a", "rb", "wb", "ab"]


def open_file(path: str, mode: FileMode = "r") -> None:
    """Open file with specific mode."""
    print(f"Opening {path} in mode {mode}")


Direction = Literal["north", "south", "east", "west"]


def move(direction: Direction, distance: int) -> None:
    """Move in a cardinal direction."""
    print(f"Moving {direction} for {distance} units")


# Final types
MAX_CONNECTIONS: Final[int] = 100
API_VERSION: Final[str] = "v1.0"


class Config:
    """Configuration with final values."""

    API_URL: Final[str] = "https://api.example.com"
    TIMEOUT: Final[int] = 30


# NewType (distinct types for type safety)
UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)
ProductId = NewType("ProductId", int)


def get_user(user_id: UserId) -> dict[str, str]:
    """Get user by ID."""
    return {"id": str(user_id), "name": "User"}


def get_order(order_id: OrderId) -> dict[str, str]:
    """Get order by ID."""
    return {"id": str(order_id), "status": "pending"}


def process_user_order(user_id: UserId, order_id: OrderId) -> None:
    """Process an order for a user."""
    user = get_user(user_id)
    order = get_order(order_id)
    print(f"Processing order {order['id']} for user {user['name']}")


# Callable types
def apply_operation(x: int, operation: Callable[[int], int]) -> int:
    """Apply a unary operation to a value."""
    return operation(x)


def apply_binary(x: int, y: int, operation: Callable[[int, int], int]) -> int:
    """Apply a binary operation to two values."""
    return operation(x, y)


def run_callback(callback: Callable[[], None]) -> None:
    """Run a callback with no arguments."""
    callback()


Validator = Callable[[str], bool]


def validate_input(value: str, validator: Validator) -> bool:
    """Validate input using a validator function."""
    return validator(value)


# Type aliases
Vector: TypeAlias = list[float]
Matrix: TypeAlias = list[Vector]
JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
Numeric: TypeAlias = int | float
OptionalString: TypeAlias = str | None


def scale_vector(vector: Vector, factor: float) -> Vector:
    """Scale a vector by a factor."""
    return [x * factor for x in vector]


def add_matrices(m1: Matrix, m2: Matrix) -> Matrix:
    """Add two matrices."""
    return [[a + b for a, b in zip(row1, row2)] for row1, row2 in zip(m1, m2)]


# Overloaded functions
@overload
def process(data: str) -> str: ...


@overload
def process(data: int) -> int: ...


@overload
def process(data: list[str]) -> list[str]: ...


def process(data: str | int | list[str]) -> str | int | list[str]:
    """Process different types of data."""
    if isinstance(data, str):
        return data.upper()
    elif isinstance(data, int):
        return data * 2
    else:
        return [s.upper() for s in data]


# Type guards
def is_string_list(val: list[object]) -> TypeGuard[list[str]]:
    """Check if list contains only strings."""
    return all(isinstance(x, str) for x in val)


def process_list(items: list[object]) -> None:
    """Process a list, handling strings specially."""
    if is_string_list(items):
        # Type narrowed to list[str]
        for item in items:
            print(item.upper())
    else:
        for item in items:
            print(item)


# Complex generic example
class Repository(Generic[T]):
    """Generic repository pattern."""

    def __init__(self) -> None:
        self._items: dict[int, T] = {}
        self._next_id = 1

    def add(self, item: T) -> int:
        """Add item and return ID."""
        item_id = self._next_id
        self._items[item_id] = item
        self._next_id += 1
        return item_id

    def get(self, item_id: int) -> T | None:
        """Get item by ID."""
        return self._items.get(item_id)

    def all(self) -> list[T]:
        """Get all items."""
        return list(self._items.values())


# Usage examples
if __name__ == "__main__":
    # Generic types
    names = ["Alice", "Bob", "Charlie"]
    first_name: str | None = first_item(names)
    print(f"First name: {first_name}")

    numbers = [1, 2, 3, 4, 5]
    first_num: int | None = first_item(numbers)
    print(f"First number: {first_num}")

    # Stack
    int_stack: Stack[int] = Stack()
    int_stack.push(1)
    int_stack.push(2)
    print(f"Popped: {int_stack.pop()}")

    # Protocol
    circle = Circle(5.0)
    square = Square(10.0)
    render_shape(circle)
    render_shape(square)

    # TypedDict
    user: User = {"name": "Alice", "age": 30, "email": "alice@example.com"}
    print(process_user(user))

    # Literal
    set_log_level("INFO")
    move("north", 10)

    # NewType
    user_id = UserId(123)
    order_id = OrderId(456)
    process_user_order(user_id, order_id)

    # Callable
    result = apply_operation(5, lambda x: x * 2)
    print(f"Result: {result}")

    result2 = apply_binary(3, 4, lambda x, y: x + y)
    print(f"Result: {result2}")

    # Overload
    str_result: str = process("hello")
    int_result: int = process(42)
    list_result: list[str] = process(["a", "b"])
    print(str_result, int_result, list_result)

    # Repository
    user_repo: Repository[User] = Repository()
    uid = user_repo.add({"name": "Bob", "age": 25, "email": "bob@example.com"})
    stored_user = user_repo.get(uid)
    print(f"Stored user: {stored_user}")
