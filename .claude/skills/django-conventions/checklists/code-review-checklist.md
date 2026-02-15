# Django Code Review Checklist

Use this checklist when reviewing Django code to ensure adherence to best practices.

## Project Structure

- [ ] Apps are focused on single domain concepts
- [ ] Settings split by environment (base, dev, prod, test)
- [ ] URL configuration uses `include()` for app-specific URLs
- [ ] Static and media files properly configured
- [ ] Requirements split by environment

## Models

### Field Definitions
- [ ] All fields have verbose names using `gettext_lazy`
- [ ] Field names use snake_case (not camelCase)
- [ ] Boolean fields named like questions (is_active, has_paid)
- [ ] Date/time fields use appropriate suffixes (_at, _date)
- [ ] Choice fields use TextChoices/IntegerChoices
- [ ] Decimal fields used for money (not Float)
- [ ] File/image fields use upload_to with date structure

### Relationships
- [ ] All ForeignKey have explicit `on_delete` handler
- [ ] All ForeignKey/ManyToMany have `related_name`
- [ ] related_name uses plural for one-to-many
- [ ] related_query_name set for clear queries
- [ ] Using string references for circular imports

### Meta Class
- [ ] verbose_name and verbose_name_plural defined
- [ ] Default ordering specified (if applicable)
- [ ] Indexes on frequently queried fields
- [ ] Indexes on fields used in ordering
- [ ] Constraints for data integrity
- [ ] Custom permissions defined (if needed)

### Model Methods
- [ ] `__str__()` method returns meaningful string
- [ ] `get_absolute_url()` defined (if applicable)
- [ ] Business logic in model methods (not signals)
- [ ] Properties use @property decorator
- [ ] Expensive computations use @cached_property
- [ ] clean() method for validation
- [ ] save() override only when necessary

### Timestamps
- [ ] created_at with auto_now_add=True
- [ ] updated_at with auto_now=True
- [ ] Other date fields have null=True if optional

### Managers and QuerySets
- [ ] Custom QuerySet for reusable query logic
- [ ] Manager methods return QuerySets (for chaining)
- [ ] Descriptive method names
- [ ] select_related/prefetch_related in manager methods

## Views

### Class-Based Views
- [ ] CBVs used for standard CRUD operations
- [ ] Appropriate generic view selected
- [ ] get_queryset() optimizes queries
- [ ] get_context_data() for additional context
- [ ] form_valid() for form processing
- [ ] Mixins used for reusable behavior

### Function-Based Views
- [ ] FBVs used for custom/unique logic
- [ ] Appropriate decorators applied
- [ ] Clear, focused purpose

### Permissions
- [ ] LoginRequiredMixin or @login_required used
- [ ] Custom permissions checked
- [ ] test_func() in UserPassesTestMixin
- [ ] Permission checks before operations

### Query Optimization
- [ ] select_related() for ForeignKey/OneToOne
- [ ] prefetch_related() for ManyToMany/reverse FK
- [ ] only() or defer() when appropriate
- [ ] No N+1 query problems
- [ ] Pagination on list views

## Django REST Framework

### Serializers
- [ ] ModelSerializer for model-based serializers
- [ ] Separate serializers for list/detail/write
- [ ] read_only=True on computed fields
- [ ] write_only=True on sensitive input fields
- [ ] Field validation in validate_<field>()
- [ ] Cross-field validation in validate()
- [ ] SerializerMethodField for computed data

### ViewSets
- [ ] ViewSets used for standard CRUD APIs
- [ ] get_queryset() optimizes queries
- [ ] get_serializer_class() returns appropriate serializer
- [ ] perform_create() sets related fields
- [ ] Custom actions use @action decorator
- [ ] Proper HTTP methods on custom actions

### Permissions
- [ ] Permission classes defined
- [ ] get_permissions() for action-specific permissions
- [ ] Custom permissions in separate file
- [ ] Object-level permissions checked

### Filtering and Pagination
- [ ] Filtering configured (django-filter)
- [ ] Search fields defined
- [ ] Ordering fields defined
- [ ] Pagination class set
- [ ] Reasonable page_size

### Authentication
- [ ] Token/JWT authentication configured
- [ ] Authentication classes in settings
- [ ] Login/logout endpoints provided

## Forms

