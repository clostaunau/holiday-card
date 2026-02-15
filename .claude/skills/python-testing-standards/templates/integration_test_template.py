"""Integration test template with database fixtures.

This template demonstrates:
- Integration testing with real database
- Database fixtures with transaction rollback
- Testing multi-component interactions
- Cleanup strategies

Usage:
1. Copy to tests/integration/test_[feature_name].py
2. Configure database engine for your database type
3. Replace placeholder models and repositories
4. Add your integration test cases
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from myapp.models import Base, User, Post  # Replace with actual models
from myapp.repositories import UserRepository, PostRepository  # Replace with actual repositories


# Session-scoped fixtures (expensive setup, reused across tests)
@pytest.fixture(scope="session")
def database_engine():
    """Create database engine for testing.

    Uses in-memory SQLite for fast tests. For testing specific database:
    - PostgreSQL: "postgresql://localhost/test_db"
    - MySQL: "mysql://localhost/test_db"
    - SQLite file: "sqlite:///test.db"

    Returns:
        Engine: SQLAlchemy engine
    """
    # Using in-memory SQLite for fast tests
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,  # Set to True for SQL debugging
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def SessionFactory(database_engine):
    """Create session factory.

    Args:
        database_engine: Database engine fixture

    Returns:
        sessionmaker: Session factory
    """
    return sessionmaker(bind=database_engine)


# Function-scoped fixtures (fresh for each test)
@pytest.fixture
def db_session(database_engine):
    """Provide database session with automatic rollback.

    This fixture:
    - Creates a new connection for each test
    - Starts a transaction
    - Provides a session
    - Rolls back transaction after test (cleanup)

    Args:
        database_engine: Database engine fixture

    Yields:
        Session: SQLAlchemy session
    """
    # Create connection and transaction
    connection = database_engine.connect()
    transaction = connection.begin()

    # Create session bound to connection
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    # Cleanup: rollback transaction and close connection
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user_repository(db_session):
    """Provide user repository with database session.

    Args:
        db_session: Database session fixture

    Returns:
        UserRepository: Repository instance
    """
    return UserRepository(session=db_session)


@pytest.fixture
def post_repository(db_session):
    """Provide post repository with database session.

    Args:
        db_session: Database session fixture

    Returns:
        PostRepository: Repository instance
    """
    return PostRepository(session=db_session)


# Data factories for creating test data
@pytest.fixture
def user_factory(db_session):
    """Provide factory for creating test users.

    Args:
        db_session: Database session fixture

    Returns:
        callable: Factory function
    """
    created_users = []

    def _create_user(**kwargs):
        """Create a test user.

        Args:
            **kwargs: User attributes

        Returns:
            User: Created user
        """
        defaults = {
            "username": f"testuser_{len(created_users)}",
            "email": f"user{len(created_users)}@example.com",
            "is_active": True,
        }
        defaults.update(kwargs)

        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        created_users.append(user)
        return user

    return _create_user


@pytest.fixture
def post_factory(db_session, user_factory):
    """Provide factory for creating test posts.

    Args:
        db_session: Database session fixture
        user_factory: User factory fixture

    Returns:
        callable: Factory function
    """
    created_posts = []

    def _create_post(**kwargs):
        """Create a test post.

        Args:
            **kwargs: Post attributes

        Returns:
            Post: Created post
        """
        # Create author if not provided
        if "author" not in kwargs:
            kwargs["author"] = user_factory()

        defaults = {
            "title": f"Test Post {len(created_posts)}",
            "content": "Test content",
        }
        defaults.update(kwargs)

        post = Post(**defaults)
        db_session.add(post)
        db_session.commit()
        db_session.refresh(post)

        created_posts.append(post)
        return post

    return _create_post


# Integration Tests
class TestUserRepository:
    """Integration tests for UserRepository.

    These tests verify:
    - Database interactions work correctly
    - CRUD operations persist data
    - Queries return correct results
    """

    def test_create_user_persists_to_database(self, user_repository):
        """Test that creating a user persists to database.

        Args:
            user_repository: UserRepository instance
        """
        # Arrange
        user_data = {
            "username": "john_doe",
            "email": "john@example.com",
        }

        # Act
        user = user_repository.create(**user_data)

        # Assert
        assert user.id is not None
        assert user.username == "john_doe"
        assert user.email == "john@example.com"

        # Verify persisted
        retrieved_user = user_repository.find_by_id(user.id)
        assert retrieved_user is not None
        assert retrieved_user.username == "john_doe"

    def test_find_by_email_returns_correct_user(self, user_repository, user_factory):
        """Test finding user by email returns correct user.

        Args:
            user_repository: UserRepository instance
            user_factory: Factory for creating users
        """
        # Arrange
        user1 = user_factory(username="user1", email="user1@example.com")
        user2 = user_factory(username="user2", email="user2@example.com")

        # Act
        found_user = user_repository.find_by_email("user2@example.com")

        # Assert
        assert found_user is not None
        assert found_user.id == user2.id
        assert found_user.username == "user2"

    def test_find_by_nonexistent_email_returns_none(self, user_repository):
        """Test finding user by non-existent email returns None.

        Args:
            user_repository: UserRepository instance
        """
        # Act
        found_user = user_repository.find_by_email("nonexistent@example.com")

        # Assert
        assert found_user is None

    def test_update_user_persists_changes(self, user_repository, user_factory):
        """Test updating user persists changes to database.

        Args:
            user_repository: UserRepository instance
            user_factory: Factory for creating users
        """
        # Arrange
        user = user_factory(username="original")

        # Act
        user_repository.update(user.id, username="updated")

        # Assert
        updated_user = user_repository.find_by_id(user.id)
        assert updated_user.username == "updated"

    def test_delete_user_removes_from_database(self, user_repository, user_factory):
        """Test deleting user removes it from database.

        Args:
            user_repository: UserRepository instance
            user_factory: Factory for creating users
        """
        # Arrange
        user = user_factory()

        # Act
        user_repository.delete(user.id)

        # Assert
        deleted_user = user_repository.find_by_id(user.id)
        assert deleted_user is None


class TestUserPostRelationship:
    """Integration tests for User-Post relationship.

    These tests verify:
    - Relationships are correctly established
    - Cascade operations work
    - Queries across relationships work
    """

    def test_user_can_create_post(self, user_factory, post_factory, db_session):
        """Test that user can create a post.

        Args:
            user_factory: Factory for creating users
            post_factory: Factory for creating posts
            db_session: Database session
        """
        # Arrange
        user = user_factory(username="author")

        # Act
        post = post_factory(author=user, title="Test Post")

        # Assert
        assert post.author_id == user.id
        assert post.author.username == "author"

        # Verify relationship from user side
        db_session.refresh(user)
        assert len(user.posts) == 1
        assert user.posts[0].title == "Test Post"

    def test_user_can_have_multiple_posts(self, user_factory, post_factory, db_session):
        """Test that user can have multiple posts.

        Args:
            user_factory: Factory for creating users
            post_factory: Factory for creating posts
            db_session: Database session
        """
        # Arrange
        user = user_factory()

        # Act
        post1 = post_factory(author=user, title="Post 1")
        post2 = post_factory(author=user, title="Post 2")
        post3 = post_factory(author=user, title="Post 3")

        # Assert
        db_session.refresh(user)
        assert len(user.posts) == 3
        post_titles = [p.title for p in user.posts]
        assert "Post 1" in post_titles
        assert "Post 2" in post_titles
        assert "Post 3" in post_titles

    def test_deleting_user_cascades_to_posts(
        self, user_repository, post_repository, user_factory, post_factory
    ):
        """Test that deleting user also deletes their posts.

        Args:
            user_repository: UserRepository instance
            post_repository: PostRepository instance
            user_factory: Factory for creating users
            post_factory: Factory for creating posts
        """
        # Arrange
        user = user_factory()
        post1 = post_factory(author=user)
        post2 = post_factory(author=user)

        # Act
        user_repository.delete(user.id)

        # Assert
        assert user_repository.find_by_id(user.id) is None
        assert post_repository.find_by_id(post1.id) is None
        assert post_repository.find_by_id(post2.id) is None


class TestComplexQueries:
    """Integration tests for complex database queries.

    These tests verify:
    - Complex queries return correct results
    - Joins work correctly
    - Filtering and sorting work
    """

    def test_find_posts_by_author_username(
        self, post_repository, user_factory, post_factory
    ):
        """Test finding posts by author username.

        Args:
            post_repository: PostRepository instance
            user_factory: Factory for creating users
            post_factory: Factory for creating posts
        """
        # Arrange
        user1 = user_factory(username="alice")
        user2 = user_factory(username="bob")
        post1 = post_factory(author=user1, title="Alice's Post")
        post2 = post_factory(author=user2, title="Bob's Post")
        post3 = post_factory(author=user1, title="Another Alice Post")

        # Act
        alice_posts = post_repository.find_by_author_username("alice")

        # Assert
        assert len(alice_posts) == 2
        titles = [p.title for p in alice_posts]
        assert "Alice's Post" in titles
        assert "Another Alice Post" in titles
        assert "Bob's Post" not in titles

    def test_find_active_users_with_posts(
        self, user_repository, user_factory, post_factory
    ):
        """Test finding active users who have posts.

        Args:
            user_repository: UserRepository instance
            user_factory: Factory for creating users
            post_factory: Factory for creating posts
        """
        # Arrange
        active_with_post = user_factory(is_active=True)
        active_no_post = user_factory(is_active=True)
        inactive_with_post = user_factory(is_active=False)

        post_factory(author=active_with_post)
        post_factory(author=inactive_with_post)

        # Act
        users = user_repository.find_active_users_with_posts()

        # Assert
        assert len(users) == 1
        assert users[0].id == active_with_post.id


# Testing transactions and rollback
class TestTransactionBehavior:
    """Tests for transaction and rollback behavior.

    These tests verify:
    - Changes are isolated to transactions
    - Rollback works correctly
    - Fixtures provide clean state
    """

    def test_changes_in_one_test_dont_affect_another(
        self, user_repository, user_factory
    ):
        """Test that changes in one test don't affect another.

        Args:
            user_repository: UserRepository instance
            user_factory: Factory for creating users
        """
        # This test creates a user
        user = user_factory(username="test1")

        # Assert
        assert user_repository.count() == 1

    def test_database_starts_clean(self, user_repository):
        """Test that database starts clean for each test.

        Args:
            user_repository: UserRepository instance
        """
        # Even though previous test created a user,
        # this test should start with empty database
        assert user_repository.count() == 0


# Performance tests (marked as slow)
@pytest.mark.slow
class TestDatabasePerformance:
    """Tests for database performance.

    These tests verify:
    - Bulk operations work correctly
    - Performance is acceptable
    - Large datasets are handled
    """

    def test_bulk_insert_performance(self, user_repository, db_session):
        """Test bulk insert of many users.

        Args:
            user_repository: UserRepository instance
            db_session: Database session
        """
        # Arrange
        users = [
            User(username=f"user{i}", email=f"user{i}@example.com")
            for i in range(1000)
        ]

        # Act
        db_session.bulk_save_objects(users)
        db_session.commit()

        # Assert
        assert user_repository.count() == 1000
