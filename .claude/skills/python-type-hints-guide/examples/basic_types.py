"""Examples of basic type hint usage in Python 3.9+.

This file demonstrates fundamental type hint patterns for common use cases.
"""

from typing import Optional


# Basic types
def greet(name: str) -> str:
    """Simple string parameter and return type."""
    return f"Hello, {name}!"


def add(x: int, y: int) -> int:
    """Multiple parameters of same type."""
    return x + y


def calculate_average(scores: list[float]) -> float:
    """List with specific element type."""
    return sum(scores) / len(scores)


def is_valid(flag: bool) -> bool:
    """Boolean parameter and return type."""
    return not flag


# None type
def log_message(message: str) -> None:
    """Function that returns nothing."""
    print(f"[LOG] {message}")


def log_error(error: str) -> None:
    """Another void function."""
    print(f"[ERROR] {error}")


# Optional types (values that can be None)
def find_user_legacy(user_id: int) -> Optional[dict]:
    """Legacy style using Optional (Python 3.9)."""
    if user_id > 0:
        return {"id": user_id, "name": "User"}
    return None


def find_user(user_id: int) -> dict | None:
    """Modern style using union operator (Python 3.10+)."""
    if user_id > 0:
        return {"id": user_id, "name": "User"}
    return None


def greet_with_title(name: str, title: str | None = None) -> str:
    """Optional parameter with default None."""
    if title:
        return f"Hello, {title} {name}!"
    return f"Hello, {name}!"


# Collection types (Python 3.9+ - lowercase built-in types)
def process_names(names: list[str]) -> dict[str, int]:
    """List of strings to dict of string to int."""
    return {name: len(name) for name in names}


def unique_items(items: set[int]) -> list[int]:
    """Set to list conversion."""
    return sorted(items)


def get_coordinates() -> tuple[float, float]:
    """Fixed-length tuple."""
    return (42.0, -71.0)


def get_3d_point() -> tuple[float, float, float]:
    """Three-element tuple."""
    return (1.0, 2.0, 3.0)


def process_values(values: tuple[int, ...]) -> int:
    """Variable-length tuple (homogeneous)."""
    return sum(values)


def process_matrix(matrix: list[list[float]]) -> float:
    """Nested collections - 2D list."""
    return sum(sum(row) for row in matrix)


def count_items(items: list[str]) -> dict[str, int]:
    """Count occurrences of each item."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


# Union types (multiple possible types)
def process_id_legacy(user_id: int | str) -> str:
    """Accept int or str, return str."""
    return str(user_id)


def parse_value(value: int | float | str | None) -> float:
    """Multiple union types."""
    if value is None:
        return 0.0
    return float(value)


def format_value(value: str | int | float) -> str:
    """Format different numeric types."""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return f"{value:d}"
    return f"{value:.2f}"


# Dict with specific key and value types
def get_config() -> dict[str, str]:
    """Dict with string keys and values."""
    return {
        "host": "localhost",
        "port": "8080",
        "debug": "true",
    }


def get_scores() -> dict[str, float]:
    """Dict with string keys and float values."""
    return {
        "math": 95.5,
        "science": 87.0,
        "english": 92.3,
    }


def get_user_ages() -> dict[int, int]:
    """Dict with int keys and int values."""
    return {
        1: 25,
        2: 30,
        3: 35,
    }


# Multiple return values (tuple)
def divide_with_remainder(dividend: int, divisor: int) -> tuple[int, int]:
    """Return quotient and remainder."""
    return dividend // divisor, dividend % divisor


def get_min_max(numbers: list[int]) -> tuple[int, int]:
    """Return min and max values."""
    return min(numbers), max(numbers)


# Type annotations for variables
def process_data() -> None:
    """Example of variable type annotations."""
    # Explicit type annotation
    count: int = 0
    message: str = "Starting"
    is_valid: bool = True

    # Type inferred from assignment (annotation optional)
    total = 100  # Type inferred as int
    name = "Alice"  # Type inferred as str

    # Annotation needed when value comes later
    result: float
    result = calculate_average([1.0, 2.0, 3.0])

    # Collection variables
    names: list[str] = []
    scores: dict[str, int] = {}
    unique: set[int] = set()


# Usage examples
if __name__ == "__main__":
    print(greet("World"))
    print(add(5, 3))
    print(calculate_average([85.5, 92.0, 78.5]))

    # Optional types
    user = find_user(1)
    if user:
        print(f"Found user: {user['name']}")

    # Collections
    name_lengths = process_names(["Alice", "Bob", "Charlie"])
    print(name_lengths)

    # Union types
    print(process_id_legacy(123))
    print(process_id_legacy("abc"))

    # Multiple returns
    quotient, remainder = divide_with_remainder(17, 5)
    print(f"17 / 5 = {quotient} remainder {remainder}")
