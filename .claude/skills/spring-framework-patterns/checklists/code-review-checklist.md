# Spring Framework Code Review Checklist

Use this checklist when reviewing Spring Boot applications.

## Architecture and Layering

- [ ] **Clear layer separation**: Controller → Service → Repository
- [ ] **Controllers are thin**: No business logic in controllers
- [ ] **Business logic in services**: All business rules in service layer
- [ ] **No repository access from controllers**: Controllers only call services
- [ ] **Proper package structure**: Organized by feature or layer

## Dependency Injection

- [ ] **Constructor injection used**: All required dependencies via constructor
- [ ] **No field injection**: No `@Autowired` on fields
- [ ] **Final fields**: All injected dependencies are final
- [ ] **Lombok used correctly**: `@RequiredArgsConstructor` for constructor injection
- [ ] **No circular dependencies**: If present, refactor design
- [ ] **Setter injection only for optional deps**: Used sparingly

## Controllers

- [ ] **RESTful URLs**: Follow REST conventions (plural nouns, proper nesting)
- [ ] **Correct HTTP methods**: GET, POST, PUT, DELETE used appropriately
- [ ] **Correct status codes**: 200, 201, 204, 400, 404, 409, 500
- [ ] **@Valid for validation**: Request validation with Bean Validation
- [ ] **DTOs used**: Not exposing entities directly
- [ ] **Pagination support**: List endpoints support pagination
- [ ] **Location header**: Created resources include Location header
- [ ] **ResponseEntity used**: Not returning naked objects

## Services

- [ ] **@Transactional on service methods**: Not on repository methods
- [ ] **readOnly=true for queries**: Optimization for read operations
- [ ] **Proper transaction boundaries**: Transactions start/end at appropriate points
- [ ] **Business validation**: Validation logic in service layer
- [ ] **Exception handling**: Throwing domain-specific exceptions
- [ ] **Logging**: Appropriate use of SLF4J logging
- [ ] **No entity exposure**: Returning DTOs, not entities

## Repositories

- [ ] **Correct interface**: Extends JpaRepository or appropriate interface
- [ ] **Query method naming**: Follows Spring Data conventions
- [ ] **@Query usage**: Custom queries properly written
- [ ] **No @Transactional**: Transaction management in service layer
- [ ] **Specifications for dynamic queries**: Using Specifications instead of string concatenation

## Data Transfer Objects (DTOs)

- [ ] **Separate request/response DTOs**: CreateRequest, UpdateRequest, DTO
- [ ] **Bean Validation annotations**: @NotNull, @NotBlank, @Email, etc.
- [ ] **No entities in API**: Entities never exposed in REST API
- [ ] **Proper mapping**: MapStruct or manual mapping
- [ ] **No sensitive data**: Passwords, tokens excluded from response DTOs

## Entities

- [ ] **JPA annotations present**: @Entity, @Table, @Id, @GeneratedValue
- [ ] **No business logic**: Entities are pure data models
- [ ] **No dependency injection**: No @Autowired in entities
- [ ] **Relationships defined**: @OneToMany, @ManyToOne, etc. if needed
- [ ] **Fetch strategies**: Lazy loading configured where appropriate
- [ ] **Equals/hashCode**: Implemented based on ID or natural key

## Exception Handling

- [ ] **@RestControllerAdvice present**: Global exception handler
- [ ] **Custom exceptions**: Domain-specific exceptions defined
- [ ] **Proper HTTP status codes**: Exceptions mapped to correct status codes
- [ ] **Consistent error format**: ErrorResponse DTO used consistently
- [ ] **Validation errors handled**: MethodArgumentNotValidException handled
- [ ] **No generic catches**: Specific exceptions caught and handled

## Security

- [ ] **SecurityFilterChain configured**: Spring Security 6+ pattern
- [ ] **Authentication enabled**: Endpoints properly secured
- [ ] **Authorization rules**: Role-based access control configured
- [ ] **Method security**: @PreAuthorize used where needed
- [ ] **Password encoding**: BCryptPasswordEncoder configured
- [ ] **CSRF configured**: Enabled for stateful, disabled for stateless with justification
- [ ] **JWT implementation**: Properly implemented if using JWT
- [ ] **No hardcoded secrets**: Secrets in environment variables

## Configuration

