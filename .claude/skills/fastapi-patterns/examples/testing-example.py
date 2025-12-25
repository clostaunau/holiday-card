"""
FastAPI Testing Examples

Demonstrates comprehensive testing patterns for FastAPI applications.
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Assuming these imports from your application
# from app.main import app
# from app.database import Base, get_db
# from app.models import User
# from app.dependencies import get_current_user


# ============================================================================
# SYNCHRONOUS TESTING (Simple Tests)
# ============================================================================

def test_root_endpoint():
    """Test the root endpoint using TestClient."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check():
    """Test health check endpoint."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_user():
    """Test user creation."""
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "TestPass123"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data
    assert "password" not in data  # Password should not be in response


def test_create_user_duplicate_email():
    """Test that duplicate email raises error."""
    from app.main import app

    client = TestClient(app)

    # Create first user
    client.post(
        "/api/v1/users/",
        json={
            "email": "duplicate@example.com",
            "username": "user1",
            "password": "Pass123"
        }
    )

    # Try to create second user with same email
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "duplicate@example.com",
            "username": "user2",
            "password": "Pass123"
        }
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


# ============================================================================
# ASYNC TESTING
# ============================================================================

@pytest.mark.asyncio
async def test_async_list_users():
    """Test listing users with async client."""
    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/users/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_async_create_and_get_user():
    """Test creating and retrieving a user."""
    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create user
        create_response = await ac.post(
            "/api/v1/users/",
            json={
                "email": "async@example.com",
                "username": "asyncuser",
                "password": "AsyncPass123"
            }
        )
        assert create_response.status_code == 201
        user_id = create_response.json()["id"]

        # Get user
        get_response = await ac.get(f"/api/v1/users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == user_id


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

# Synchronous test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Async test database
ASYNC_SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test_async.db"

async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
AsyncTestingSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture
def db_session():
    """Create a test database session (synchronous)."""
    from app.database import Base

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    yield override_get_db

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def async_db_session():
    """Create a test database session (async)."""
    from app.database import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with AsyncTestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    yield override_get_db

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client(db_session):
    """Create a test client with database override."""
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(async_db_session):
    """Create an async test client with database override."""
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = async_db_session

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# TESTS WITH FIXTURES
# ============================================================================

def test_with_fixture(client):
    """Test using client fixture."""
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_with_fixture(async_client):
    """Test using async client fixture."""
    response = await async_client.get("/health")
    assert response.status_code == 200


# ============================================================================
# DEPENDENCY OVERRIDE TESTS
# ============================================================================

def test_override_authentication():
    """Test endpoint with overridden authentication."""
    from app.main import app
    from app.dependencies import get_current_user
    from app.models import User

    # Mock user
    def override_get_current_user():
        return User(
            id=1,
            email="test@example.com",
            username="testuser",
            is_active=True,
            is_superuser=False
        )

    # Override dependency
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

    # Clean up
    app.dependency_overrides.clear()


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

def test_login_success(client):
    """Test successful login."""
    # First create a user
    client.post(
        "/api/v1/users/",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "LoginPass123"
        }
    )

    # Now login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "loginuser",
            "password": "LoginPass123"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "nonexistent",
            "password": "wrongpass"
        }
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_protected_endpoint_without_token(client):
    """Test accessing protected endpoint without authentication."""
    response = client.get("/api/v1/users/")

    assert response.status_code == 401


def test_protected_endpoint_with_token(client):
    """Test accessing protected endpoint with valid token."""
    # Create user
    client.post(
        "/api/v1/users/",
        json={
            "email": "auth@example.com",
            "username": "authuser",
            "password": "AuthPass123"
        }
    )

    # Login to get token
    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "authuser",
            "password": "AuthPass123"
        }
    )
    token = login_response.json()["access_token"]

    # Access protected endpoint
    response = client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_validation_error_invalid_email(client):
    """Test validation error for invalid email."""
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "not-an-email",
            "username": "testuser",
            "password": "Pass123"
        }
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("email" in str(error).lower() for error in errors)


def test_validation_error_short_password(client):
    """Test validation error for short password."""
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "short"
        }
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("password" in str(error).lower() for error in errors)


# ============================================================================
# MOCKING EXTERNAL SERVICES
# ============================================================================

@pytest.mark.asyncio
async def test_with_mocked_external_service(async_client, monkeypatch):
    """Test endpoint that calls external service with mocking."""
    from unittest.mock import AsyncMock

    # Mock external API call
    async def mock_fetch_external_data(*args, **kwargs):
        return {"data": "mocked"}

    # Apply mock
    monkeypatch.setattr(
        "app.services.external_api.fetch_data",
        mock_fetch_external_data
    )

    response = await async_client.get("/api/v1/external-data/")

    assert response.status_code == 200
    assert response.json()["data"] == "mocked"


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

@pytest.mark.parametrize("endpoint,expected_status", [
    ("/", 200),
    ("/health", 200),
    ("/api/v1/users/", 401),  # Requires auth
    ("/nonexistent", 404),
])
def test_endpoints_status_codes(client, endpoint, expected_status):
    """Test various endpoints return expected status codes."""
    response = client.get(endpoint)
    assert response.status_code == expected_status


@pytest.mark.parametrize("invalid_data", [
    {"username": "test", "password": "pass"},  # Missing email
    {"email": "test@example.com", "password": "pass"},  # Missing username
    {"email": "test@example.com", "username": "test"},  # Missing password
    {},  # Empty
])
def test_create_user_invalid_data(client, invalid_data):
    """Test user creation with various invalid data."""
    response = client.post("/api/v1/users/", json=invalid_data)
    assert response.status_code == 422


# ============================================================================
# CONFTEST.PY EXAMPLE
# ============================================================================

"""
# conftest.py - Place this in your tests/ directory

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import Base, get_db

# Test database URL
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

# Synchronous engine for simple tests
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async engine for async tests
async_engine = create_async_engine(
    "sqlite+aiosqlite:///./test_async.db",
    connect_args={"check_same_thread": False}
)
AsyncTestingSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def setup_database():
    '''Create test database tables.'''
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_database):
    '''Get database session for testing.'''
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    '''Get test client with database override.'''
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    '''Get async test client.'''
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with AsyncTestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
"""
