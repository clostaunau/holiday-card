# Spring Framework Patterns - Templates

This directory contains code templates for common Spring Framework patterns and components.

## Available Templates

### 1. RestController.java.template

**Purpose:** Template for RESTful controllers following Spring best practices.

**Features:**
- Constructor injection with Lombok
- Full CRUD operations
- Pagination and sorting
- Proper HTTP status codes
- Location header for created resources
- Input validation with @Valid

**Placeholders:**
- `[ENTITY_NAME]` - Entity class name (e.g., User, Product)
- `[entityName]` - camelCase entity name (e.g., user, product)
- `[entity-name-plural]` - kebab-case plural (e.g., users, products)

**Usage:**
```bash
# Copy template
cp RestController.java.template ../src/main/java/com/example/app/controller/UserController.java

# Replace placeholders
# [ENTITY_NAME] -> User
# [entityName] -> user
# [entity-name-plural] -> users
```

### 2. Service.java.template

**Purpose:** Template for service layer with transaction management and business logic.

**Features:**
- Constructor injection
- @Transactional annotations
- Read-only optimization
- Logging with SLF4J
- Entity-DTO mapping
- Business validation

**Placeholders:**
- `[ENTITY_NAME]` - Entity class name
- `[entityName]` - camelCase entity name
- `[entity-name-plural]` - kebab-case plural

**Usage:**
```bash
# Copy template
cp Service.java.template ../src/main/java/com/example/app/service/UserService.java

# Replace placeholders
```

### 3. Repository.java.template

**Purpose:** Template for Spring Data JPA repositories.

**Features:**
- Extends JpaRepository and JpaSpecificationExecutor
- Query methods following Spring Data naming conventions
- Custom JPQL queries
- Native SQL queries

**Placeholders:**
- `[ENTITY_NAME]` - Entity class name
- `[FIELD]` - Field name in PascalCase (e.g., Email)
- `[field]` - Field name in camelCase (e.g., email)
- `[table_name]` - Database table name

**Usage:**
```bash
# Copy template
cp Repository.java.template ../src/main/java/com/example/app/repository/UserRepository.java

# Replace placeholders
```

### 4. GlobalExceptionHandler.java.template

**Purpose:** Global exception handler with @RestControllerAdvice.

**Features:**
- Handles common exceptions
- Validation error handling
- Consistent error response format
- Logging

**Usage:**
```bash
# Copy template - no placeholders needed
cp GlobalExceptionHandler.java.template ../src/main/java/com/example/app/exception/GlobalExceptionHandler.java
```

## Example: Creating a Product Resource

### Step 1: Create Entity
```java
@Entity
@Table(name = "products")
@Data
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private String description;
    private BigDecimal price;
    private boolean active;
}
```

### Step 2: Create DTOs
```java
// ProductDTO.java
@Data
public class ProductDTO {
    private Long id;
    private String name;
    private String description;
    private BigDecimal price;
}

// CreateProductRequest.java
@Data
public class CreateProductRequest {
    @NotBlank(message = "Name is required")
    private String name;

    private String description;

    @NotNull(message = "Price is required")
    @DecimalMin(value = "0.0", message = "Price must be positive")
    private BigDecimal price;
}

// UpdateProductRequest.java
@Data
public class UpdateProductRequest {
    private String name;
    private String description;
    private BigDecimal price;
}
```

### Step 3: Create Repository from Template
```bash
cp Repository.java.template ProductRepository.java
```

Replace:
- `[ENTITY_NAME]` → `Product`
- `[FIELD]` → `Name`
- `[field]` → `name`
- `[table_name]` → `products`

### Step 4: Create Service from Template
```bash
cp Service.java.template ProductService.java
```

Replace:
- `[ENTITY_NAME]` → `Product`
- `[entityName]` → `product`
- `[entity-name-plural]` → `products`

### Step 5: Create Controller from Template
```bash
cp RestController.java.template ProductController.java
```

Replace:
- `[ENTITY_NAME]` → `Product`
- `[entityName]` → `product`
- `[entity-name-plural]` → `products`

## Quick Reference: Placeholder Mappings

| Template Placeholder | Example (User) | Example (Product) | Example (OrderItem) |
|---------------------|----------------|-------------------|---------------------|
| `[ENTITY_NAME]` | User | Product | OrderItem |
| `[entityName]` | user | product | orderItem |
| `[entity-name-plural]` | users | products | order-items |
| `[FIELD]` | Email | Name | Quantity |
| `[field]` | email | name | quantity |
| `[table_name]` | users | products | order_items |

## Additional Notes

- All templates use Lombok for boilerplate reduction
- Constructor injection is used throughout
- Templates follow Spring Boot 3.x conventions
- Jakarta EE annotations (not javax)
- SLF4J for logging
- Proper transaction boundaries
- DTOs for API contracts

## Integration with Spring Boot

After creating files from templates:

1. Ensure proper package structure
2. Run application and verify bean creation
3. Test endpoints with Postman or curl
4. Add integration tests
5. Configure security if needed
