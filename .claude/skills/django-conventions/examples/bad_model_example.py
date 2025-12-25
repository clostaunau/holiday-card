"""
Example of Poorly-Designed Django Model (Anti-Patterns)

This example shows what NOT to do:
- No verbose names (bad for i18n)
- Tuple choices instead of TextChoices
- No related_name on ForeignKey
- camelCase instead of snake_case
- No indexes
- No validation
- Business logic in wrong places
"""

from django.db import models
from django.contrib.auth.models import User


# Bad: Using tuple choices instead of TextChoices
STATUS_CHOICES = (
    (1, 'Draft'),
    (2, 'Published'),
    (3, 'Archived'),
)


class Post(models.Model):
    """Bad example - avoid these patterns."""

    # Bad: No verbose names (i18n issues)
    # Bad: camelCase instead of snake_case
    postTitle = models.CharField(max_length=200)

    # Bad: No slug field for URLs
    # Bad: No help_text

    # Bad: TextField with no blank=True (will allow empty in forms but not in admin)
    content = models.TextField()

    # Bad: No related_name (creates post_set which is unclear)
    # Bad: No on_delete specified (required in modern Django)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    # Bad: Using integer choices instead of TextChoices
    # Bad: No db_index despite frequent querying
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)

    # Bad: No validation on view_count (could be negative)
    viewCount = models.IntegerField(default=0)

    # Bad: Using DateTimeField but no timezone awareness noted
    # Bad: No auto_now_add (manual timestamp management)
    createdAt = models.DateTimeField()

    # Bad: No updated_at field

    # Bad: No Meta class configuration
    # - No verbose_name
    # - No ordering
    # - No indexes
    # - No constraints

    # Bad: No __str__ method (will show "Post object (1)" in admin)

    # Bad: Business logic in signal handlers instead of methods
    # See signals.py (anti-pattern)

    # Bad: No clean() method for validation

    def save(self, *args, **kwargs):
        """Bad save override."""
        # Bad: Setting created_at on every save (should use auto_now_add)
        if not self.pk:
            from datetime import datetime
            self.createdAt = datetime.now()  # Bad: Not timezone-aware

        # Bad: No validation before save
        super().save(*args, **kwargs)


# Bad: Using raw SQL instead of ORM
def get_published_posts():
    """Bad: Using raw SQL when ORM would work."""
    from django.db import connection
    cursor = connection.cursor()
    # Bad: SQL injection risk if user input was used
    cursor.execute("SELECT * FROM blog_post WHERE status = 2")
    return cursor.fetchall()


# Bad: N+1 query problem
def display_posts_with_authors():
    """Bad: Causes N+1 queries."""
    posts = Post.objects.all()  # 1 query
    for post in posts:
        # Bad: This triggers a query for each post!
        print(f"{post.postTitle} by {post.author.username}")


# Bad: Not using transactions for atomic operations
def transfer_post_ownership(post_id, new_author_id):
    """Bad: No transaction, could fail partially."""
    post = Post.objects.get(id=post_id)
    post.author_id = new_author_id
    post.save()

    # Bad: If this fails, the post already changed ownership
    AuditLog.objects.create(
        action='transfer',
        post=post,
        new_author_id=new_author_id
    )


# Bad: Storing secrets in code
SECRET_API_KEY = 'hardcoded-secret-key-12345'


# Bad: Using filter().first() instead of get()
def get_post_by_slug(slug):
    """Bad: Less clear intent than get()."""
    return Post.objects.filter(postTitle=slug).first()


# Bad: No custom manager for reusable queries
# Instead, duplicating query logic everywhere


class Comment(models.Model):
    """Bad comment model."""

    # Bad: No related_name
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    # Bad: No related_name
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    # Bad: No field name context
    text = models.TextField()

    # Bad: No timestamps

    # Bad: No Meta class
    # Bad: No __str__ method
    pass
