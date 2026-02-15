# Python Testing Code Review Checklist

Use this checklist when reviewing Python test code to ensure quality and adherence to best practices.

## Test File Organization

- [ ] Test files named `test_*.py` or `*_test.py`
- [ ] Tests organized in logical directories (`unit/`, `integration/`, `e2e/`)
- [ ] Shared fixtures in `conftest.py` at appropriate levels
- [ ] One test file per module/class being tested
- [ ] Imports are organized and minimal
- [ ] No commented-out code

## Test Function/Class Naming

- [ ] Test functions start with `test_`
- [ ] Test classes start with `Test` (no underscore)
- [ ] Names describe the scenario: `test_<what>_<when>_<expected>`
- [ ] Names are clear and self-documenting
- [ ] No generic names like `test_1()` or `test_main()`

## Test Structure

- [ ] Tests follow AAA or Given-When-Then pattern
- [ ] Clear separation between Arrange, Act, Assert sections
- [ ] Each test verifies one logical behavior
- [ ] Tests are independent and can run in any order
- [ ] No shared mutable state between tests
- [ ] Setup/teardown properly handled

## Documentation

- [ ] Each test has a docstring explaining what it tests
- [ ] Complex test scenarios are well-documented
- [ ] Fixture purposes are clear from docstrings
- [ ] README explains how to run tests
- [ ] Custom markers are documented

## Fixtures

- [ ] Appropriate fixture scope selected (function/class/module/session)
- [ ] Fixtures have descriptive names (nouns, not verbs)
- [ ] Fixtures clean up resources (using yield)
- [ ] Fixture dependencies are logical and clear
- [ ] `autouse` only used when absolutely necessary
- [ ] No overly complex fixture setup
- [ ] Fixtures in `conftest.py` are truly shared

## Parametrization

- [ ] `@pytest.mark.parametrize` used for multiple similar test cases
- [ ] Test IDs provided for clarity (using `pytest.param`)
- [ ] Parametrized tests cover full range of inputs
- [ ] Parameters are well-named and clear

## Mocking and Patching

- [ ] Only external dependencies are mocked
- [ ] Internal business logic is tested directly (not mocked)
- [ ] Patches target where object is used, not where it's defined
- [ ] Mock assertions verify expected behavior
- [ ] Mocks are properly configured with return values
- [ ] No over-mocking (testing too little real code)
- [ ] pytest-mock (`mocker` fixture) used instead of unittest.mock when possible

## Mock Assertions

- [ ] All mocks have verification assertions
- [ ] Appropriate assertion methods used (`assert_called_once`, `assert_called_with`, etc.)
- [ ] `assert_not_called()` used to verify mocks weren't called when appropriate
- [ ] Side effects properly configured for retry/failure scenarios

## Assertions

- [ ] Tests have at least one assertion
- [ ] Assertions are specific and meaningful
- [ ] Exception tests use `pytest.raises()`
- [ ] Exception tests include `match` parameter for message verification
- [ ] Assertion messages provided for complex checks
- [ ] No bare `assert True` or similar pointless assertions

## Test Coverage

- [ ] Critical paths have 100% coverage
- [ ] Overall coverage meets project threshold (typically 80%+)
- [ ] Business logic is thoroughly tested
- [ ] Edge cases are covered
- [ ] Boundary conditions are tested
- [ ] Error handling is tested
- [ ] Negative test cases are included

## What's Being Tested

- [ ] Tests verify behavior, not implementation details
- [ ] Public API/interface is tested, not private methods
- [ ] Framework/library code is not being tested
- [ ] No testing of trivial getters/setters
- [ ] No testing of generated code

## Edge Cases and Error Handling

- [ ] Empty collections tested ([], {}, "")
- [ ] None values tested
- [ ] Zero values tested
- [ ] Negative numbers tested
- [ ] Boundary values tested (max/min)
- [ ] Invalid input types tested
- [ ] Exception handling tested
- [ ] All error paths have tests

## Test Independence

- [ ] Tests don't depend on execution order
- [ ] Tests don't share mutable state
- [ ] Each test creates its own test data
- [ ] No module-level or class-level shared state
- [ ] Database state is reset between tests

## Test Quality

- [ ] No testing of implementation details
- [ ] No overly complex test setup (use fixtures instead)
- [ ] Tests are not flaky (deterministic, no timing dependencies)
- [ ] Tests are fast (unit tests < 100ms)
- [ ] No duplicate test code (DRY principle)
- [ ] Test logic is simple and easy to understand

