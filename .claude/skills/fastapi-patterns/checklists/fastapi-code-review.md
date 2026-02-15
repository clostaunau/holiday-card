# FastAPI Code Review Checklist

Use this checklist when reviewing FastAPI code to ensure best practices are followed.

## Application Structure

- [ ] Project follows recommended directory structure (routers, models, services, repositories)
- [ ] Configuration is managed through Pydantic Settings with environment variables
- [ ] Routers are properly organized by domain/resource
- [ ] Business logic is separated from route handlers (service layer)
- [ ] Data access is abstracted through repository pattern
- [ ] Main application uses lifespan context manager for startup/shutdown

## Path Operations

- [ ] All endpoints have type hints for parameters and return values
- [ ] `response_model` is specified for all endpoints
- [ ] Appropriate HTTP status codes are used (201 for creation, 204 for deletion, etc.)
- [ ] Endpoints have `summary` and `description` for documentation
- [ ] Endpoints are organized with `tags` for API documentation
- [ ] Error responses are documented with `responses` parameter
- [ ] Path parameters use `Path()` with validation
- [ ] Query parameters use `Query()` with validation and defaults

## Pydantic Models

- [ ] Separate models for Create, Update, and Response (not reusing same model)
- [ ] Response models never include sensitive data (passwords, secrets)
- [ ] Field validation is comprehensive (min/max length, regex, custom validators)
- [ ] Models use `model_config` for ORM mode and examples
- [ ] Optional fields are properly typed with `Optional[]` or `| None`
- [ ] Model inheritance is used to avoid duplication (Base models)
- [ ] Custom validators use `@field_validator` or `@model_validator`
- [ ] JSON schema examples are provided for documentation

## Dependency Injection

- [ ] Database sessions use `Depends(get_db)` instead of creating connections
- [ ] Authentication uses dependency pattern, not implemented in each route
- [ ] Shared dependencies are defined once and reused
- [ ] Dependencies with cleanup use `yield` pattern
- [ ] Type hints use `Annotated[Type, Depends(...)]` for clarity
- [ ] Router-level dependencies are used for shared requirements
- [ ] No hardcoded values that should come from dependencies

## Async Patterns

- [ ] `async def` is used for I/O-bound operations (database, HTTP calls)
- [ ] `def` is used for CPU-bound operations
- [ ] All async operations use `await` (no forgotten awaits)
- [ ] No blocking operations in async functions (`time.sleep`, synchronous I/O)
- [ ] Async database driver is used (asyncpg, aiomysql, aiosqlite)
- [ ] Background tasks use `BackgroundTasks` for long operations
- [ ] Concurrent operations use `asyncio.gather()` when appropriate
- [ ] No `asyncio.run()` inside async functions

## Database Integration

- [ ] Async database engine is properly configured
- [ ] Connection pooling is configured appropriately
- [ ] Database sessions are managed through dependency injection
- [ ] Sessions properly commit on success and rollback on error
- [ ] N+1 query problems are avoided (use eager loading)
- [ ] SQLAlchemy 2.0 syntax is used (not legacy patterns)
- [ ] Repository pattern is used for data access
- [ ] Database models use proper type hints with `Mapped[]`
- [ ] Indexes are defined on frequently queried fields
- [ ] Migrations are managed (Alembic)

## Authentication & Authorization

- [ ] Passwords are hashed with bcrypt or equivalent
- [ ] JWT tokens are used for stateless authentication
- [ ] Secret keys are loaded from environment variables
- [ ] Token expiration is properly configured
- [ ] OAuth2PasswordBearer is used for token scheme
- [ ] Authentication is implemented as dependency
- [ ] Role-based authorization uses dependency factories
- [ ] Inactive users are prevented from accessing protected routes
- [ ] CORS is properly configured for production

## Error Handling

- [ ] HTTPException is used for expected errors
- [ ] Custom exception handlers are defined for domain exceptions
- [ ] Validation errors return 422 with clear messages
- [ ] 404 errors are raised when resources not found
- [ ] 403 errors are raised for insufficient permissions
- [ ] Error responses have consistent structure
- [ ] No bare `except:` clauses catching all exceptions
- [ ] Sensitive information is not exposed in error messages

## Testing

