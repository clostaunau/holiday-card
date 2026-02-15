"""
Repository Pattern Template for FastAPI with SQLAlchemy Async

This template demonstrates the repository pattern for data access layer abstraction.
"""

from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository with common CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
            def __init__(self, db: AsyncSession):
                super().__init__(User, db)
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            db: Async database session
        """
        self.model = model
        self.db = db

    async def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        result = await self.db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Pydantic model with creation data

        Returns:
            Created model instance
        """
        obj_data = obj_in.model_dump()
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        id: int,
        obj_in: UpdateSchemaType
    ) -> Optional[ModelType]:
        """
        Update an existing record.

        Args:
            id: Record ID
            obj_in: Pydantic model with update data

        Returns:
            Updated model instance or None if not found
        """
        db_obj = await self.get(id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        """
        Delete a record.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get(id)
        if not db_obj:
            return False

        await self.db.delete(db_obj)
        return True


# Example: Specific repository with custom methods
class UserRepository(BaseRepository):
    """User-specific repository with custom queries."""

    async def get_by_email(self, email: str) -> Optional[ModelType]:
        """Get user by email address."""
        result = await self.db.execute(
            select(self.model).where(self.model.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[ModelType]:
        """Get user by username."""
        result = await self.db.execute(
            select(self.model).where(self.model.username == username)
        )
        return result.scalar_one_or_none()

    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get only active users."""
        result = await self.db.execute(
            select(self.model)
            .where(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def search_by_name(
        self,
        name: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Search users by name (case-insensitive)."""
        result = await self.db.execute(
            select(self.model)
            .where(self.model.full_name.ilike(f"%{name}%"))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


# Example: Repository factory pattern
class RepositoryFactory:
    """Factory for creating repository instances."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._repositories = {}

    def get_user_repository(self) -> UserRepository:
        """Get or create UserRepository instance."""
        if "user" not in self._repositories:
            from app.models import User
            self._repositories["user"] = UserRepository(User, self.db)
        return self._repositories["user"]

    def get_item_repository(self) -> BaseRepository:
        """Get or create ItemRepository instance."""
        if "item" not in self._repositories:
            from app.models import Item, ItemCreate, ItemUpdate
            self._repositories["item"] = BaseRepository[Item, ItemCreate, ItemUpdate](
                Item, self.db
            )
        return self._repositories["item"]