### Form Definition
- [ ] ModelForm for model-backed forms
- [ ] Meta class with model, fields, labels
- [ ] Custom widgets for better UX
- [ ] Help text provided
- [ ] Error messages customized

### Validation
- [ ] clean_<field>() for field validation
- [ ] clean() for cross-field validation
- [ ] ValidationError with clear messages
- [ ] add_error() for specific field errors

### Form Handling
- [ ] __init__() for dynamic behavior
- [ ] save() override only when needed
- [ ] commit=False for additional processing
- [ ] save_m2m() called after save(commit=False)

## Security

### General
- [ ] DEBUG=False in production
- [ ] SECRET_KEY in environment variable
- [ ] ALLOWED_HOSTS configured
- [ ] No secrets in code

### CSRF Protection
- [ ] {% csrf_token %} in all POST forms
- [ ] CSRF token in AJAX requests
- [ ] Never @csrf_exempt in production

### SQL Injection Prevention
- [ ] Using Django ORM (not raw SQL)
- [ ] Parameterized queries if raw SQL needed
- [ ] No string concatenation in SQL

### XSS Prevention
- [ ] Django auto-escaping enabled
- [ ] |safe filter used cautiously
- [ ] format_html for building HTML
- [ ] escape() for user input in Python

### Authentication & Authorization
- [ ] Strong password validators configured
- [ ] Login required on protected views
- [ ] Object-level permissions checked
- [ ] User input validated

### HTTPS & Security Headers
- [ ] SECURE_SSL_REDIRECT=True in production
- [ ] SESSION_COOKIE_SECURE=True
- [ ] CSRF_COOKIE_SECURE=True
- [ ] SECURE_HSTS_SECONDS set
- [ ] X_FRAME_OPTIONS set

## Performance

### Database Queries
- [ ] select_related() for ForeignKey
- [ ] prefetch_related() for ManyToMany
- [ ] No N+1 query problems
- [ ] Indexes on queried fields
- [ ] Indexes on ordering fields
- [ ] only()/defer() when appropriate

### Caching
- [ ] Cache configured in settings
- [ ] Expensive queries cached
- [ ] Template fragments cached
- [ ] @cache_page on expensive views
- [ ] Cache invalidation strategy

### Database
- [ ] CONN_MAX_AGE for connection pooling
- [ ] Appropriate database backend
- [ ] Database connection settings optimized

### Other
- [ ] Static files collected and served efficiently
- [ ] Media files served efficiently
- [ ] Large files handled properly
- [ ] Background tasks for slow operations

## Testing

### Test Coverage
- [ ] Tests for all models
- [ ] Tests for all views/API endpoints
- [ ] Tests for forms
- [ ] Tests for custom permissions
- [ ] Tests for business logic
- [ ] Test coverage > 80%

### Test Quality
- [ ] Tests use TestCase/APITestCase
- [ ] setUp() for common test data
- [ ] Descriptive test names
- [ ] One assertion per test (guideline)
- [ ] Tests are independent
- [ ] Mock external dependencies

### Test Data
- [ ] Factories for test data (factory_boy)
- [ ] Fixtures for complex scenarios
- [ ] No hardcoded IDs
- [ ] Clean test database between tests

## Migrations

### Migration Quality
- [ ] Migrations reviewed before committing
- [ ] Descriptive migration names (--name)
- [ ] Data migrations with reverse operations
- [ ] No editing applied migrations
- [ ] Migration files committed to git

### Migration Safety
- [ ] New fields nullable or with defaults
- [ ] Large tables migrated carefully
- [ ] Indexes added in separate migrations
- [ ] Tested on production-like data

## Documentation

### Code Documentation
- [ ] Docstrings on all models
- [ ] Docstrings on all views/viewsets
- [ ] Docstrings on all forms
- [ ] Complex logic explained
- [ ] TODO/FIXME addressed

### Project Documentation
- [ ] README with setup instructions
- [ ] API documentation (if applicable)
- [ ] Deployment documentation
- [ ] Environment variables documented

## Common Anti-Patterns to Avoid

- [ ] No filter().first() instead of get()
- [ ] No missing select_related/prefetch_related
- [ ] No raw SQL when ORM works
- [ ] No business logic in signals
- [ ] No secrets in code
- [ ] No skipping migrations
- [ ] No circular imports
- [ ] No N+1 queries
- [ ] No mutable default arguments
- [ ] No using DEBUG=True in production
