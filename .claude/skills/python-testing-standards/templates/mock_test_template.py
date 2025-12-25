"""Test template demonstrating mocking and patching best practices.

This template demonstrates:
- When to mock vs when to test real implementation
- pytest-mock usage
- unittest.mock usage
- Patching strategies
- Mock assertions
- Side effects

Usage:
1. Copy relevant sections to your test file
2. Replace mock targets with actual dependencies
3. Add proper verification assertions
"""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from myapp.services import UserService, EmailService  # Replace with actual imports
from myapp.models import User  # Replace with actual imports


# Example 1: Mocking External API Calls
class TestExternalAPIInteraction:
    """Tests demonstrating mocking of external API calls."""

    def test_fetch_user_data_from_api(self, mocker):
        """Test fetching user data from external API.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock requests.get
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.json.return_value = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com"
        }
        mock_get.return_value.status_code = 200

        # Act
        api_client = APIClient()
        user_data = api_client.fetch_user(user_id=1)

        # Assert: Verify API was called correctly
        mock_get.assert_called_once_with(
            "https://api.example.com/users/1",
            headers={"Authorization": "Bearer token"},
            timeout=30
        )
        assert user_data["name"] == "John Doe"
        assert user_data["email"] == "john@example.com"

    def test_api_failure_raises_exception(self, mocker):
        """Test that API failure raises appropriate exception.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock API to raise exception
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        # Act & Assert
        api_client = APIClient()
        with pytest.raises(APIError, match="Failed to fetch user data"):
            api_client.fetch_user(user_id=1)


# Example 2: Mocking Database Operations
class TestDatabaseMocking:
    """Tests demonstrating mocking of database operations."""

    def test_user_service_creates_user_in_database(self, mocker):
        """Test that user service creates user in database.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock database repository
        mock_repo = mocker.Mock()
        mock_repo.save.return_value = User(id=1, username="john")

        service = UserService(repository=mock_repo)

        # Act
        user = service.create_user(username="john", email="john@example.com")

        # Assert: Verify repository.save was called
        mock_repo.save.assert_called_once()
        call_args = mock_repo.save.call_args[0][0]  # First positional argument
        assert isinstance(call_args, User)
        assert call_args.username == "john"
        assert user.id == 1

    def test_find_user_by_email_queries_database(self, mocker):
        """Test that finding user queries database correctly.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock repository
        mock_repo = mocker.Mock()
        mock_repo.find_by_email.return_value = User(
            id=1,
            username="john",
            email="john@example.com"
        )

        service = UserService(repository=mock_repo)

        # Act
        user = service.find_user_by_email("john@example.com")

        # Assert
        mock_repo.find_by_email.assert_called_once_with("john@example.com")
        assert user.email == "john@example.com"


# Example 3: Mocking Email Service
class TestEmailServiceMocking:
    """Tests demonstrating mocking of email service."""

    def test_user_registration_sends_welcome_email(self, mocker):
        """Test that user registration sends welcome email.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock email service
        mock_email = mocker.patch("myapp.services.EmailService.send")

        service = UserService()

        # Act
        user = service.register("john@example.com", "password123")

        # Assert: Verify email was sent
        mock_email.assert_called_once_with(
            to="john@example.com",
            subject="Welcome to Our Service!",
            template="welcome",
            context={"username": user.username}
        )

    def test_registration_failure_does_not_send_email(self, mocker):
        """Test that failed registration doesn't send email.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock email service
        mock_email = mocker.patch("myapp.services.EmailService.send")

        service = UserService()

        # Act: Try to register with invalid data
        with pytest.raises(ValidationError):
            service.register("invalid-email", "pass")

        # Assert: Email was NOT sent
        mock_email.assert_not_called()


# Example 4: Mocking File Operations
class TestFileOperationMocking:
    """Tests demonstrating mocking of file operations."""

    def test_read_config_file(self, mocker):
        """Test reading configuration from file.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock file reading
        mock_open = mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data="config_value=test")
        )

        # Act
        config = ConfigLoader.load("config.txt")

        # Assert
        mock_open.assert_called_once_with("config.txt", "r")
        assert config["config_value"] == "test"

    def test_write_log_file(self, mocker):
        """Test writing to log file.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock file writing
        mock_open = mocker.patch("builtins.open", mocker.mock_open())

        logger = Logger("app.log")

        # Act
        logger.log("Test message")

        # Assert: Verify file was opened and written to
        mock_open.assert_called_once_with("app.log", "a")
        handle = mock_open()
        handle.write.assert_called_once_with("Test message\n")


