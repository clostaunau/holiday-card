# Spring Framework Patterns - Examples

This directory contains complete, working examples demonstrating Spring Framework best practices.

## Available Examples

### 1. UserServiceExample.java

**Purpose:** Comprehensive service layer example showing all key patterns.

**Demonstrates:**
- Constructor injection with Lombok
- Transaction management
- Read-only transaction optimization
- Business validation
- Entity-DTO mapping
- Exception handling
- Logging
- Password encoding
- Async operations (email service)

**Key Patterns:**
```java
// Constructor injection
@RequiredArgsConstructor
private final UserRepository userRepository;

// Read-only transaction
@Transactional(readOnly = true)
public Page<UserDTO> findAll(Pageable pageable)

// Write transaction
@Transactional
public UserDTO createUser(CreateUserRequest request)

// Business validation
if (userRepository.existsByEmail(request.getEmail())) {
    throw new EmailAlreadyExistsException(request.getEmail());
}

// Entity-DTO mapping
private UserDTO mapToDTO(User user)
```

### 2. SecurityConfigExample.java

**Purpose:** Complete Spring Security 6+ configuration for REST API.

**Demonstrates:**
- SecurityFilterChain (Spring Security 6 pattern)
- JWT authentication filter integration
- Stateless session management
- CORS configuration
- Role-based authorization
- Method security enablement
- Password encoder configuration
- Authentication manager setup

**Key Patterns:**
```java
// SecurityFilterChain instead of WebSecurityConfigurerAdapter
@Bean
public SecurityFilterChain filterChain(HttpSecurity http)

// Stateless session for JWT
.sessionManagement(session -> session
    .sessionCreationPolicy(SessionCreationPolicy.STATELESS))

// Role-based authorization
.requestMatchers("/api/v1/admin/**").hasRole("ADMIN")

// BCrypt password encoder
@Bean
public PasswordEncoder passwordEncoder() {
    return new BCryptPasswordEncoder(12);
}
```

## Complete Example: User Management Feature

### Directory Structure
```
src/main/java/com/example/app/
├── controller/
│   └── UserController.java
├── service/
│   └── UserService.java
├── repository/
│   └── UserRepository.java
├── entity/
│   └── User.java
├── dto/
│   ├── UserDTO.java
│   ├── CreateUserRequest.java
│   └── UpdateUserRequest.java
├── exception/
│   ├── ResourceNotFoundException.java
│   ├── EmailAlreadyExistsException.java
│   └── GlobalExceptionHandler.java
└── config/
    └── SecurityConfig.java
```

### Entity Layer

**User.java**
```java
@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false)
    private String email;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String password;

    private boolean active;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
```

### DTO Layer

**UserDTO.java**
```java
@Data
public class UserDTO {
    private Long id;
    private String email;
    private String name;
    private boolean active;
    private LocalDateTime createdAt;
    // Note: password is NOT included
}
```

**CreateUserRequest.java**
```java
@Data
public class CreateUserRequest {

    @NotBlank(message = "Email is required")
    @Email(message = "Email must be valid")
    private String email;

    @NotBlank(message = "Name is required")
    @Size(min = 2, max = 100, message = "Name must be between 2 and 100 characters")
    private String name;

    @NotBlank(message = "Password is required")
    @Size(min = 8, message = "Password must be at least 8 characters")
    private String password;
}
```

**UpdateUserRequest.java**
```java
@Data
public class UpdateUserRequest {

    @Email(message = "Email must be valid")
    private String email;

    @Size(min = 2, max = 100, message = "Name must be between 2 and 100 characters")
    private String name;
}
```

### Repository Layer

**UserRepository.java**
```java
@Repository
public interface UserRepository extends JpaRepository<User, Long>,
                                       JpaSpecificationExecutor<User> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    List<User> findByActiveTrue();

    @Query("SELECT u FROM User u WHERE u.createdAt > :date")
    List<User> findRecentUsers(@Param("date") LocalDateTime date);
}
```

### Service Layer

See `UserServiceExample.java` for complete service implementation.

### Controller Layer