- [ ] **application.yml used**: Proper YAML configuration
- [ ] **Profile-specific config**: application-{profile}.yml files
- [ ] **@ConfigurationProperties**: Type-safe configuration properties
- [ ] **Externalized config**: No hardcoded values
- [ ] **Environment variables**: Sensitive data from env vars
- [ ] **Connection pooling**: HikariCP configured

## Testing

- [ ] **Unit tests for services**: Using @ExtendWith(MockitoExtension.class)
- [ ] **Integration tests**: Using @SpringBootTest where appropriate
- [ ] **Repository tests**: Using @DataJpaTest
- [ ] **Controller tests**: Using @WebMvcTest
- [ ] **Mocking external deps**: Database, email, APIs mocked in unit tests
- [ ] **Test coverage**: Minimum 80% coverage
- [ ] **Assertions**: Proper assertions, not just execution

## Performance

- [ ] **Caching enabled**: @Cacheable used where appropriate
- [ ] **Async operations**: @Async for long-running operations
- [ ] **N+1 queries avoided**: Proper join fetching strategies
- [ ] **Connection pool sized**: Appropriate pool size configured
- [ ] **Lazy loading**: Used to avoid unnecessary data fetching
- [ ] **Pagination**: Large result sets paginated

## Code Quality

- [ ] **No code duplication**: DRY principle followed
- [ ] **Meaningful names**: Classes, methods, variables properly named
- [ ] **Methods are focused**: Single Responsibility Principle
- [ ] **No commented code**: Old code removed, not commented
- [ ] **Logging levels**: DEBUG, INFO, WARN, ERROR used appropriately
- [ ] **No System.out.println**: Use logger instead
- [ ] **Java conventions**: Follows Java naming and style conventions
- [ ] **Lombok used wisely**: Not overused, only for boilerplate

## Common Anti-Patterns to Avoid

- [ ] **No field injection**: Constructor injection used instead
- [ ] **No service bypassing**: Controllers don't call repositories directly
- [ ] **No entity exposure**: DTOs used for API contracts
- [ ] **No @Transactional on repositories**: Only on services
- [ ] **No circular dependencies**: Design refactored if present
- [ ] **No business logic in entities**: Entities are data models only
- [ ] **No missing connection pooling**: HikariCP configured
- [ ] **No @Lazy as band-aid**: Circular deps properly resolved
- [ ] **No mutable singleton state**: Stateless services

## Documentation

- [ ] **JavaDoc for public API**: Public methods documented
- [ ] **README present**: Project setup and running instructions
- [ ] **API documentation**: Swagger/OpenAPI configured
- [ ] **Configuration documented**: Important properties documented

## Build and Dependencies

- [ ] **Maven/Gradle up to date**: Using current versions
- [ ] **Spring Boot version**: Using supported Spring Boot version
- [ ] **Java version**: Java 17+ for Spring Boot 3.x
- [ ] **Dependency management**: No version conflicts
- [ ] **Starter dependencies**: Using Spring Boot starters

## Deployment Readiness

- [ ] **Health endpoint**: Actuator health check enabled
- [ ] **Metrics**: Actuator metrics configured
- [ ] **Logging configured**: Production-ready logging
- [ ] **Profile support**: Dev, test, prod profiles
- [ ] **Environment-specific config**: Properties externalized

---

## Quick Reference: Common Issues

| Issue | Fix |
|-------|-----|
| Field injection | Change to constructor injection |
| Controller calling repository | Add service layer |
| Entity exposed in API | Create and use DTO |
| No pagination | Add Pageable parameter |
| Wrong HTTP status code | Use ResponseEntity with correct status |
| Missing @Transactional | Add to service method |
| Validation not working | Add @Valid to @RequestBody |
| Circular dependency | Refactor - extract common service |
| Missing error handling | Add @RestControllerAdvice |
| No connection pooling | Configure HikariCP in application.yml |

---

**Review Tips:**

1. Start with architecture - verify proper layering
2. Check dependency injection patterns
3. Review REST API design
4. Examine transaction boundaries
5. Validate security configuration
6. Check test coverage
7. Look for common anti-patterns
8. Verify configuration management

**Common Patterns to Look For:**

✅ **Good:**
- Constructor injection
- Service layer between controller and repository
- DTOs for API contracts
- @Transactional on service methods
- Global exception handling
- Proper HTTP status codes

❌ **Bad:**
- Field injection
- Controllers calling repositories directly
- Entities in API responses
- @Transactional on repositories
- No exception handling
- Always returning 200 OK
