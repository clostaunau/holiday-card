"""
Authentication Dependencies Template for FastAPI

Implements OAuth2 with JWT tokens and role-based authorization.
"""

from datetime import datetime, timedelta
from typing import Annotated, Optional
from enum import Enum

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Configuration (replace with your actual config)
SECRET_KEY = "your-secret-key-here"  # Use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Models
class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None


class Role(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# Password utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


# JWT token utilities
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in token (typically {"sub": user_id})
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData with user_id

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return TokenData(user_id=int(user_id))
    except JWTError:
        raise credentials_exception


# Database operations (replace with your actual database logic)
async def get_user_by_id(db: AsyncSession, user_id: int):
    """Fetch user from database by ID."""
    # Replace with actual database query
    # result = await db.execute(select(User).where(User.id == user_id))
    # return result.scalar_one_or_none()
    pass


async def get_user_by_username(db: AsyncSession, username: str):
    """Fetch user from database by username."""
    # Replace with actual database query
    # result = await db.execute(select(User).where(User.username == username))
    # return result.scalar_one_or_none()
    pass


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str
):
    """
    Authenticate user with username and password.

    Args:
        db: Database session
        username: Username
        password: Plain text password

    Returns:
        User object if authenticated, None otherwise
    """
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# Dependencies
async def get_db() -> AsyncSession:
    """Database session dependency."""
    # Replace with your actual database session logic
    # async with AsyncSessionLocal() as session:
    #     try:
    #         yield session
    #         await session.commit()
    #     except Exception:
    #         await session.rollback()
    #         raise
    pass


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Get current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token_data = decode_access_token(token)

    user = await get_user_by_id(db, user_id=token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[object, Depends(get_current_user)]
):
    """
    Ensure current user is active.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Active user object

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(required_role: Role):
    """
    Dependency factory for role-based authorization.

    Args:
        required_role: Required role for access

    Returns:
        Dependency function that checks user role

    Usage:
        @router.delete("/admin/users/{user_id}")
        async def delete_user(
            user_id: int,
            admin: Annotated[User, Depends(require_role(Role.ADMIN))]
        ):
            # Only admins can access this endpoint
            pass
    """
    async def check_role(
        current_user: Annotated[object, Depends(get_current_active_user)]
    ):
        # Admins have access to everything
        if current_user.role == Role.ADMIN:
            return current_user

        # Check if user has required role
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user

    return check_role


def require_any_role(*required_roles: Role):
    """
    Dependency factory for role-based authorization (any of multiple roles).

    Args:
        required_roles: Any of these roles grants access

    Returns:
        Dependency function that checks user role

    Usage:
        @router.get("/content/")
        async def get_content(
            user: Annotated[User, Depends(require_any_role(Role.ADMIN, Role.USER))]
        ):
            # Admins and users can access, guests cannot
            pass
    """
    async def check_role(
        current_user: Annotated[object, Depends(get_current_active_user)]
    ):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user

    return check_role


# Route examples (add to your router)
"""
from fastapi import APIRouter, Depends
from typing import Annotated

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    '''Login endpoint to get access token.'''
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    '''Get current user information.'''
    return current_user


@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(require_role(Role.ADMIN))]
):
    '''Delete a user (admin only).'''
    # Implementation
    pass


@router.get("/content/")
async def get_content(
    user: Annotated[User, Depends(require_any_role(Role.ADMIN, Role.USER))]
):
    '''Get content (admin or regular user).'''
    # Implementation
    pass
"""
