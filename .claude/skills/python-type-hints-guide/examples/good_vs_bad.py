"""Examples comparing good and bad type hint patterns.

This file demonstrates common type hint anti-patterns and their better alternatives.
"""

from typing import Any, TypedDict, Protocol
from collections.abc import Iterable, Mapping


# ============================================================================
# 1. Overusing Any
# ============================================================================

# BAD: Using Any everywhere defeats the purpose
def process_data_bad(data: Any) -> Any:
    return data


def calculate_bad(x: Any, y: Any) -> Any:
    return x + y


# GOOD: Use specific types
def process_user_good(data: dict[str, str]) -> dict[str, str]:
    return {k: v.upper() for k, v in data.items()}


def calculate_good(x: int, y: int) -> int:
    return x + y


# ACCEPTABLE: Gradual typing with documentation
def legacy_function(data: Any) -> dict[str, Any]:
    """Process legacy data format.

    TODO: Add proper types once data structure is stable.
    """
    return {"result": data}


# ============================================================================
# 2. Overly Complex Type Hints
# ============================================================================

# BAD: Unreadable nested types
def transform_bad(
    data: dict[str, list[tuple[int, str, dict[str, list[int | str | None]]]]]
) -> list[tuple[str, dict[str, list[int]]]]:
    pass


# GOOD: Use type aliases for readability
InputRecord = tuple[int, str, dict[str, list[int | str | None]]]
InputData = dict[str, list[InputRecord]]
OutputRecord = tuple[str, dict[str, list[int]]]
OutputData = list[OutputRecord]


def transform_good(data: InputData) -> OutputData:
    pass


# BETTER: Use TypedDict for structured data
class Record(TypedDict):
    id: int
    name: str
    metadata: dict[str, list[int | str | None]]


class TransformedRecord(TypedDict):
    name: str
    values: dict[str, list[int]]


def transform_better(data: dict[str, list[Record]]) -> list[TransformedRecord]:
    pass


# ============================================================================
# 3. Using type: ignore Without Justification
# ============================================================================

# BAD: Silent errors without explanation
def risky_bad():
    result = some_operation()  # type: ignore
    return result


# BAD: Generic ignore
def generic_bad():
    value = complex_call()  # type: ignore
    return value


# GOOD: Specific error with explanation
def risky_good():
    # mypy doesn't understand this runtime type check
    result = some_operation()  # type: ignore[arg-type]  # See issue #456
    return result


# GOOD: Document temporary workaround
def legacy_good():
    # TODO: Remove after upgrading to library v2.0 with type stubs
    value = legacy_lib.call()  # type: ignore[no-untyped-call]
    return value


# BEST: Fix the underlying issue
def properly_typed() -> int:
    return 42


# ============================================================================
# 4. Over-Specification vs Flexibility
# ============================================================================

# BAD: Too rigid - only accepts list
def process_items_bad(items: list[str]) -> list[str]:
    return [item.upper() for item in items]


# GOOD: Accept any iterable, return list
def process_items_good(items: Iterable[str]) -> list[str]:
    return [item.upper() for item in items]


# Now works with lists, tuples, sets, generators
# process_items_good(["a", "b"])  # OK
# process_items_good(("a", "b"))  # OK
# process_items_good(x for x in ["a", "b"])  # OK


# BAD: Forces specific dict implementation
def merge_bad(d1: dict[str, int], d2: dict[str, int]) -> dict[str, int]:
    return {**d1, **d2}


# GOOD: Accept any mapping
def merge_good(d1: Mapping[str, int], d2: Mapping[str, int]) -> dict[str, int]:
    return {**d1, **d2}


# ============================================================================
# 5. Inconsistent Type Hint Usage
# ============================================================================

# BAD: Inconsistent typing in same module
def get_user_bad(user_id: int) -> dict:  # Untyped dict
    return {"id": user_id}


def create_user_bad(name, email):  # No types at all
    return {"name": name, "email": email}


def delete_user_bad(user_id: int) -> bool:  # Typed
    return True


# GOOD: Consistent typing throughout
class User(TypedDict):
    id: int
    name: str
    email: str


def get_user_good(user_id: int) -> User:
    return {"id": user_id, "name": "Unknown", "email": "unknown@example.com"}