# Example 5: Mocking datetime
class TestDateTimeMocking:
    """Tests demonstrating mocking of datetime operations."""

    def test_timestamp_generation(self, mocker):
        """Test timestamp generation with frozen time.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock datetime.now()
        from datetime import datetime

        mock_datetime = mocker.patch("myapp.utils.datetime")
        fixed_time = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time

        # Act
        timestamp = generate_timestamp()

        # Assert
        assert timestamp == "2024-01-01 12:00:00"

    def test_expiry_check_with_mocked_time(self, mocker):
        """Test expiry check with controlled time.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock time
        from datetime import datetime, timedelta

        mock_datetime = mocker.patch("myapp.utils.datetime")
        current_time = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = current_time

        token = Token(
            value="abc123",
            created_at=current_time - timedelta(hours=2),
            expires_in_hours=1
        )

        # Act
        is_expired = token.is_expired()

        # Assert
        assert is_expired is True


# Example 6: Mock Side Effects
class TestMockSideEffects:
    """Tests demonstrating mock side effects."""

    def test_retry_logic_with_failures(self, mocker):
        """Test retry logic when operations fail multiple times.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: First two calls fail, third succeeds
        mock_api = mocker.Mock()
        mock_api.fetch.side_effect = [
            ConnectionError("Failed"),
            ConnectionError("Failed"),
            {"status": "success", "data": "result"}
        ]

        client = APIClient(api=mock_api)

        # Act
        result = client.fetch_with_retry(max_retries=3)

        # Assert
        assert result["status"] == "success"
        assert mock_api.fetch.call_count == 3

    def test_callback_execution(self, mocker):
        """Test that callbacks are executed correctly.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock with side effect function
        mock_callback = mocker.Mock()

        def side_effect_func(value):
            """Side effect that calls callback."""
            mock_callback(f"processed_{value}")
            return f"result_{value}"

        mock_processor = mocker.Mock()
        mock_processor.process.side_effect = side_effect_func

        # Act
        result = mock_processor.process("test")

        # Assert
        assert result == "result_test"
        mock_callback.assert_called_once_with("processed_test")


# Example 7: Patching Class Methods
class TestClassMethodPatching:
    """Tests demonstrating patching of class methods."""

    def test_patch_class_method(self, mocker):
        """Test patching a class method.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Patch class method
        mock_validate = mocker.patch("myapp.models.User.validate")
        mock_validate.return_value = True

        # Act
        user = User(username="test", email="test@example.com")
        is_valid = user.validate()

        # Assert
        assert is_valid is True
        mock_validate.assert_called_once()

    def test_patch_instance_method(self, mocker):
        """Test patching an instance method.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Create instance then patch its method
        user = User(username="test", email="test@example.com")
        mock_method = mocker.patch.object(user, "validate", return_value=True)

        # Act
        is_valid = user.validate()

        # Assert
        assert is_valid is True
        mock_method.assert_called_once()


# Example 8: Multiple Mock Assertions
class TestMockAssertions:
    """Tests demonstrating various mock assertion methods."""

    def test_mock_call_assertions(self, mocker):
        """Test various ways to assert mock calls.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange
        mock_service = mocker.Mock()

        # Act: Call mock multiple times
        mock_service.send("user1@example.com", "Message 1")
        mock_service.send("user2@example.com", "Message 2")
        mock_service.send("user3@example.com", "Message 3")

        # Assert: Various assertion methods
        assert mock_service.send.called
        assert mock_service.send.call_count == 3

        # Check specific call
        mock_service.send.assert_any_call("user2@example.com", "Message 2")

        # Check last call
        mock_service.send.assert_called_with("user3@example.com", "Message 3")

        # Check all calls
        expected_calls = [
            call("user1@example.com", "Message 1"),
            call("user2@example.com", "Message 2"),
            call("user3@example.com", "Message 3"),
        ]
        mock_service.send.assert_has_calls(expected_calls)

        # Get call arguments
        first_call_args = mock_service.send.call_args_list[0]
        assert first_call_args == call("user1@example.com", "Message 1")


# Example 9: Mocking Context Managers
class TestContextManagerMocking:
    """Tests demonstrating mocking of context managers."""

    def test_database_transaction(self, mocker):
        """Test code using database transaction context manager.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock context manager
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_db.transaction.return_value.__enter__.return_value = mock_transaction

        # Act
        with mock_db.transaction() as txn:
            txn.execute("INSERT INTO users VALUES (?)", ("test",))
            txn.commit()

        # Assert
        mock_db.transaction.assert_called_once()
        mock_transaction.execute.assert_called_once_with(
            "INSERT INTO users VALUES (?)", ("test",)
        )
        mock_transaction.commit.assert_called_once()


