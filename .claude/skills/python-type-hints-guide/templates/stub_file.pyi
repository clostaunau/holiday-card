# stub_file.pyi - Type stub template
# Create a .pyi file parallel to the .py file you want to type
# Example: If you have mymodule.py, create mymodule.pyi

"""Type stubs for [module name].

Stub files provide type information for untyped code or third-party libraries.
They should mirror the public API of the actual module.
"""

from typing import Any, Optional, Union, List, Dict, Callable, TypeVar, Protocol

# Type variables for generic functions/classes
T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

# Constants
MODULE_VERSION: str
DEFAULT_TIMEOUT: int

# Simple function stub
def simple_function(arg: str) -> int: ...

# Function with optional arguments
def function_with_defaults(
    required: str,
    optional: int = ...,
    keyword_only: bool = ...,
) -> None: ...

# Function with *args and **kwargs
def flexible_function(
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]: ...

# Generic function
def process_items(items: List[T]) -> List[T]: ...

# Class stub
class ExampleClass:
    """Class docstring goes here."""

    # Class variable
    class_var: str

    # Instance variables (can be in __init__ or as annotations)
    instance_var: int

    def __init__(
        self,
        name: str,
        value: int = ...,
        *,
        flag: bool = ...,
    ) -> None: ...

    # Instance method
    def method(self, param: str) -> bool: ...

    # Class method
    @classmethod
    def from_string(cls, data: str) -> "ExampleClass": ...

    # Static method
    @staticmethod
    def utility_function(x: int, y: int) -> int: ...

    # Property
    @property
    def computed_value(self) -> float: ...

    @computed_value.setter
    def computed_value(self, value: float) -> None: ...

# Protocol for duck typing
class SupportsClose(Protocol):
    def close(self) -> None: ...

# Generic class
class Container(Generic[T]):
    def __init__(self) -> None: ...
    def add(self, item: T) -> None: ...
    def get(self) -> Optional[T]: ...

# Function returning callable
def get_processor() -> Callable[[str], int]: ...

# Overloaded function (multiple signatures)
from typing import overload

@overload
def process(data: str) -> str: ...

@overload
def process(data: int) -> int: ...

def process(data: Union[str, int]) -> Union[str, int]: ...

# Context manager
class ManagedResource:
    def __enter__(self) -> "ManagedResource": ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

# Async context manager
class AsyncManagedResource:
    async def __aenter__(self) -> "AsyncManagedResource": ...
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

# Module-level __all__ (defines public API)
__all__ = [
    'simple_function',
    'ExampleClass',
    'Container',
]