- [ ] Tests use `TestClient` or `AsyncClient` appropriately
- [ ] Database dependencies are overridden in tests
- [ ] Test database is separate from development database
- [ ] Fixtures are used for common setup
- [ ] Authentication is tested (login, protected endpoints)
- [ ] Validation errors are tested
- [ ] Both success and failure cases are tested
- [ ] External services are mocked
- [ ] Tests clean up after themselves (database, files)
- [ ] Async tests are marked with `@pytest.mark.asyncio`

## OpenAPI Documentation

- [ ] API title and version are configured
- [ ] Endpoints have clear summaries and descriptions
- [ ] Request/response examples are provided
- [ ] Tags are used to organize endpoints
- [ ] Error responses are documented
- [ ] Authentication scheme is documented
- [ ] Deprecated endpoints are marked as deprecated

## Performance

- [ ] Expensive operations are cached when appropriate
- [ ] Database queries are optimized (no N+1 queries)
- [ ] Connection pooling is configured
- [ ] Async is used for concurrent I/O operations
- [ ] Background tasks are used for long-running operations
- [ ] Response models only select needed fields
- [ ] Pagination is implemented for list endpoints
- [ ] No blocking operations in async code paths

## Security

- [ ] No sensitive data in logs
- [ ] Passwords are never returned in responses
- [ ] SQL injection is prevented (using ORM properly)
- [ ] CORS is properly configured
- [ ] Rate limiting is implemented for public endpoints
- [ ] Input validation is comprehensive
- [ ] Authentication is required for protected endpoints
- [ ] Authorization is checked for sensitive operations
- [ ] Dependencies are up to date (no known vulnerabilities)

## Code Quality

- [ ] Type hints are used throughout
- [ ] Code follows PEP 8 style guide
- [ ] Functions are appropriately sized (not too long)
- [ ] No code duplication (DRY principle)
- [ ] Variable and function names are descriptive
- [ ] Magic numbers/strings are replaced with constants
- [ ] Imports are organized (standard library, third-party, local)
- [ ] No commented-out code
- [ ] Docstrings for complex functions

## Common Anti-Patterns to Avoid

- [ ] ❌ Using `async def` without `await`
- [ ] ❌ Blocking operations in async functions
- [ ] ❌ Missing type hints
- [ ] ❌ Creating database connections in routes
- [ ] ❌ Not using Pydantic models for validation
- [ ] ❌ Exposing passwords in response models
- [ ] ❌ Ignoring status codes (always 200)
- [ ] ❌ No error handling
- [ ] ❌ Manual validation instead of Pydantic
- [ ] ❌ Hardcoded configuration values

## FastAPI-Specific Best Practices

- [ ] Uses FastAPI 0.100+ features (lifespan, Annotated)
- [ ] Pydantic 2.0 syntax is used (model_config, etc.)
- [ ] SQLAlchemy 2.0 syntax is used
- [ ] Proper use of `from_attributes` for ORM models
- [ ] Response models use `model_dump()` not `dict()`
- [ ] Settings use `pydantic_settings.BaseSettings`

## Additional Checks

- [ ] Environment variables are documented in `.env.example`
- [ ] README includes setup instructions
- [ ] Requirements are properly specified
- [ ] Docker configuration if applicable
- [ ] Health check endpoint exists
- [ ] Logging is configured appropriately
- [ ] Metrics/monitoring if in production

---

## Review Process

1. **First Pass**: Check structure and organization
2. **Second Pass**: Review models and validation
3. **Third Pass**: Examine endpoints and business logic
4. **Fourth Pass**: Verify async patterns and database usage
5. **Fifth Pass**: Security and error handling
6. **Final Pass**: Testing coverage and documentation

## Severity Levels

- **Critical**: Security issues, data loss risks, production blockers
- **High**: Performance problems, broken functionality, missing error handling
- **Medium**: Code quality issues, missing tests, incomplete documentation
- **Low**: Style inconsistencies, minor optimization opportunities

## Common Findings

### Critical
- Exposed passwords in response models
- SQL injection vulnerabilities
- Missing authentication on protected endpoints
- Hardcoded secrets

### High
- N+1 query problems
- Blocking operations in async code
- Missing error handling
- No input validation

### Medium
- Missing type hints
- Poor separation of concerns
- Duplicated code
- Missing tests

### Low
- Missing docstrings
- Inconsistent naming
- Unclear variable names
- Missing API documentation