# Example 10: Patching Multiple Targets
class TestMultiplePatches:
    """Tests demonstrating patching multiple targets."""

    def test_with_multiple_patches(self, mocker):
        """Test with multiple dependencies mocked.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Patch multiple dependencies
        mock_db = mocker.patch("myapp.services.Database")
        mock_email = mocker.patch("myapp.services.EmailService.send")
        mock_logger = mocker.patch("myapp.services.logger")

        # Configure mocks
        mock_db.return_value.save.return_value = True

        service = UserService()

        # Act
        user = service.register("test@example.com", "password")

        # Assert: Verify all dependencies were used
        mock_db.return_value.save.assert_called_once()
        mock_email.assert_called_once()
        mock_logger.info.assert_called()

    def test_with_decorator_patches(self):
        """Test using @patch decorators (alternative to mocker).

        Note: pytest-mock's mocker fixture is preferred, but this shows
        the decorator approach for reference.
        """
        # Arrange & Act & Assert in one
        with patch("myapp.services.Database") as mock_db, \
             patch("myapp.services.EmailService.send") as mock_email:

            mock_db.return_value.save.return_value = True

            service = UserService()
            user = service.register("test@example.com", "password")

            mock_db.return_value.save.assert_called_once()
            mock_email.assert_called_once()


# Example 11: Property Mocking
class TestPropertyMocking:
    """Tests demonstrating mocking of properties."""

    def test_mock_property(self, mocker):
        """Test mocking a property.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock property
        user = User(username="test")
        mocker.patch.object(
            type(user),
            "is_admin",
            new_callable=mocker.PropertyMock,
            return_value=True
        )

        # Act
        is_admin = user.is_admin

        # Assert
        assert is_admin is True


# Example 12: Mocking Generators
class TestGeneratorMocking:
    """Tests demonstrating mocking of generators."""

    def test_mock_generator(self, mocker):
        """Test mocking a generator function.

        Args:
            mocker: pytest-mock fixture
        """
        # Arrange: Mock generator to yield specific values
        def mock_generator():
            yield 1
            yield 2
            yield 3

        mock_data_source = mocker.patch("myapp.data.get_data_stream")
        mock_data_source.return_value = mock_generator()

        # Act
        processor = DataProcessor()
        results = list(processor.process_stream())

        # Assert
        assert results == [1, 2, 3]


# Best Practices Summary
"""
BEST PRACTICES FOR MOCKING:

1. Mock External Dependencies:
   ✅ DO mock: APIs, databases, email services, file I/O
   ❌ DON'T mock: Your business logic, simple data structures

2. Patch Where Used, Not Where Defined:
   ✅ DO: mocker.patch("myapp.services.Database")  # where it's imported
   ❌ DON'T: mocker.patch("myapp.database.Database")  # where it's defined

3. Always Verify Mock Calls:
   ✅ DO: mock.assert_called_once_with(expected_args)
   ❌ DON'T: Just mock and forget to verify

4. Use pytest-mock When Possible:
   ✅ DO: Use mocker fixture
   ❌ DON'T: Use unittest.mock directly unless necessary

5. Keep Mocks Simple:
   ✅ DO: Mock only what's necessary
   ❌ DON'T: Over-mock and test nothing real

6. Clean Up:
   ✅ DO: Use fixtures (automatic cleanup)
   ❌ DON'T: Use manual patching without cleanup
"""
