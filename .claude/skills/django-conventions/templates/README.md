# Django Conventions Templates

This directory contains templates for creating Django code following best practices.

## Available Templates

### 1. Django Model Template (`django_model_template.py`)

**Purpose:** Template for creating well-designed Django models.

**Includes:**
- TextChoices/IntegerChoices for choice fields
- Proper field definitions with verbose names
- ForeignKey and ManyToMany relationships
- Meta class configuration (indexes, constraints, permissions)
- Custom managers and QuerySets
- Model methods and properties
- Validation logic
- Timestamp fields

**Usage:**
1. Copy template to your app's `models.py`
2. Replace `[MODEL_NAME]` with your model name (PascalCase)
3. Replace `[field_name]` with actual field names (snake_case)
4. Add/remove fields as needed
5. Implement custom methods
6. Configure Meta class

### 2. Django REST Framework ViewSet Template (`drf_viewset_template.py`)

**Purpose:** Template for creating DRF ViewSets with CRUD operations.

**Includes:**
- Complete ViewSet configuration
- Permission handling
- Filtering, searching, and ordering
- Query optimization with select_related/prefetch_related
- Serializer selection based on action
- Custom actions with @action decorator
- Pagination
- Performance optimizations

**Usage:**
1. Copy template to your app's `views.py`
2. Replace `[MODEL_NAME]` with your model name
3. Replace `[Serializer]` with your serializer class names
4. Configure permissions
5. Implement custom actions
6. Set up filtering and pagination

### 3. Django Form Template (`django_form_template.py`)

**Purpose:** Template for creating Django forms with validation.

**Includes:**
- ModelForm configuration
- Field customization (widgets, labels, help text)
- Field-level validation (clean_<field>)
- Form-level validation (clean)
- Form initialization with custom parameters
- Save override for additional processing
- Regular Form (non-ModelForm) example
- File upload form example
- Search form example

**Usage:**
1. Copy template to your app's `forms.py`
2. Replace `[MODEL_NAME]` with your model name
3. Configure Meta class with fields
4. Add validation logic
5. Customize widgets and labels
6. Implement save override if needed

## Examples

### Creating a Model

```python
# From template
class [MODEL_NAME](models.Model):
    name = models.CharField(_('name'), max_length=200)
    # ...

# Your implementation
class Article(models.Model):
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), unique=True)
    # ...
```

### Creating a ViewSet

```python
# From template
class [MODEL_NAME]ViewSet(viewsets.ModelViewSet):
    queryset = [MODEL_NAME].objects.all()
    # ...

# Your implementation
class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    # ...
```

### Creating a Form

```python
# From template
class [MODEL_NAME]Form(forms.ModelForm):
    class Meta:
        model = [MODEL_NAME]
        # ...

# Your implementation
class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'category']
        # ...
```

## Best Practices Reminders

### Models
- Use verbose names with gettext_lazy for i18n
- Set related_name on all relationships
- Add indexes on frequently queried fields
- Include created_at and updated_at timestamps
- Use TextChoices for choice fields
- Implement __str__() method

### ViewSets
- Use select_related/prefetch_related in get_queryset()
- Return different serializers for list/detail/write
- Configure permissions appropriately
- Add pagination to list endpoints
- Use custom actions for non-CRUD operations

### Forms
- Validate in clean_<field>() for single field
- Validate in clean() for multi-field validation
- Use ModelForm for database-backed forms
- Customize widgets for better UX
- Add help text to guide users

## Additional Resources

- See `../SKILL.md` for comprehensive Django best practices
- See `../examples/` for complete working examples
- See `../checklists/` for code review checklists
