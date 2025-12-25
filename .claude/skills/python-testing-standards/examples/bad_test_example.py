"""Example of poorly written tests (anti-patterns).

This file demonstrates what NOT to do:
- Poor naming
- Missing AAA pattern
- Test interdependence
- Testing implementation details
- Over-mocking
- Missing edge cases

DO NOT USE THESE PATTERNS IN YOUR TESTS!
"""

# Anti-Pattern 1: Poor Test Names
def test_cart():
    """What does this test? Who knows!"""
    cart = ShoppingCart()
    cart.add(Product("Widget", 10.00), 1)
    assert len(cart.items) == 1  # What aspect of cart is being tested?


def test_1():
    """Completely non-descriptive."""
    pass


def testUserStuff():
    """Doesn't follow pytest naming convention, vague."""
    pass


# Anti-Pattern 2: Testing Multiple Unrelated Things
def test_shopping_cart():
    """This test does too much!"""
    # Test 1: Creating cart
    cart = ShoppingCart()
    assert cart.is_empty()

    # Test 2: Adding items
    cart.add(Product("Widget", 10.00), 1)
    assert len(cart.items) == 1

    # Test 3: Calculating total
    total = cart.total()
    assert total == 10.00

    # Test 4: Removing items
    cart.clear()
    assert cart.is_empty()

    # Test 5: Discount application
    cart.add(Product("Widget", 100.00), 1)
    total_with_discount = cart.total(Discount(10))
    assert total_with_discount == 90.00

    # When this fails, which part is broken?


# Anti-Pattern 3: No AAA Pattern
def test_add_to_cart():
    """Everything mixed together, hard to understand."""
    cart = ShoppingCart()
    product = Product("Widget", 25.00)
    cart.add(product, 2)
    assert cart.total() == 50.00
    cart.add(Product("Gadget", 15.00), 1)
    assert len(cart.items) == 2
    total = cart.total()
    assert total == 65.00


# Anti-Pattern 4: Test Interdependence
# Shared state between tests - NEVER DO THIS!
_test_cart = ShoppingCart()

def test_add_item():
    """This test must run first!"""
    _test_cart.add(Product("Widget", 10.00), 1)
    assert len(_test_cart.items) == 1


def test_calculate_total():
    """This test depends on test_add_item running first!"""
    # Assumes item was added by previous test
    total = _test_cart.total()
    assert total == 10.00  # Will fail if test_add_item didn't run!


def test_remove_item():
    """This test depends on both previous tests!"""
    _test_cart.clear()
    assert len(_test_cart.items) == 0


# Anti-Pattern 5: Testing Implementation Details
def test_internal_validation():
    """DON'T test private methods directly!"""
    cart = ShoppingCart()

    # Testing private method
    result = cart._validate_product(Product("Widget", 10.00))
    assert result is True

    # Testing private attribute
    assert cart._items == []


def test_with_implementation_mock():
    """DON'T mock internal implementation!"""
    cart = ShoppingCart()

    # Mocking internal method defeats the purpose
    with patch.object(cart, "_calculate_subtotal", return_value=100.00):
        total = cart.total()
        assert total == 100.00  # This doesn't test anything real!


# Anti-Pattern 6: Over-Mocking
def test_over_mocked():
    """Mocking everything, testing nothing!"""
    # Mock ALL the things!
    mock_product = Mock()
    mock_cart = Mock()
    mock_cart.add = Mock()
    mock_cart.total = Mock(return_value=100.00)

    # This doesn't test any real code
    mock_cart.add(mock_product, 1)
    total = mock_cart.total()

    assert total == 100.00  # Completely pointless


# Anti-Pattern 7: Unclear Assertions
def test_user_creation():
    """Assertions don't make sense."""
    user = User("john@example.com")

    # What does this even test?
    assert user
    assert user.email  # Just checking it's not None? Too vague!


def test_multiple_unclear_assertions():
    """Too many unrelated assertions."""
    user = User("john@example.com")

    # What is this test actually verifying?
    assert user is not None
    assert user.email is not None
    assert len(user.email) > 0
    assert "@" in user.email
    assert user.created_at is not None
    assert user.is_active


# Anti-Pattern 8: No Edge Case Testing
def test_divide():
    """Only tests happy path!"""
    result = divide(10, 2)
    assert result == 5.0

    # What about:
    # - Division by zero?
    # - Negative numbers?
    # - Floating point precision?
    # - Very large numbers?


# Anti-Pattern 9: Magic Values
def test_with_magic_values():
    """What do these values mean?"""
    user = User("test@example.com", "password123", 30, True, "admin", 12345)

    # What is 30? What is True? What is 12345?
    assert user.age == 30
    assert user.is_active is True
    assert user.user_id == 12345


