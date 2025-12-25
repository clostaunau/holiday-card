"""
Example of a Well-Designed Django Model

This example demonstrates Django best practices:
- Clear field definitions with verbose names
- TextChoices for status fields
- Proper indexes and constraints
- Custom manager and QuerySet
- Validation logic
- Timestamp fields
- Meaningful __str__ method
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class PublishedPostQuerySet(models.QuerySet):
    """Custom QuerySet for Post model."""

    def published(self):
        """Return only published posts."""
        return self.filter(
            status=Post.PostStatus.PUBLISHED,
            published_at__lte=timezone.now(),
        )

    def featured(self):
        """Return featured posts."""
        return self.filter(featured=True)

    def by_author(self, author):
        """Return posts by specific author."""
        return self.filter(author=author)

    def with_author_info(self):
        """Optimize query by selecting related author."""
        return self.select_related('author', 'category')


class PublishedPostManager(models.Manager):
    """Manager for Post model."""

    def get_queryset(self):
        """Return custom QuerySet."""
        return PublishedPostQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def featured(self):
        return self.get_queryset().featured()


class Category(models.Model):
    """Blog post category."""

    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['name']

    def __str__(self):
        return self.name


class Post(models.Model):
    """
    Blog post model.

    Represents a blog post with author, category, content, and metadata.
    """

    class PostStatus(models.TextChoices):
        """Post publication status."""
        DRAFT = 'DRAFT', _('Draft')
        PUBLISHED = 'PUBLISHED', _('Published')
        ARCHIVED = 'ARCHIVED', _('Archived')

    # Basic fields
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True)
    content = models.TextField(_('content'))

    # Relationships
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        related_query_name='post',
        verbose_name=_('author'),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        related_query_name='post',
        verbose_name=_('category'),
    )

    # Status and metadata
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=PostStatus.choices,
        default=PostStatus.DRAFT,
        db_index=True,
    )
    featured = models.BooleanField(_('featured'), default=False)
    view_count = models.PositiveIntegerField(
        _('view count'),
        default=0,
        validators=[MinValueValidator(0)],
    )

    # Timestamps
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    # Custom manager
    objects = PublishedPostManager()

    class Meta:
        verbose_name = _('post')
        verbose_name_plural = _('posts')
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['category', '-published_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(view_count__gte=0),
                name='post_view_count_non_negative',
            ),
        ]
        permissions = [
            ('can_publish', 'Can publish posts'),
        ]

    def __str__(self):
        """String representation."""
        return self.title

    def __repr__(self):
        """Developer representation."""
        return f'<Post(id={self.pk}, title="{self.title}", status={self.status})>'

    def get_absolute_url(self):
        """Return absolute URL for this post."""
        from django.urls import reverse
        return reverse('blog:post-detail', kwargs={'slug': self.slug})

    @property
    def is_published(self):
        """Check if post is published."""
        return (
            self.status == self.PostStatus.PUBLISHED and
            self.published_at is not None and
            self.published_at <= timezone.now()
        )

    def publish(self):
        """Publish this post."""
        if self.status == self.PostStatus.PUBLISHED:
            return

        self.status = self.PostStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()

        self.save(update_fields=['status', 'published_at', 'updated_at'])

    def archive(self):
        """Archive this post."""
        self.status = self.PostStatus.ARCHIVED
        self.save(update_fields=['status', 'updated_at'])

    def increment_view_count(self):
        """Increment view count efficiently."""
        self.__class__.objects.filter(pk=self.pk).update(
            view_count=models.F('view_count') + 1
        )
        self.refresh_from_db(fields=['view_count'])

    def clean(self):
        """Validate model fields."""
        from django.core.exceptions import ValidationError

        errors = {}

        # Published posts must have category
        if self.status == self.PostStatus.PUBLISHED and not self.category:
            errors['category'] = _('Published posts must have a category.')

        # Content must be at least 100 characters
        if self.content and len(self.content) < 100:
            errors['content'] = _('Content must be at least 100 characters.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save to set published_at when status changes."""
        # Auto-generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)

        # Set published_at when publishing
        if self.status == self.PostStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)


class Comment(models.Model):
    """Comment on a blog post."""

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        related_query_name='comment',
        verbose_name=_('post'),
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        related_query_name='comment',
        verbose_name=_('author'),
    )
    content = models.TextField(_('content'))
    is_approved = models.BooleanField(_('approved'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('comment')
        verbose_name_plural = _('comments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        return f'Comment by {self.author.username} on {self.post.title}'

    def approve(self):
        """Approve this comment."""
        self.is_approved = True
        self.save(update_fields=['is_approved', 'updated_at'])
