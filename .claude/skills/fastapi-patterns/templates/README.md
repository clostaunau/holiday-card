# FastAPI Templates

This directory contains reusable templates for common FastAPI patterns.

## Available Templates

### 1. repository-pattern.py

**Purpose**: Generic repository pattern implementation for data access layer.

**When to use**:
- Abstracting database operations
- Implementing CRUD operations
- Separating data access from business logic

**Key features**:
- Generic base repository with type hints
- Common CRUD operations (get, list, create, update, delete)
- Example of custom repository methods
- Repository factory pattern

**Usage**:
```python
from app.repositories.base import BaseRepository
from app.models import User, UserCreate, UserUpdate

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    # Add custom methods
    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(self.model).where(self.model.email == email)
        )
        return result.scalar_one_or_none()
```

### 2. auth-dependencies.py

**Purpose**: Complete authentication and authorization implementation with JWT.

**When to use**:
- Implementing user authentication
- Adding role-based access control
- Securing API endpoints

**Key features**:
- Password hashing with bcrypt
- JWT token generation and validation
- OAuth2 password flow
- Current user dependency
- Role-based authorization factories

**Usage**:
```python
from app.dependencies.auth import get_current_active_user, require_role, Role
from typing import Annotated
from fastapi import Depends

@router.get("/protected/")
async def protected_endpoint(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return {"user": current_user.username}

@router.delete("/admin/resource/{id}")
async def admin_only_endpoint(
    id: int,
    admin: Annotated[User, Depends(require_role(Role.ADMIN))]
):
    # Only admins can access
    pass
```

### 3. async-database-repository.py

**Purpose**: Complete example of async database integration with SQLAlchemy.

**When to use**:
- Setting up async database connection
- Creating database models
- Implementing repositories
- Building CRUD endpoints

**Key features**:
- Async SQLAlchemy engine configuration
- Database models with type hints
- Pydantic request/response models
- Complete repository implementations
- Database session dependency
- Example FastAPI routes

**Usage**:
```python
from app.database import get_db, AsyncSession
from app.repositories import UserRepository
from typing import Annotated
from fastapi import Depends

@router.get("/users/")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)]
):
    repo = UserRepository(db)
    users = await repo.list_users()
    return users
```

## Integration Guide

### Step 1: Choose Templates

Identify which templates you need based on your requirements:
- **Authentication needed?** → Use `auth-dependencies.py`
- **Database operations?** → Use `async-database-repository.py`
- **Data access abstraction?** → Use `repository-pattern.py`

### Step 2: Adapt to Your Project

1. Copy the relevant template(s) to your project
2. Update imports to match your project structure
3. Replace placeholder configurations with your settings
4. Customize to fit your specific requirements

### Step 3: Integrate with Main App

```python
# main.py
from fastapi import FastAPI
from app.routers import users, items
from app.database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
```

## Best Practices

### Repository Pattern

1. **One repository per model**: Keep repositories focused on a single model
2. **Business logic in services**: Repositories should only handle data access
3. **Type hints everywhere**: Use generics for reusable base repositories
4. **Async all the way**: Use async methods for all I/O operations

### Authentication

1. **Environment variables**: Never hardcode secret keys
2. **Strong passwords**: Enforce password requirements
3. **Token expiration**: Set appropriate token expiration times
4. **Refresh tokens**: Consider implementing refresh token pattern for production
5. **HTTPS only**: Always use HTTPS in production

### Database

1. **Connection pooling**: Configure appropriate pool size
2. **Session management**: Always use dependency injection for sessions
3. **Error handling**: Properly handle and rollback failed transactions
4. **Migrations**: Use Alembic for database migrations
5. **Eager loading**: Avoid N+1 queries with proper eager loading

## Customization Examples

### Custom Repository Method

```python
class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    async def search_by_name(
        self,
        search_term: str,
        limit: int = 50
    ) -> List[User]:
        result = await self.db.execute(
            select(self.model)
            .where(self.model.full_name.ilike(f"%{search_term}%"))
            .limit(limit)
        )
        return list(result.scalars().all())
```

### Custom Authorization Rule

```python
def require_owner_or_admin(resource_id_param: str = "id"):
    """Check if user is resource owner or admin."""
    async def check_ownership(
        resource_id: int,
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)]
    ):
        if current_user.is_admin:
            return current_user

        resource = await get_resource(db, resource_id)
        if resource.owner_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this resource"
            )

        return current_user

    return check_ownership
```

### Custom Validation

```python
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char in '!@#$%^&*' for char in v):
            raise ValueError('Password must contain at least one special character')
        return v
```

## Dependencies

All templates require these core dependencies:

```txt
fastapi>=0.104.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
sqlalchemy>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.5
```

For async database support:
```txt
asyncpg>=0.28.0  # For PostgreSQL
aiomysql>=0.2.0  # For MySQL
aiosqlite>=0.19.0  # For SQLite
```

## Testing

Each template includes inline examples of how to test the implementation. See `examples/testing-example.py` for comprehensive testing patterns.

## Troubleshooting

### Common Issues

**Issue**: "RuntimeError: no running event loop"
- **Solution**: Ensure you're using async database session and await all operations

**Issue**: "TypeError: can't pickle async generator"
- **Solution**: Use `expire_on_commit=False` in AsyncSessionLocal configuration

**Issue**: "sqlalchemy.exc.PendingRollbackError"
- **Solution**: Properly handle exceptions and rollback in database session dependency

**Issue**: "jose.exceptions.JWTError: Signature verification failed"
- **Solution**: Ensure SECRET_KEY is consistent and not changing between requests

## Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## Contributing

When adding new templates:
1. Follow existing template structure
2. Include comprehensive docstrings
3. Add usage examples
4. Update this README
5. Ensure templates are production-ready
