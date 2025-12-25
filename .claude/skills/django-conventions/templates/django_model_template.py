"""
Django Model Template

This template provides a starting point for creating Django models
following best practices and conventions.

Usage:
1. Copy this template to your app's models.py
2. Replace [MODEL_NAME] with your model name (PascalCase)
3. Replace [field_name] with actual field names (snake_case)
4. Add appropriate field types and options
5. Implement custom methods and properties
6. Add indexes and constraints in Meta class
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class [MODEL_NAME](models.Model):
    """
    Model representing [description].

    This model [what it does / its purpose].
    """

    # ==========================================
    # Choice Classes (use TextChoices/IntegerChoices)
    # ==========================================
    class [CHOICE_NAME](models.TextChoices):
        """[Description of choices]."""
        OPTION_ONE = 'VALUE1', _('Option One Display')
        OPTION_TWO = 'VALUE2', _('Option Two Display')
        OPTION_THREE = 'VALUE3', _('Option Three Display')

    # ==========================================
    # Fields
    # ==========================================

    # Character fields
    name = models.CharField(
        _('name'),
        max_length=200,
        help_text=_('Enter the name'),
    )

    # Slug field (usually unique)
    slug = models.SlugField(
        _('slug'),
        max_length=200,
        unique=True,
        help_text=_('URL-friendly version of name'),
    )

    # Text field
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Optional description'),
    )

    # Integer field with validators
    quantity = models.PositiveIntegerField(
        _('quantity'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(9999)],
    )

    # Decimal field (for money, percentages)
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    # Boolean field (name like a question)
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Is this item active?'),
    )

    # Choice field
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=[CHOICE_NAME].choices,
        default=[CHOICE_NAME].OPTION_ONE,
        db_index=True,  # Index if frequently queried
    )

    # ForeignKey (many-to-one relationship)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,  # or SET_NULL, PROTECT, etc.
        related_name='[model_name]s',  # Plural
        related_query_name='[model_name]',  # Singular
        verbose_name=_('author'),
    )

    # ForeignKey with null (optional relationship)
    category = models.ForeignKey(
        'Category',  # String reference if in same app
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='[model_name]s',
        related_query_name='[model_name]',
        verbose_name=_('category'),
    )

    # ManyToMany field
    tags = models.ManyToManyField(
        'Tag',
        related_name='[model_name]s',
        related_query_name='[model_name]',
        blank=True,
        verbose_name=_('tags'),
    )

    # Image/File field
    image = models.ImageField(
        _('image'),
        upload_to='[model_name]s/%Y/%m/%d/',
        null=True,
        blank=True,
    )

    # Date/DateTime fields
    published_at = models.DateTimeField(
        _('published at'),
        null=True,
        blank=True,
    )

    # Timestamp fields (almost always include these)
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )

    # ==========================================
    # Manager
    # ==========================================
    # Use custom manager if you have reusable query logic
    # objects = [MODEL_NAME]Manager()

    # ==========================================
    # Meta Class
    # ==========================================
    class Meta:
        verbose_name = _('[model name]')
        verbose_name_plural = _('[model names]')
        ordering = ['-created_at']  # Default ordering

        # Database table name (optional - Django auto-generates)
        # db_table = '[app_name]_[model_name]'

        # Indexes for performance
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

        # Constraints
        constraints = [
            # Unique together
            models.UniqueConstraint(
                fields=['author', 'slug'],
                name='unique_author_slug',
            ),
            # Check constraint
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='[model_name]_quantity_non_negative',
            ),
        ]

        # Custom permissions
        permissions = [
            ('can_publish', 'Can publish [model name]'),
            ('can_feature', 'Can feature [model name]'),
        ]

        # Get latest by
        get_latest_by = 'created_at'

    # ==========================================
    # String Representation
    # ==========================================
    def __str__(self):
        """String representation."""
        return self.name

    def __repr__(self):
        """Developer representation."""
        return f'<{self.__class__.__name__}(id={self.pk}, name="{self.name}")>'

    # ==========================================
    # Absolute URL
    # ==========================================
    def get_absolute_url(self):
        """Return absolute URL for this object."""
        from django.urls import reverse
        return reverse('[app_name]:[model_name]-detail', kwargs={'slug': self.slug})

    # ==========================================
    # Properties
    # ==========================================
    @property
    def is_published(self):
        """Check if object is published."""
        return (
            self.status == self.[CHOICE_NAME].PUBLISHED and
            self.published_at is not None
        )

    # Use cached_property for expensive computations
    from django.utils.functional import cached_property

    @cached_property
    def related_count(self):
        """Count related objects (cached on instance)."""
        return self.related_objects.count()

    # ==========================================
    # Custom Methods
    # ==========================================
    def publish(self):
        """Publish this object."""
        from django.utils import timezone

        self.status = self.[CHOICE_NAME].PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at', 'updated_at'])

    def archive(self):
        """Archive this object."""
        self.status = self.[CHOICE_NAME].ARCHIVED
        self.is_active = False
        self.save(update_fields=['status', 'is_active', 'updated_at'])

    def increment_view_count(self):
        """Increment view count efficiently (avoid race conditions)."""
        self.__class__.objects.filter(pk=self.pk).update(
            view_count=models.F('view_count') + 1
        )
        self.refresh_from_db(fields=['view_count'])

    # ==========================================
    # Model Validation
    # ==========================================
    def clean(self):
        """Validate model fields."""
        from django.core.exceptions import ValidationError

        errors = {}

        # Example validation: Published items must have published_at
        if self.status == self.[CHOICE_NAME].PUBLISHED and not self.published_at:
            errors['published_at'] = _('Published items must have a publish date.')

        # Example validation: Price must be positive
        if self.price and self.price < 0:
            errors['price'] = _('Price must be positive.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save to add custom logic."""
        # Run validation
        self.full_clean()

        # Auto-generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)

        # Custom logic before save
        # ...

        super().save(*args, **kwargs)

        # Custom logic after save (e.g., clear cache)
        # from django.core.cache import cache
        # cache.delete(f'[model_name]_{self.pk}')

    # ==========================================
    # Delete Override
    # ==========================================
    def delete(self, *args, **kwargs):
        """Override delete to add custom logic."""
        # Delete related files
        if self.image:
            self.image.delete(save=False)

        # Custom logic before delete
        # ...

        super().delete(*args, **kwargs)


# ==========================================
# Example: Abstract Base Model
# ==========================================
class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields."""

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        abstract = True


# ==========================================
# Example: Model Using Abstract Base
# ==========================================
class ConcreteModel(TimeStampedModel):
    """Concrete model inheriting from abstract base."""

    name = models.CharField(_('name'), max_length=200)

    class Meta:
        verbose_name = _('concrete model')
        verbose_name_plural = _('concrete models')

    def __str__(self):
        return self.name
