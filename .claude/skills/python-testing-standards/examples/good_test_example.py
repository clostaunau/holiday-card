"""Example of well-written pytest tests.

This file demonstrates best practices:
- Clear test organization
- AAA pattern
- Good naming
- Proper fixture usage
- Comprehensive coverage
- Edge case testing
"""

import pytest
from datetime import datetime, timedelta
from myapp.shopping import ShoppingCart, Product, Discount
from myapp.exceptions import InvalidProductError, InsufficientStockError


# Fixtures
@pytest.fixture
def empty_cart():
    """Provide an empty shopping cart."""
    return ShoppingCart()


@pytest.fixture
def product_factory():
    """Provide factory for creating test products."""
    def _create_product(**kwargs):
        defaults = {
            "name": "Test Product",
            "price": 10.00,
            "stock": 100
        }
        defaults.update(kwargs)
        return Product(**defaults)
    return _create_product


@pytest.fixture
def sample_products(product_factory):
    """Provide sample products for testing."""
    return [
        product_factory(name="Widget", price=25.00, stock=50),
        product_factory(name="Gadget", price=15.00, stock=30),
        product_factory(name="Doohickey", price=5.00, stock=100),
    ]


# Test Class: Shopping Cart Operations
class TestShoppingCartOperations:
    """Tests for basic shopping cart operations."""

    def test_new_cart_is_empty(self, empty_cart):
        """Test that newly created cart is empty."""
        # Assert
        assert empty_cart.is_empty() is True
        assert len(empty_cart.items) == 0
        assert empty_cart.total() == 0.00

    def test_add_product_to_cart_increases_item_count(self, empty_cart, product_factory):
        """Test that adding product increases item count."""
        # Arrange
        product = product_factory(name="Widget", price=25.00)

        # Act
        empty_cart.add(product, quantity=1)

        # Assert
        assert empty_cart.is_empty() is False
        assert len(empty_cart.items) == 1
        assert empty_cart.items[0].product.name == "Widget"
        assert empty_cart.items[0].quantity == 1

    def test_add_same_product_twice_combines_quantities(self, empty_cart, product_factory):
        """Test that adding same product twice combines quantities."""
        # Arrange
        product = product_factory(name="Widget")

        # Act
        empty_cart.add(product, quantity=2)
        empty_cart.add(product, quantity=3)

        # Assert
        assert len(empty_cart.items) == 1  # Still one unique product
        assert empty_cart.items[0].quantity == 5

    def test_remove_product_from_cart_decreases_item_count(self, empty_cart, product_factory):
        """Test that removing product decreases item count."""
        # Arrange
        product = product_factory(name="Widget")
        empty_cart.add(product, quantity=1)

        # Act
        empty_cart.remove(product)

        # Assert
        assert empty_cart.is_empty() is True
        assert len(empty_cart.items) == 0

    def test_clear_cart_removes_all_items(self, empty_cart, sample_products):
        """Test that clearing cart removes all items."""
        # Arrange
        for product in sample_products:
            empty_cart.add(product, quantity=1)

        # Act
        empty_cart.clear()

        # Assert
        assert empty_cart.is_empty() is True
        assert len(empty_cart.items) == 0


# Test Class: Total Calculation
class TestShoppingCartTotalCalculation:
    """Tests for shopping cart total calculation."""

    def test_total_with_empty_cart_returns_zero(self, empty_cart):
        """Test that total for empty cart is zero."""
        # Act
        total = empty_cart.total()

        # Assert
        assert total == 0.00

    def test_total_with_single_product_calculates_correctly(self, empty_cart, product_factory):
        """Test total calculation with single product."""
        # Arrange
        product = product_factory(price=25.00)
        empty_cart.add(product, quantity=2)

        # Act
        total = empty_cart.total()

        # Assert
        assert total == 50.00

    def test_total_with_multiple_products_sums_correctly(self, empty_cart, sample_products):
        """Test total calculation with multiple products."""
        # Arrange
        empty_cart.add(sample_products[0], quantity=2)  # Widget: 25.00 * 2 = 50.00
        empty_cart.add(sample_products[1], quantity=1)  # Gadget: 15.00 * 1 = 15.00
        empty_cart.add(sample_products[2], quantity=3)  # Doohickey: 5.00 * 3 = 15.00

        # Act
        total = empty_cart.total()

        # Assert
        assert total == 80.00

    @pytest.mark.parametrize("discount_percent,expected_total", [
        (0, 100.00),
        (10, 90.00),
        (25, 75.00),
        (50, 50.00),
        (100, 0.00),
    ])
    def test_total_with_discount_applies_correctly(
        self, empty_cart, product_factory, discount_percent, expected_total
    ):
        """Test total calculation with various discount percentages."""
        # Arrange
        product = product_factory(price=100.00)
        empty_cart.add(product, quantity=1)
        discount = Discount(percentage=discount_percent)

        # Act
        total = empty_cart.total(discount=discount)

        # Assert
        assert total == expected_total


