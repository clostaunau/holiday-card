"""Template for a well-typed Python class.

This template demonstrates best practices for type hints in Python classes,
including instance variables, class variables, properties, and methods.
"""

from __future__ import annotations

from typing import ClassVar, Protocol, TypeVar, Generic, Final
from functools import cached_property
from dataclasses import dataclass


# Example 1: Basic typed class with instance variables
class User:
    """Example user class with comprehensive type hints."""

    # Class variable (shared across all instances)
    total_users: ClassVar[int] = 0

    # Instance variables can be declared at class level
    name: str
    age: int
    email: str | None

    def __init__(
        self,
        name: str,
        age: int,
        email: str | None = None,
        *,
        active: bool = True,
    ) -> None:
        """Initialize a new user.

        Args:
            name: User's full name
            age: User's age in years
            email: Optional email address
            active: Whether the user account is active (keyword-only)
        """
        self.name = name
        self.age = age
        self.email = email
        self.active = active
        User.total_users += 1

    def greet(self) -> str:
        """Return a greeting message.

        Returns:
            Personalized greeting string
        """
        return f"Hello, I'm {self.name} and I'm {self.age} years old!"

    def update_email(self, email: str) -> None:
        """Update the user's email address.

        Args:
            email: New email address
        """
        self.email = email

    @classmethod
    def from_dict(cls, data: dict[str, str | int]) -> User:
        """Create a User from a dictionary.

        Args:
            data: Dictionary containing user data

        Returns:
            New User instance
        """
        return cls(
            name=str(data["name"]),
            age=int(data["age"]),
            email=str(data.get("email")),
        )

    @staticmethod
    def is_valid_age(age: int) -> bool:
        """Check if an age is valid.

        Args:
            age: Age to validate

        Returns:
            True if age is valid (0-150)
        """
        return 0 <= age <= 150

    @property
    def display_name(self) -> str:
        """Get formatted display name.

        Returns:
            Capitalized name
        """
        return self.name.title()

    @display_name.setter
    def display_name(self, value: str) -> None:
        """Set name from display name.

        Args:
            value: New display name
        """
        self.name = value.lower()

    def __str__(self) -> str:
        """String representation.

        Returns:
            User description
        """
        return f"User(name={self.name}, age={self.age})"

    def __repr__(self) -> str:
        """Developer representation.

        Returns:
            Recreatable representation
        """
        return f"User(name={self.name!r}, age={self.age!r}, email={self.email!r})"


# Example 2: Generic class
T = TypeVar("T")


class Stack(Generic[T]):
    """Generic stack implementation with type safety."""

    def __init__(self) -> None:
        """Initialize an empty stack."""
        self._items: list[T] = []

    def push(self, item: T) -> None:
        """Push an item onto the stack.

        Args:
            item: Item to push
        """
        self._items.append(item)

    def pop(self) -> T | None:
        """Pop an item from the stack.

        Returns:
            The top item, or None if stack is empty
        """
        return self._items.pop() if self._items else None

    def peek(self) -> T | None:
        """Look at the top item without removing it.

        Returns:
            The top item, or None if stack is empty
        """
        return self._items[-1] if self._items else None

    def is_empty(self) -> bool:
        """Check if stack is empty.

        Returns:
            True if stack has no items
        """
        return len(self._items) == 0

    def __len__(self) -> int:
        """Get number of items in stack.

        Returns:
            Number of items
        """
        return len(self._items)


# Example 3: Protocol (structural typing)
class Drawable(Protocol):
    """Protocol for objects that can be drawn."""

    def draw(self) -> None:
        """Draw the object."""
        ...

    @property
    def color(self) -> str:
        """Get the object's color."""
        ...


class Circle:
    """Circle that satisfies Drawable protocol."""

    def __init__(self, radius: float, color: str = "black") -> None:
        """Initialize a circle.

        Args:
            radius: Circle radius
            color: Circle color
        """
        self.radius: Final[float] = radius
        self._color = color

    def draw(self) -> None:
        """Draw the circle."""
        print(f"Drawing a {self._color} circle with radius {self.radius}")

    @property
    def color(self) -> str:
        """Get the circle's color.

        Returns:
            Color name
        """
        return self._color


# Example 4: Dataclass (automatically generates __init__, __repr__, etc.)
@dataclass
class Product:
    """Product with automatic type-safe initialization.

    Dataclasses are perfect for data containers with type hints.
    """

    name: str
    price: float
    quantity: int = 0
    category: str | None = None

    @cached_property
    def total_value(self) -> float:
        """Calculate total inventory value.

        Returns:
            Price multiplied by quantity
        """
        return self.price * self.quantity

    def apply_discount(self, percent: float) -> float:
        """Calculate discounted price.

        Args:
            percent: Discount percentage (0-100)

        Returns:
            New price after discount
        """
        return self.price * (1 - percent / 100)


# Example 5: Class with complex type hints
class DataProcessor:
    """Example of complex type hints in a real-world class."""

    def __init__(
        self,
        data: list[dict[str, int | str | float]],
        *,
        filters: list[str] | None = None,
    ) -> None:
        """Initialize the data processor.

        Args:
            data: List of data records
            filters: Optional list of fields to filter
        """
        self._data = data
        self._filters = filters or []

    def process(
        self,
        transform: Callable[[dict[str, int | str | float]], dict[str, int | str | float]],
    ) -> list[dict[str, int | str | float]]:
        """Process data with a transformation function.

        Args:
            transform: Function to transform each record

        Returns:
            Transformed data
        """
        return [transform(record) for record in self._data]

    def filter_by(self, field: str, value: int | str | float) -> list[dict[str, int | str | float]]:
        """Filter records by field value.

        Args:
            field: Field name to filter on
            value: Value to match

        Returns:
            Filtered records
        """
        return [record for record in self._data if record.get(field) == value]


# Usage examples
if __name__ == "__main__":
    # Example 1: Basic class
    user = User("Alice", 30, "alice@example.com")
    print(user.greet())

    # Example 2: Generic class
    int_stack: Stack[int] = Stack()
    int_stack.push(1)
    int_stack.push(2)
    print(int_stack.pop())  # Type checker knows this is int | None

    # Example 3: Protocol
    circle: Drawable = Circle(5.0, "red")
    circle.draw()

    # Example 4: Dataclass
    product = Product("Widget", 19.99, 100, "Electronics")
    print(f"Total value: ${product.total_value:.2f}")

    # Example 5: Complex types
    processor = DataProcessor([{"id": 1, "name": "Test", "value": 42.0}])
    results = processor.filter_by("id", 1)
