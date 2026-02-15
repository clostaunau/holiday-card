"""
Django Form Template

This template provides a starting point for creating Django forms
following best practices and conventions.

Usage:
1. Copy this template to your app's forms.py
2. Replace [MODEL_NAME] with your model name
3. Replace [field_name] with actual field names
4. Implement validation logic
5. Add custom widgets and labels as needed
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from .models import [MODEL_NAME]

User = get_user_model()


# ==========================================
# ModelForm Template
# ==========================================
class [MODEL_NAME]Form(forms.ModelForm):
    """
    Form for creating and updating [MODEL_NAME] instances.

    This form provides validation and custom widgets for [MODEL_NAME].
    """

    # ==========================================
    # Additional Fields (not in model)
    # ==========================================

    # Example: Field not in model but needed for form
    agree_to_terms = forms.BooleanField(
        required=True,
        label=_('I agree to the terms and conditions'),
        help_text=_('You must agree to proceed.'),
    )

    # Example: Overriding model field
    # description = forms.CharField(
    #     widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
    #     required=False,
    # )

    # ==========================================
    # Meta Configuration
    # ==========================================
    class Meta:
        model = [MODEL_NAME]
        fields = [
            'title',
            'description',
            'category',
            'status',
            'is_active',
        ]
        # Or exclude fields:
        # exclude = ['created_at', 'updated_at', 'author']

        # Custom labels
        labels = {
            'title': _('Title'),
            'description': _('Description'),
            'category': _('Category'),
            'status': _('Status'),
            'is_active': _('Active'),
        }

        # Help text
        help_texts = {
            'title': _('Enter a descriptive title.'),
            'description': _('Provide detailed description.'),
        }

        # Error messages
        error_messages = {
            'title': {
                'required': _('Title is required.'),
                'max_length': _('Title is too long.'),
            },
        }

        # Custom widgets
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter title'),
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Enter description'),
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    # ==========================================
    # Form Initialization
    # ==========================================
    def __init__(self, *args, **kwargs):
        """
        Initialize form with custom behavior.

        Use this to:
        - Accept custom parameters
        - Modify field properties dynamically
        - Set initial values
        - Filter querysets for choice fields
        """
        # Extract custom parameters
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)

        # Call parent init
        super().__init__(*args, **kwargs)

        # Modify fields dynamically
        if not self.instance.pk:
            # On create, make certain fields optional
            self.fields['slug'].required = False

        # Filter category choices based on user
        if self.user and not self.user.is_staff:
            self.fields['category'].queryset = Category.objects.filter(
                is_public=True
            )

        # Add CSS classes to all fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'

        # Set field as read-only
        if self.instance.pk and self.instance.is_published:
            self.fields['status'].disabled = True

    # ==========================================
    # Field-Level Validation (clean_<fieldname>)
    # ==========================================
    def clean_title(self):
        """
        Validate title field.

        Field-level validation runs before form-level validation.
        Return the cleaned value.
        """
        title = self.cleaned_data.get('title')

        # Check length
        if len(title) < 5:
            raise ValidationError(
                _('Title must be at least 5 characters long.')
            )

        # Check for banned words
        banned_words = ['spam', 'banned']
        if any(word in title.lower() for word in banned_words):
            raise ValidationError(
                _('Title contains banned words.')
            )

        # Check uniqueness (excluding current instance)
        queryset = [MODEL_NAME].objects.filter(title__iexact=title)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError(
                _('An item with this title already exists.')
            )

        # Return cleaned value (can transform it)
        return title.strip()

    def clean_slug(self):
        """Validate and auto-generate slug."""
        slug = self.cleaned_data.get('slug')
        title = self.cleaned_data.get('title')

        # Auto-generate slug if not provided
        if not slug and title:
            from django.utils.text import slugify
            slug = slugify(title)

        # Validate format
        import re
        if not re.match(r'^[a-z0-9-]+$', slug):
            raise ValidationError(
                _('Slug can only contain lowercase letters, numbers, and hyphens.')
            )

        # Check uniqueness
        queryset = [MODEL_NAME].objects.filter(slug=slug)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError(
                _('An item with this slug already exists.')
            )

        return slug

    def clean_email(self):
        """Validate email field."""
        email = self.cleaned_data.get('email')

        # Check format (Django does this automatically, but you can add more)
        if email:
            email = email.lower().strip()

            # Check domain
            domain = email.split('@')[1]
            blocked_domains = ['tempmail.com', 'throwaway.email']
            if domain in blocked_domains:
                raise ValidationError(
                    _('Email from this domain is not allowed.')
                )

        return email

    # ==========================================
    # Form-Level Validation (clean)
    # ==========================================
    def clean(self):
        """
        Validate across multiple fields.

        Use this for validation that involves multiple fields.
        """
        cleaned_data = super().clean()

        # Get field values (might be None if field validation failed)
        title = cleaned_data.get('title')
        description = cleaned_data.get('description')
        status = cleaned_data.get('status')
        category = cleaned_data.get('category')

        # Cross-field validation example
        if status == 'PUBLISHED' and not category:
            # Add error to specific field
            self.add_error('category', _('Published items must have a category.'))
            # Or raise ValidationError with dict
            # raise ValidationError({
            #     'category': _('Published items must have a category.')
            # })

        # Another example
        if title and description and title.lower() == description.lower():
            raise ValidationError(
                _('Title and description cannot be the same.')
            )

        # Check user permissions
        if self.user and not self.user.is_staff:
            if status == 'PUBLISHED':
                raise ValidationError(
                    _('You do not have permission to publish items.')
                )

        return cleaned_data

    # ==========================================
    # Save Override
    # ==========================================
    def save(self, commit=True):
        """
        Save the form instance.

        Use this to:
        - Set fields that aren't in the form
        - Perform additional processing
        - Save related objects
        """
        instance = super().save(commit=False)

        # Set author if not already set
        if not instance.pk and self.user:
            instance.author = self.user

        # Auto-generate slug if not provided
        if not instance.slug:
            from django.utils.text import slugify
            instance.slug = slugify(instance.title)

        # Set published_at if status is published
        if instance.status == 'PUBLISHED' and not instance.published_at:
            from django.utils import timezone
            instance.published_at = timezone.now()

        if commit:
            instance.save()
            # Save many-to-many fields
            self.save_m2m()

            # Additional processing after save
            # Example: Send notification
            # from .tasks import send_notification
            # send_notification.delay(instance.id)

        return instance


# ==========================================
# Regular Form (not ModelForm)
# ==========================================
class Contact[MODEL_NAME]Form(forms.Form):
    """
    Contact form not backed by a model.

    Use regular Form when:
    - Not saving to database
    - Combining data from multiple models
    - Processing data without creating objects
    """

    # ==========================================
    # Field Definitions
    # ==========================================

    name = forms.CharField(
        label=_('Your Name'),
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your name'),
        }),
    )

    email = forms.EmailField(
        label=_('Email Address'),
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('your@email.com'),
        }),
    )

    subject = forms.CharField(
        label=_('Subject'),
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Message subject'),
        }),
    )

    message = forms.CharField(
        label=_('Message'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': _('Your message...'),
        }),
    )

    # ==========================================
    # Validation
    # ==========================================
    def clean_message(self):
        """Validate message field."""
        message = self.cleaned_data.get('message')

        if len(message) < 10:
            raise ValidationError(
                _('Message must be at least 10 characters long.')
            )

        return message

    # ==========================================
    # Custom Methods
    # ==========================================
    def send_email(self):
        """
        Send email with form data.

        Call this after form is validated.
        """
        from django.core.mail import send_mail

        send_mail(
            subject=f"Contact Form: {self.cleaned_data['subject']}",
            message=self.cleaned_data['message'],
            from_email=self.cleaned_data['email'],
            recipient_list=['contact@example.com'],
            fail_silently=False,
        )


# ==========================================
# Example: Form with File Upload
# ==========================================
class [MODEL_NAME]UploadForm(forms.ModelForm):
    """Form with file upload field."""

    class Meta:
        model = [MODEL_NAME]
        fields = ['title', 'image', 'document']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx',
            }),
        }

    def clean_image(self):
        """Validate image file."""
        image = self.cleaned_data.get('image')

        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError(
                    _('Image file size must be under 5MB.')
                )

            # Check file type
            import imghdr
            image_type = imghdr.what(image)
            if image_type not in ['jpeg', 'jpg', 'png', 'gif']:
                raise ValidationError(
                    _('Invalid image format. Use JPEG, PNG, or GIF.')
                )

        return image


# ==========================================
# Example: Inline Formset
# ==========================================
from django.forms import inlineformset_factory

# Create formset for related model
[MODEL_NAME]CommentFormSet = inlineformset_factory(
    [MODEL_NAME],
    Comment,
    fields=['content', 'is_approved'],
    extra=1,  # Number of empty forms
    can_delete=True,  # Allow deletion
    widgets={
        'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
    },
)


# ==========================================
# Example: Search Form
# ==========================================
class [MODEL_NAME]SearchForm(forms.Form):
    """Form for searching [MODEL_NAME] instances."""

    query = forms.CharField(
        label=_('Search'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search...'),
        }),
    )

    category = forms.ModelChoiceField(
        label=_('Category'),
        queryset=Category.objects.all(),
        required=False,
        empty_label=_('All Categories'),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', _('All'))] + [MODEL_NAME].STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    ordering = forms.ChoiceField(
        label=_('Sort By'),
        choices=[
            ('-created_at', _('Newest First')),
            ('created_at', _('Oldest First')),
            ('title', _('Title A-Z')),
            ('-title', _('Title Z-A')),
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