# Test Class: Validation
class TestShoppingCartValidation:
    """Tests for shopping cart validation."""

    def test_add_product_with_zero_quantity_raises_error(self, empty_cart, product_factory):
        """Test that adding product with zero quantity raises ValueError."""
        # Arrange
        product = product_factory()

        # Act & Assert
        with pytest.raises(ValueError, match="Quantity must be greater than zero"):
            empty_cart.add(product, quantity=0)

    def test_add_product_with_negative_quantity_raises_error(self, empty_cart, product_factory):
        """Test that adding product with negative quantity raises ValueError."""
        # Arrange
        product = product_factory()

        # Act & Assert
        with pytest.raises(ValueError, match="Quantity must be greater than zero"):
            empty_cart.add(product, quantity=-5)

    def test_add_product_exceeding_stock_raises_error(self, empty_cart, product_factory):
        """Test that adding more than available stock raises InsufficientStockError."""
        # Arrange
        product = product_factory(stock=10)

        # Act & Assert
        with pytest.raises(InsufficientStockError):
            empty_cart.add(product, quantity=15)

    def test_add_invalid_product_raises_error(self, empty_cart):
        """Test that adding invalid product raises InvalidProductError."""
        # Arrange
        invalid_product = None

        # Act & Assert
        with pytest.raises(InvalidProductError):
            empty_cart.add(invalid_product, quantity=1)


# Test Class: Edge Cases
class TestShoppingCartEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_add_product_with_maximum_quantity(self, empty_cart, product_factory):
        """Test adding product with maximum allowed quantity."""
        # Arrange
        product = product_factory(stock=1000)
        max_quantity = 999

        # Act
        empty_cart.add(product, quantity=max_quantity)

        # Assert
        assert empty_cart.items[0].quantity == max_quantity

    def test_total_with_very_small_prices(self, empty_cart, product_factory):
        """Test total calculation with very small prices."""
        # Arrange
        product = product_factory(price=0.01)
        empty_cart.add(product, quantity=3)

        # Act
        total = empty_cart.total()

        # Assert
        assert total == 0.03

    def test_total_with_large_prices(self, empty_cart, product_factory):
        """Test total calculation with large prices."""
        # Arrange
        product = product_factory(price=999999.99)
        empty_cart.add(product, quantity=2)

        # Act
        total = empty_cart.total()

        # Assert
        assert total == 1999999.98

    def test_remove_nonexistent_product_handles_gracefully(self, empty_cart, product_factory):
        """Test that removing non-existent product doesn't raise error."""
        # Arrange
        product = product_factory()

        # Act & Assert (should not raise)
        empty_cart.remove(product)
        assert empty_cart.is_empty() is True


# Test Class: Integration with Mocking
class TestShoppingCartWithMocking:
    """Tests demonstrating proper use of mocking."""

    def test_checkout_sends_receipt_email(self, empty_cart, product_factory, mocker):
        """Test that checkout sends receipt email."""
        # Arrange
        product = product_factory(price=25.00)
        empty_cart.add(product, quantity=2)

        mock_email = mocker.patch("myapp.shopping.EmailService.send")

        # Act
        empty_cart.checkout(email="customer@example.com")

        # Assert
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args[1]
        assert call_kwargs["to"] == "customer@example.com"
        assert call_kwargs["subject"] == "Your Receipt"
        assert "50.00" in call_kwargs["body"]

    def test_checkout_updates_inventory(self, empty_cart, product_factory, mocker):
        """Test that checkout updates product inventory."""
        # Arrange
        product = product_factory(stock=100)
        empty_cart.add(product, quantity=5)

        mock_inventory = mocker.patch("myapp.shopping.InventoryService.update_stock")

        # Act
        empty_cart.checkout(email="customer@example.com")

        # Assert
        mock_inventory.assert_called_once_with(product.id, -5)

    def test_checkout_failure_does_not_send_email(self, empty_cart, product_factory, mocker):
        """Test that failed checkout doesn't send email."""
        # Arrange
        product = product_factory()
        empty_cart.add(product, quantity=1)

        mock_email = mocker.patch("myapp.shopping.EmailService.send")
        mock_payment = mocker.patch("myapp.shopping.PaymentService.charge")
        mock_payment.side_effect = PaymentError("Card declined")

        # Act & Assert
        with pytest.raises(PaymentError):
            empty_cart.checkout(email="customer@example.com")

        # Email should NOT be sent on failure
        mock_email.assert_not_called()


# Standalone utility tests
def test_calculate_tax():
    """Test tax calculation utility function."""
    # Arrange
    subtotal = 100.00
    tax_rate = 0.08

    # Act
    tax = calculate_tax(subtotal, tax_rate)

    # Assert
    assert tax == 8.00


@pytest.mark.parametrize("input_price,expected_formatted", [
    (0.00, "$0.00"),
    (10.00, "$10.00"),
    (10.50, "$10.50"),
    (1234.56, "$1,234.56"),
    (1000000.00, "$1,000,000.00"),
])
def test_format_currency(input_price, expected_formatted):
    """Test currency formatting with various inputs."""
    # Act
    formatted = format_currency(input_price)

    # Assert
    assert formatted == expected_formatted
