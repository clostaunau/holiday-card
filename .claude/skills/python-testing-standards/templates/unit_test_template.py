"""Unit test template for [MODULE_NAME].

This template demonstrates pytest best practices:
- AAA pattern (Arrange-Act-Assert)
- Clear test names
- Proper fixture usage
- Parametrization
- Docstrings

Usage:
1. Copy this file to tests/unit/test_[module_name].py
2. Replace [MODULE_NAME] with actual module name
3. Replace placeholder imports and fixtures
4. Add your test cases following the patterns below
"""

import pytest
from myapp.module import FunctionOrClass  # Replace with actual import


# Fixtures
@pytest.fixture
def sample_data():
    """Provide sample test data.

    Returns:
        dict: Sample data for testing
    """
    return {
        "field1": "value1",
        "field2": "value2",
    }


@pytest.fixture
def mock_dependency(mocker):
    """Provide mocked external dependency.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mock: Mocked dependency
    """
    mock = mocker.patch("myapp.module.ExternalDependency")
    mock.method.return_value = "mocked_result"
    return mock


# Test Functions
def test_function_with_valid_input_returns_expected_result():
    """Test that function returns expected result with valid input.

    This test demonstrates:
    - Descriptive test name
    - Clear AAA pattern
    - Specific assertion
    """
    # Arrange
    input_value = "test_input"
    expected_output = "expected_result"

    # Act
    result = function_under_test(input_value)

    # Assert
    assert result == expected_output


def test_function_with_invalid_input_raises_error():
    """Test that function raises ValueError for invalid input.

    This test demonstrates:
    - Testing error cases
    - Using pytest.raises()
    - Matching error message
    """
    # Arrange
    invalid_input = None

    # Act & Assert
    with pytest.raises(ValueError, match="Input cannot be None"):
        function_under_test(invalid_input)


def test_function_with_fixture(sample_data):
    """Test function using fixture data.

    Args:
        sample_data: Fixture providing test data

    This test demonstrates:
    - Using fixtures for test data
    - Testing with realistic data
    """
    # Arrange
    # (data provided by fixture)

    # Act
    result = function_under_test(sample_data)

    # Assert
    assert result is not None
    assert "field1" in result


def test_function_calls_external_service(mock_dependency):
    """Test that function calls external service correctly.

    Args:
        mock_dependency: Mocked external dependency

    This test demonstrates:
    - Mocking external dependencies
    - Verifying mock interactions
    """
    # Arrange
    input_value = "test"

    # Act
    result = function_under_test(input_value)

    # Assert
    mock_dependency.method.assert_called_once_with(input_value)
    assert result == "mocked_result"


@pytest.mark.parametrize("input_value,expected_output", [
    ("input1", "output1"),
    ("input2", "output2"),
    ("input3", "output3"),
])
def test_function_with_multiple_inputs(input_value, expected_output):
    """Test function with various inputs using parametrization.

    Args:
        input_value: Input value to test
        expected_output: Expected output for given input

    This test demonstrates:
    - Using @pytest.mark.parametrize
    - Testing multiple scenarios efficiently
    """
    # Act
    result = function_under_test(input_value)

    # Assert
    assert result == expected_output


@pytest.mark.parametrize("input_value,should_raise", [
    pytest.param("valid_input", False, id="valid_input"),
    pytest.param("", True, id="empty_string"),
    pytest.param(None, True, id="none_value"),
])
def test_function_validation(input_value, should_raise):
    """Test function validation with various inputs.

    Args:
        input_value: Input to test
        should_raise: Whether an exception should be raised

    This test demonstrates:
    - Testing both valid and invalid inputs
    - Using pytest.param for test IDs
    """
    if should_raise:
        with pytest.raises(ValueError):
            function_under_test(input_value)
    else:
        result = function_under_test(input_value)
        assert result is not None


# Test Classes (for grouping related tests)
class TestClassUnderTest:
    """Tests for ClassUnderTest.

    This class demonstrates:
    - Grouping related tests
    - Using class-level fixtures
    - Testing class methods
    """

    @pytest.fixture
    def instance(self):
        """Provide instance of class under test.

        Returns:
            ClassUnderTest: Instance for testing
        """
        return ClassUnderTest(param1="value1", param2="value2")

    def test_method_with_valid_input_succeeds(self, instance):
        """Test that method succeeds with valid input.

        Args:
            instance: Instance of class under test
        """
        # Arrange
        input_value = "test"

        # Act
        result = instance.method(input_value)

        # Assert
        assert result is not None

    def test_method_updates_state_correctly(self, instance):
        """Test that method updates instance state correctly.

        Args:
            instance: Instance of class under test
        """
        # Arrange
        initial_state = instance.state

        # Act
        instance.method("test")

        # Assert
        assert instance.state != initial_state
        assert instance.state == "expected_state"

    def test_method_with_dependency(self, instance, mocker):
        """Test method interaction with dependency.

        Args:
            instance: Instance of class under test
            mocker: pytest-mock fixture
        """
        # Arrange
        mock_service = mocker.patch.object(instance, "service")
        mock_service.call.return_value = "mocked_result"

        # Act
        result = instance.method_using_service("input")

        # Assert
        mock_service.call.assert_called_once_with("input")
        assert result == "mocked_result"


# Edge Cases and Special Scenarios
class TestEdgeCases:
    """Tests for edge cases and boundary conditions.

    This class demonstrates:
    - Testing edge cases
    - Testing boundary conditions
    - Testing special scenarios
    """

    def test_function_with_empty_input(self):
        """Test function handles empty input correctly."""
        # Arrange
        empty_input = []

        # Act
        result = function_under_test(empty_input)

        # Assert
        assert result == []

    def test_function_with_large_input(self):
        """Test function handles large input correctly."""
        # Arrange
        large_input = list(range(10000))

        # Act
        result = function_under_test(large_input)

        # Assert
        assert len(result) == len(large_input)

    def test_function_with_unicode_characters(self):
        """Test function handles unicode characters correctly."""
        # Arrange
        unicode_input = "Hello, 世界! 🌍"

        # Act
        result = function_under_test(unicode_input)

        # Assert
        assert "世界" in result
        assert "🌍" in result


# Helper Functions (not tests, but used by tests)
def create_test_object(**kwargs):
    """Helper function to create test objects.

    Args:
        **kwargs: Parameters for object creation

    Returns:
        TestObject: Created test object
    """
    defaults = {
        "field1": "default1",
        "field2": "default2",
    }
    defaults.update(kwargs)
    return TestObject(**defaults)


# Markers for test organization
@pytest.mark.slow
def test_slow_operation():
    """Test that takes longer to run.

    This test demonstrates:
    - Using markers to categorize tests
    - Run with: pytest -m slow
    - Skip with: pytest -m "not slow"
    """
    # Arrange
    large_dataset = generate_large_dataset()

    # Act
    result = process_large_dataset(large_dataset)

    # Assert
    assert result is not None
