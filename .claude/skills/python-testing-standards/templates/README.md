# Python Testing Standards - Templates

This directory contains reusable templates for writing high-quality Python tests.

## Available Templates

### 1. Unit Test Template (`unit_test_template.py`)

**Purpose:** Template for writing unit tests using pytest with best practices.

**Features:**
- AAA pattern examples
- Fixture usage demonstrations
- Parametrization examples
- Mocking examples
- Test class organization
- Edge case testing patterns

**Usage:**
```bash
# Copy template
cp templates/unit_test_template.py tests/unit/test_your_module.py

# Edit the file:
# 1. Replace [MODULE_NAME] with your module name
# 2. Update imports
# 3. Modify/add fixtures for your needs
# 4. Add your test cases following the patterns
```

**Best for:**
- Testing individual functions/methods
- Testing business logic
- Fast, isolated tests
- Testing with mocked dependencies

---

### 2. Integration Test Template (`integration_test_template.py`)

**Purpose:** Template for writing integration tests with database interactions.

**Features:**
- Database engine setup (SQLite, PostgreSQL, MySQL)
- Session fixtures with transaction rollback
- Database cleanup strategies
- Test data factories
- Relationship testing
- Complex query testing

**Usage:**
```bash
# Copy template
cp templates/integration_test_template.py tests/integration/test_your_feature.py

# Edit the file:
# 1. Configure database engine for your database type
# 2. Update model imports
# 3. Update repository imports
# 4. Modify fixtures for your data model
# 5. Add integration test cases
```

**Best for:**
- Testing database interactions
- Testing ORM queries
- Testing relationships between entities
- Testing transactions and rollbacks
- Testing repositories/data access layer

---

### 3. Mock Test Template (`mock_test_template.py`)

**Purpose:** Comprehensive examples of mocking and patching with pytest-mock.

**Features:**
- External API mocking
- Database operation mocking
- Email service mocking
- File operation mocking
- datetime mocking
- Mock side effects
- Mock assertions
- Context manager mocking
- Property mocking

**Usage:**
```bash
# Reference this file for mocking patterns
# Copy relevant sections to your test files

# Examples:
# - How to mock requests.get
# - How to mock database operations
# - How to mock email sending
# - How to mock file I/O
# - How to verify mock calls
```

**Best for:**
- Learning mocking patterns
- Reference for common mocking scenarios
- Understanding when to mock vs when not to
- Mock assertion examples

---

## Template Organization

```
templates/
├── README.md                      # This file
├── unit_test_template.py          # Unit test template
├── integration_test_template.py   # Integration test template
└── mock_test_template.py          # Mocking examples and patterns
```

## Quick Start Guide

### For Unit Tests

1. Copy the unit test template:
   ```bash
   cp templates/unit_test_template.py tests/unit/test_my_module.py
   ```

2. Replace placeholders:
   - `[MODULE_NAME]` → Your module name
   - `FunctionOrClass` → Your function/class under test
   - Update imports

3. Customize fixtures for your needs

4. Write tests following the AAA pattern examples

5. Run tests:
   ```bash
   pytest tests/unit/test_my_module.py -v
   ```

### For Integration Tests

1. Copy the integration test template:
   ```bash
   cp templates/integration_test_template.py tests/integration/test_my_feature.py
   ```

2. Configure database:
   - Update `database_engine` fixture for your DB type
   - Update model imports
   - Update repository imports

3. Customize factories for your data model

4. Write integration tests

5. Run tests:
   ```bash
   pytest tests/integration/test_my_feature.py -v
   ```

### For Mocking Reference

1. Open `mock_test_template.py` in your editor

2. Find the mocking pattern you need:
   - Search for "API" for API mocking
   - Search for "Database" for DB mocking
   - Search for "Email" for email mocking
   - etc.

3. Copy the relevant example to your test file

4. Adapt to your specific use case

## Common Patterns

### Creating a Test Fixture

```python
@pytest.fixture
def my_object():
    """Provide instance of object under test."""
    obj = MyObject(param="value")
    yield obj
    # Cleanup if needed
    obj.cleanup()
```

### Creating a Factory Fixture

```python
@pytest.fixture
def object_factory():
    """Provide factory for creating test objects."""
    created_objects = []

    def _create(**kwargs):
        defaults = {"param": "default_value"}
        defaults.update(kwargs)
        obj = MyObject(**defaults)
        created_objects.append(obj)
        return obj

    yield _create

    # Cleanup all created objects
    for obj in created_objects:
        obj.cleanup()
```

### Parametrized Test

```python
@pytest.mark.parametrize("input_value,expected_output", [
    ("input1", "output1"),
    ("input2", "output2"),
    ("input3", "output3"),
])
def test_function(input_value, expected_output):
    """Test with multiple inputs."""
    result = my_function(input_value)
    assert result == expected_output
```

### Test with Mocking

```python
def test_with_mock(mocker):
    """Test with mocked dependency."""
    # Mock external service
    mock_service = mocker.patch("myapp.module.ExternalService")
    mock_service.return_value.method.return_value = "mocked_result"

    # Test
    result = function_using_service()

    # Verify
    mock_service.return_value.method.assert_called_once()
    assert result == "mocked_result"
```

## Best Practices Reminder

1. **AAA Pattern:** Always use Arrange-Act-Assert
2. **One Test, One Behavior:** Each test should verify one thing
3. **Descriptive Names:** `test_<what>_<when>_<expected>`
4. **Use Fixtures:** Don't duplicate setup code
5. **Mock External:** Mock APIs, databases, email, not your logic
6. **Clean Up:** Use yield in fixtures for cleanup
7. **Test Edge Cases:** Empty, None, zero, negative, boundaries
8. **Fast Tests:** Keep unit tests under 100ms

## Running Tests

```bash
# Run all tests
pytest

# Run specific template (to see examples)
pytest templates/unit_test_template.py -v

# Run with coverage
pytest --cov=myapp --cov-report=term-missing

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_my_module.py

# Run specific test function
pytest tests/unit/test_my_module.py::test_specific_function

# Run with markers
pytest -m "not slow"  # Skip slow tests
```

## Additional Resources

- **Main Skill:** `../SKILL.md`
- **Good Examples:** `../examples/good_test_example.py`
- **Bad Examples (Anti-patterns):** `../examples/bad_test_example.py`
- **Code Review Checklist:** `../checklists/code_review_checklist.md`

## Support

For questions about these templates or Python testing best practices:
1. Review the main SKILL.md file
2. Check the examples directory
3. Consult the code review checklist
4. Ask the `uncle-duke-python` agent for guidance

---

**Happy Testing!** 🧪