def create_user_good(name: str, email: str) -> User:
    return {"id": 0, "name": name, "email": email}


def delete_user_good(user_id: int) -> bool:
    return True


# ============================================================================
# 6. Not Using Protocol for Duck Typing
# ============================================================================

# BAD: Forces inheritance
class Animal:
    def make_sound(self) -> str:
        raise NotImplementedError


class Dog(Animal):  # Must inherit
    def make_sound(self) -> str:
        return "Woof"


# GOOD: Duck typing with type safety
class CanMakeSound(Protocol):
    def make_sound(self) -> str: ...


class DogProtocol:  # No inheritance needed
    def make_sound(self) -> str:
        return "Woof"


class Car:  # Works with anything that has make_sound
    def make_sound(self) -> str:
        return "Vroom"


def hear_sound(thing: CanMakeSound) -> None:
    print(thing.make_sound())


# ============================================================================
# 7. Missing Type Hints on Public APIs
# ============================================================================

# BAD: Public API without types
def public_calculate_discount(price, discount_percent):
    """Calculate discounted price."""
    return price * (1 - discount_percent / 100)


# GOOD: Public API fully typed
def public_calculate_discount_good(price: float, discount_percent: float) -> float:
    """Calculate discounted price.

    Args:
        price: Original price
        discount_percent: Discount percentage (0-100)

    Returns:
        Discounted price
    """
    return price * (1 - discount_percent / 100)


# ============================================================================
# 8. Not Using Built-in Generics (Python 3.9+)
# ============================================================================

# BAD: Using typing module for standard collections (legacy style)
from typing import List, Dict, Set, Tuple


def process_names_old(names: List[str]) -> Dict[str, int]:
    return {name: len(name) for name in names}


# GOOD: Using built-in types (Python 3.9+)
def process_names_new(names: list[str]) -> dict[str, int]:
    return {name: len(name) for name in names}


# ============================================================================
# 9. Improper Optional Handling
# ============================================================================

# BAD: Implicit None (can be None but not typed)
def find_user_implicit(user_id: int) -> dict:
    if user_id < 0:
        return None  # Type error! Should return dict
    return {"id": user_id}


# BAD: Mutable default argument
def append_to_list_bad(item: str, items: list[str] = []) -> list[str]:  # Dangerous!
    items.append(item)
    return items


# GOOD: Explicit None in return type
def find_user_explicit(user_id: int) -> dict | None:
    if user_id < 0:
        return None
    return {"id": user_id}


# GOOD: Use None as default, create new list
def append_to_list_good(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items


# ============================================================================
# 10. Not Leveraging Type Narrowing
# ============================================================================

# BAD: Not using type narrowing
def process_value_bad(value: int | str) -> str:
    # Type checker doesn't know what value is here
    try:
        return str(int(value) * 2)  # May fail if value is str
    except:
        return value  # type: ignore


# GOOD: Use isinstance for type narrowing
def process_value_good(value: int | str) -> str:
    if isinstance(value, int):
        # Type checker knows value is int here
        return str(value * 2)
    # Type checker knows value is str here
    return value


# ============================================================================
# 11. Missing Return Type Annotations
# ============================================================================

# BAD: No return type annotation
def calculate_total(items):
    return sum(item["price"] for item in items)


# GOOD: Clear return type
def calculate_total_good(items: list[dict[str, float]]) -> float:
    return sum(item["price"] for item in items)


# BETTER: Use TypedDict for structured data
class Item(TypedDict):
    name: str
    price: float
    quantity: int


def calculate_total_better(items: list[Item]) -> float:
    return sum(item["price"] * item["quantity"] for item in items)


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    # Demonstrate good patterns
    print(calculate_good(5, 3))
    print(process_items_good(["hello", "world"]))
    print(process_items_good(("hello", "world")))  # Works with tuple too!

    # Protocol pattern
    dog = DogProtocol()
    car = Car()
    hear_sound(dog)
    hear_sound(car)

    # Proper optional handling
    user = find_user_explicit(123)
    if user:
        print(f"Found user: {user['id']}")

    # Type narrowing
    print(process_value_good(42))
    print(process_value_good("hello"))


# Helper functions for examples (would normally be imported)
def some_operation():
    return 42


class legacy_lib:
    @staticmethod
    def call():
        return {}