**UserController.java**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping
    public ResponseEntity<Page<UserDTO>> getAllUsers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "id") String sortBy) {

        Pageable pageable = PageRequest.of(page, size, Sort.by(sortBy));
        Page<UserDTO> users = userService.findAll(pageable);
        return ResponseEntity.ok(users);
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserDTO> getUserById(@PathVariable Long id) {
        return userService.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<UserDTO> createUser(@Valid @RequestBody CreateUserRequest request) {
        UserDTO created = userService.createUser(request);
        URI location = ServletUriComponentsBuilder
                .fromCurrentRequest()
                .path("/{id}")
                .buildAndExpand(created.getId())
                .toUri();
        return ResponseEntity.created(location).body(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<UserDTO> updateUser(
            @PathVariable Long id,
            @Valid @RequestBody UpdateUserRequest request) {

        return userService.updateUser(id, request)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable Long id) {
        userService.deleteUser(id);
        return ResponseEntity.noContent().build();
    }
}
```

### Exception Layer

**ResourceNotFoundException.java**
```java
public class ResourceNotFoundException extends BusinessException {

    public ResourceNotFoundException(String resourceName, Long id) {
        super(String.format("%s with id %d not found", resourceName, id),
              "RESOURCE_NOT_FOUND");
    }
}
```

**EmailAlreadyExistsException.java**
```java
public class EmailAlreadyExistsException extends BusinessException {

    public EmailAlreadyExistsException(String email) {
        super(String.format("Email %s already exists", email),
              "EMAIL_ALREADY_EXISTS");
    }
}
```

**BusinessException.java** (Base exception)
```java
public abstract class BusinessException extends RuntimeException {

    private final String errorCode;

    public BusinessException(String message, String errorCode) {
        super(message);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}
```

**GlobalExceptionHandler.java**

See templates/GlobalExceptionHandler.java.template

### Testing Examples

**Unit Test - UserServiceTest.java**
```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private EmailService emailService;

    @InjectMocks
    private UserService userService;

    @Test
    void createUser_WithValidData_ShouldCreateUser() {
        // Arrange
        CreateUserRequest request = new CreateUserRequest();
        request.setEmail("test@example.com");
        request.setName("Test User");
        request.setPassword("password123");

        User user = new User();
        user.setId(1L);
        user.setEmail(request.getEmail());
        user.setName(request.getName());

        when(userRepository.existsByEmail(request.getEmail())).thenReturn(false);
        when(passwordEncoder.encode(request.getPassword())).thenReturn("encoded");
        when(userRepository.save(any(User.class))).thenReturn(user);

        // Act
        UserDTO result = userService.createUser(request);

        // Assert
        assertNotNull(result);
        assertEquals(1L, result.getId());
        assertEquals("test@example.com", result.getEmail());

        verify(userRepository).existsByEmail(request.getEmail());
        verify(passwordEncoder).encode(request.getPassword());
        verify(userRepository).save(any(User.class));
    }

    @Test
    void createUser_WithExistingEmail_ShouldThrowException() {
        // Arrange
        CreateUserRequest request = new CreateUserRequest();
        request.setEmail("existing@example.com");

        when(userRepository.existsByEmail(request.getEmail())).thenReturn(true);

        // Act & Assert
        assertThrows(EmailAlreadyExistsException.class,
            () -> userService.createUser(request));

        verify(userRepository).existsByEmail(request.getEmail());
        verify(userRepository, never()).save(any(User.class));
    }
}
```

**Integration Test - UserControllerIntegrationTest.java**
```java
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class UserControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        userRepository.deleteAll();
    }

    @Test
    void createUser_WithValidData_ShouldReturn201() throws Exception {
        CreateUserRequest request = new CreateUserRequest();
        request.setEmail("test@example.com");
        request.setName("Test User");
        request.setPassword("password123");

        mockMvc.perform(post("/api/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(header().exists("Location"))
                .andExpect(jsonPath("$.email").value("test@example.com"))
                .andExpect(jsonPath("$.name").value("Test User"));

        assertEquals(1, userRepository.count());
    }

    @Test
    void createUser_WithInvalidEmail_ShouldReturn400() throws Exception {
        CreateUserRequest request = new CreateUserRequest();
        request.setEmail("invalid-email");
        request.setName("Test User");
        request.setPassword("password123");

        mockMvc.perform(post("/api/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.email").exists());
    }
}
```

## Configuration Examples

**application.yml**
```yaml
spring:
  application:
    name: user-management-service

  datasource:
    url: jdbc:postgresql://localhost:5432/userdb
    username: postgres
    password: password
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5

  jpa:
    hibernate:
      ddl-auto: validate
    show-sql: false
    properties:
      hibernate:
        format_sql: true
        dialect: org.hibernate.dialect.PostgreSQLDialect

  cache:
    type: caffeine
    caffeine:
      spec: maximumSize=500,expireAfterAccess=600s

server:
  port: 8080

logging:
  level:
    root: INFO
    com.example.app: DEBUG

app:
  jwt:
    secret: ${JWT_SECRET:default-secret}
    expiration: 3600000
```

## Running the Examples

### Prerequisites
```bash
# Java 17+
java -version

# PostgreSQL running
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15

# Maven or Gradle
mvn -version
```

### Build and Run
```bash
# Using Maven
mvn clean install
mvn spring-boot:run

# Using Gradle
./gradlew clean build
./gradlew bootRun
```

### Test the API
```bash
# Create user
curl -X POST http://localhost:8080/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password": "password123"
  }'

# Get all users
curl http://localhost:8080/api/v1/users

# Get user by ID
curl http://localhost:8080/api/v1/users/1

# Update user
curl -X PUT http://localhost:8080/api/v1/users/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith"
  }'

# Delete user
curl -X DELETE http://localhost:8080/api/v1/users/1
```

## Key Takeaways

1. **Layer Separation**: Clear separation between Controller, Service, and Repository
2. **Constructor Injection**: All dependencies injected via constructor
3. **DTOs**: Never expose entities in API
4. **Transaction Management**: @Transactional on service methods
5. **Exception Handling**: Global handler with proper HTTP status codes
6. **Validation**: Bean Validation on request DTOs
7. **Security**: Proper authentication and authorization
8. **Testing**: Unit tests with mocks, integration tests with real Spring context

## Common Patterns Summary

| Pattern | Example |
|---------|---------|
| Constructor Injection | `@RequiredArgsConstructor` + `private final` |
| Service Transaction | `@Transactional` on service methods |
| Read Optimization | `@Transactional(readOnly = true)` |
| DTO Mapping | Manual or MapStruct |
| Exception Handling | `@RestControllerAdvice` |
| Validation | `@Valid` + Bean Validation annotations |
| Pagination | `Pageable` parameter |
| Security | `SecurityFilterChain` bean |

## Additional Resources

- See `../templates/` for code templates
- See `../checklists/` for code review checklist
- See `../SKILL.md` for comprehensive patterns guide