# Anti-Pattern 10: No Cleanup
def test_file_operation():
    """Leaves files behind!"""
    # Create file
    with open("test_file.txt", "w") as f:
        f.write("test data")

    # Test something
    result = process_file("test_file.txt")
    assert result == "processed"

    # File left behind! No cleanup!


# Anti-Pattern 11: Testing Framework Code
def test_django_orm():
    """DON'T test the framework!"""
    user = User(username="test")
    user.save()

    # This tests Django's ORM, not your code
    assert User.objects.filter(username="test").exists()


# Anti-Pattern 12: Broad Exception Catching
def test_with_broad_exception():
    """Too broad exception handling."""
    with pytest.raises(Exception):  # Which exception?
        risky_operation()

    # Should specify exact exception:
    # with pytest.raises(SpecificError):


# Anti-Pattern 13: No Assertions
def test_without_assertion():
    """This test doesn't verify anything!"""
    cart = ShoppingCart()
    cart.add(Product("Widget", 10.00), 1)
    total = cart.total()

    # No assertion! Test always passes!


def test_with_only_print():
    """Print is not an assertion!"""
    result = calculate(5, 10)
    print(f"Result: {result}")  # Manual verification required


# Anti-Pattern 14: Flaky Tests
def test_timing_dependent():
    """Test depends on timing - will fail randomly!"""
    import time

    start = time.time()
    slow_operation()
    duration = time.time() - start

    # Flaky: might fail on slower machines
    assert duration < 1.0


def test_random_dependent():
    """Test uses uncontrolled randomness."""
    result = generate_random_number()

    # This will fail randomly!
    assert result > 5


# Anti-Pattern 15: Unclear Test Failure Messages
def test_unclear_failure():
    """When this fails, the message won't help."""
    result = complex_calculation(10, 20, 30)

    # If this fails, you won't know what was expected
    assert result == 42


# Anti-Pattern 16: Not Using Fixtures
def test_without_fixtures_1():
    """Duplicate setup code."""
    db = Database()
    db.connect()
    user = User("test1@example.com")
    db.save(user)

    result = db.find_by_email("test1@example.com")
    assert result is not None


def test_without_fixtures_2():
    """Same setup duplicated!"""
    db = Database()
    db.connect()
    user = User("test2@example.com")
    db.save(user)

    result = db.find_by_email("test2@example.com")
    assert result is not None


# Anti-Pattern 17: Testing Private Implementation
class TestInternalDetails:
    """DON'T test internal implementation details."""

    def test_internal_cache():
        """Testing internal caching mechanism."""
        service = UserService()

        # Checking internal cache state
        assert service._cache == {}

        service.get_user(1)

        # Testing internal implementation
        assert 1 in service._cache
        assert service._cache[1] is not None


# Anti-Pattern 18: Complex Test Logic
def test_with_complex_logic():
    """Tests should be simple! This is too complex."""
    results = []

    for i in range(10):
        if i % 2 == 0:
            result = process_even(i)
        else:
            result = process_odd(i)

        if result > 5:
            results.append(result)

    # If this fails, good luck debugging
    assert len(results) == 5


# Anti-Pattern 19: Not Isolating Tests
# Using class variables - BAD!
class TestWithSharedState:
    """Shared state between tests - BAD!"""

    cart = ShoppingCart()  # Shared between all tests!

    def test_add_item(self):
        """Modifies shared state."""
        self.cart.add(Product("Widget", 10.00), 1)
        assert len(self.cart.items) == 1

    def test_total(self):
        """Depends on previous test's state!"""
        total = self.cart.total()
        # Will this be 10.00 or 0.00? Depends on test order!
        assert total == 10.00


# Anti-Pattern 20: Missing Docstrings
def test_something():
    cart = ShoppingCart()
    cart.add(Product("Widget", 10.00), 1)
    assert len(cart.items) == 1
    # What does this test? Why does it exist?


# Summary: What NOT to do
"""
ANTI-PATTERNS TO AVOID:

1. ❌ Vague test names
2. ❌ Testing multiple things in one test
3. ❌ No clear AAA structure
4. ❌ Tests depending on each other
5. ❌ Testing implementation details
6. ❌ Over-mocking
7. ❌ Unclear assertions
8. ❌ Not testing edge cases
9. ❌ Magic values without context
10. ❌ No cleanup/teardown
11. ❌ Testing framework code
12. ❌ Broad exception catching
13. ❌ No assertions
14. ❌ Flaky tests
15. ❌ Unclear failure messages
16. ❌ Duplicated setup code
17. ❌ Testing private methods
18. ❌ Complex test logic
19. ❌ Shared state between tests
20. ❌ Missing documentation

Instead, follow the best practices in good_test_example.py!
"""