## Code Quality

- [ ] Tests follow PEP 8 style guide
- [ ] Consistent indentation (4 spaces)
- [ ] Line length under 88-100 characters
- [ ] No magic values without context
- [ ] Helper functions used to reduce duplication
- [ ] Test data factories used for complex objects

## Resource Management

- [ ] Files are properly closed/cleaned up
- [ ] Database connections are closed
- [ ] Temporary files/directories are removed
- [ ] Mock patches are properly cleaned up (automatic with fixtures)
- [ ] No resource leaks

## Markers and Organization

- [ ] Slow tests marked with `@pytest.mark.slow`
- [ ] Integration tests marked appropriately
- [ ] Custom markers registered in pytest.ini
- [ ] Tests can be selectively run by marker

## Configuration

- [ ] pytest.ini or pyproject.toml configured
- [ ] Coverage thresholds set
- [ ] Test paths configured
- [ ] Markers registered
- [ ] Appropriate files omitted from coverage

## Common Anti-Patterns (Should NOT appear)

- [ ] ❌ No vague test names (e.g., `test_1`, `test_main`)
- [ ] ❌ No testing multiple unrelated behaviors in one test
- [ ] ❌ No test interdependencies
- [ ] ❌ No testing private methods directly
- [ ] ❌ No over-mocking internal logic
- [ ] ❌ No unclear assertions
- [ ] ❌ No missing edge cases
- [ ] ❌ No magic values
- [ ] ❌ No missing cleanup
- [ ] ❌ No testing framework code
- [ ] ❌ No broad exception catching (`except Exception:`)
- [ ] ❌ No tests without assertions
- [ ] ❌ No flaky tests (timing, randomness)
- [ ] ❌ No shared mutable state
- [ ] ❌ No complex test logic

## Performance Considerations

- [ ] Fast tests don't hit external services
- [ ] In-memory databases used for unit tests
- [ ] Expensive operations are mocked
- [ ] Slow tests are marked and can be skipped
- [ ] Parametrized tests don't create excessive test count

## Integration Tests (Additional Checks)

- [ ] Database fixtures use transaction rollback
- [ ] Tests verify actual database interactions
- [ ] Real relationships between entities tested
- [ ] Migration compatibility tested
- [ ] External service interactions properly mocked

## Documentation and Maintenance

- [ ] Complex test scenarios explained in comments
- [ ] Non-obvious test data explained
- [ ] Reasons for mocking specific dependencies documented
- [ ] TODO comments have associated tickets/issues
- [ ] Deprecated tests removed or updated

## CI/CD Readiness

- [ ] Tests run successfully in clean environment
- [ ] No hardcoded paths or environment-specific code
- [ ] No tests that only work on developer machine
- [ ] Environment variables properly handled
- [ ] Test data is portable

## Review Summary

### Strengths
- [ ] List what the tests do well

### Issues Found
- [ ] List issues that need to be addressed

### Recommendations
- [ ] List suggestions for improvement

### Overall Assessment
- [ ] Ready to merge
- [ ] Needs minor changes
- [ ] Needs major changes
- [ ] Blocked by issues

---

## Quick Reference: Red Flags

🚩 **Immediate Issues (Must Fix):**
- Tests that fail intermittently (flaky)
- Tests that depend on execution order
- No assertions in tests
- Testing private methods/implementation details
- Mocking internal business logic
- Shared mutable state between tests

⚠️ **Important Issues (Should Fix):**
- Missing edge case tests
- No error handling tests
- Poor test names
- Over-complex test setup
- Missing fixture cleanup
- Low code coverage (<80%)

💡 **Nice to Have (Consider):**
- Better test organization
- More parametrization
- Better documentation
- Performance optimization
- More comprehensive mocking assertions

---

## Usage Instructions

1. **Before Review:**
   - Run tests locally: `pytest`
   - Run with coverage: `pytest --cov=myapp --cov-report=term-missing`
   - Check for slow tests: `pytest --durations=10`

2. **During Review:**
   - Go through each section of this checklist
   - Mark items as you verify them
   - Note any issues found
   - Make suggestions for improvement

3. **After Review:**
   - Provide constructive feedback
   - Prioritize issues (must fix vs nice to have)
   - Suggest concrete improvements
   - Acknowledge good practices

---

**Version:** 1.0
**Last Updated:** 2025-12-24
**Reference:** `../SKILL.md`
