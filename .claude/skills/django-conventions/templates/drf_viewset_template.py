"""
Django REST Framework ViewSet Template

This template provides a starting point for creating DRF ViewSets
following best practices and conventions.

Usage:
1. Copy this template to your app's views.py
2. Replace [MODEL_NAME] with your model name
3. Replace [Serializer] with your serializer class names
4. Implement custom actions as needed
5. Configure permissions, filtering, and pagination
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    AllowAny,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import [MODEL_NAME]
from .serializers import (
    [MODEL_NAME]ListSerializer,
    [MODEL_NAME]DetailSerializer,
    [MODEL_NAME]WriteSerializer,
)
from .permissions import IsAuthorOrReadOnly
from .filters import [MODEL_NAME]Filter
from .pagination import StandardResultsSetPagination


class [MODEL_NAME]ViewSet(viewsets.ModelViewSet):
    """
    ViewSet for [MODEL_NAME] with full CRUD operations.

    Provides:
    - list: GET /api/[model-names]/
    - retrieve: GET /api/[model-names]/{id}/
    - create: POST /api/[model-names]/
    - update: PUT /api/[model-names]/{id}/
    - partial_update: PATCH /api/[model-names]/{id}/
    - destroy: DELETE /api/[model-names]/{id}/

    Custom actions:
    - publish: POST /api/[model-names]/{id}/publish/
    - featured: GET /api/[model-names]/featured/
    """

    # ==========================================
    # Basic Configuration
    # ==========================================

    # Default queryset (will be filtered in get_queryset)
    queryset = [MODEL_NAME].objects.all()

    # Default serializer (will be selected in get_serializer_class)
    serializer_class = [MODEL_NAME]DetailSerializer

    # Lookup field (default is 'pk', can use 'slug', etc.)
    lookup_field = 'pk'
    lookup_url_kwarg = 'pk'

    # ==========================================
    # Permissions
    # ==========================================

    # Default permissions for all actions
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_permissions(self):
        """
        Return appropriate permissions based on action.

        Override to provide different permissions for different actions.
        """
        if self.action in ['create']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
        elif self.action in ['publish']:
            permission_classes = [IsAuthenticated]  # Add custom permission
        else:
            permission_classes = [AllowAny]

        return [permission() for permission in permission_classes]

    # ==========================================
    # Filtering, Searching, Ordering
    # ==========================================

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Using django-filter
    filterset_class = [MODEL_NAME]Filter
    # Or simple filterset_fields
    # filterset_fields = ['status', 'category', 'is_active']

    # Search fields (icontains lookup)
    search_fields = ['title', 'description', 'author__username']

    # Ordering fields
    ordering_fields = ['created_at', 'updated_at', 'title', 'view_count']
    ordering = ['-created_at']  # Default ordering

    # ==========================================
    # Pagination
    # ==========================================

    pagination_class = StandardResultsSetPagination

    # ==========================================
    # QuerySet Optimization
    # ==========================================

    def get_queryset(self):
        """
        Return optimized queryset based on action.

        This is where you:
        - Apply select_related/prefetch_related
        - Filter based on user permissions
        - Annotate with computed fields
        """
        queryset = super().get_queryset()

        # Optimize based on action
        if self.action == 'list':
            # Optimize list queries
            queryset = queryset.select_related('author', 'category')
            queryset = queryset.annotate(
                comment_count=models.Count('comments', distinct=True),
            )

            # Filter by permissions
            if not self.request.user.is_staff:
                # Non-staff users only see published items
                queryset = queryset.filter(status='PUBLISHED')

        elif self.action == 'retrieve':
            # Optimize detail queries
            queryset = queryset.select_related('author', 'category')
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    'comments',
                    queryset=Comment.objects.select_related('author'),
                )
            )

        # Filter by query parameters
        user_id = self.request.query_params.get('user', None)
        if user_id is not None:
            queryset = queryset.filter(author_id=user_id)

        return queryset

    # ==========================================
    # Serializer Selection
    # ==========================================

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.

        Use different serializers for:
        - list (minimal fields)
        - retrieve (full fields with nested data)
        - create/update (write-only fields)
        """
        if self.action == 'list':
            return [MODEL_NAME]ListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return [MODEL_NAME]WriteSerializer
        return [MODEL_NAME]DetailSerializer

    def get_serializer_context(self):
        """
        Add extra context to serializer.

        Useful for passing request, view, or custom data to serializers.
        """
        context = super().get_serializer_context()
        context['user'] = self.request.user
        # Add custom context as needed
        return context

    # ==========================================
    # CRUD Method Overrides
    # ==========================================

    def perform_create(self, serializer):
        """
        Called when creating an object.

        Use this to set fields based on request (like author).
        """
        # Set author to current user
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        """
        Called when updating an object.

        Use this for additional logic during update.
        """
        serializer.save()

        # Example: Clear cache after update
        # from django.core.cache import cache
        # cache.delete(f'[model_name]_{serializer.instance.pk}')

    def perform_destroy(self, instance):
        """
        Called when deleting an object.

        Use this for cleanup or soft delete.
        """
        # Soft delete example:
        # instance.is_active = False
        # instance.save()

        # Hard delete (default):
        instance.delete()

    # ==========================================
    # Custom Actions
    # ==========================================

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        """
        Custom action to publish an object.

        POST /api/[model-names]/{id}/publish/
        """
        obj = self.get_object()

        # Validate current state
        if obj.status == 'PUBLISHED':
            return Response(
                {'detail': 'Already published.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform action
        obj.publish()

        # Return serialized object
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def featured(self, request):
        """
        List featured objects.

        GET /api/[model-names]/featured/
        """
        queryset = self.get_queryset().filter(is_featured=True)[:10]

        # Use pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """
        Get comments for this object.

        GET /api/[model-names]/{id}/comments/
        """
        obj = self.get_object()
        comments = obj.comments.select_related('author').all()

        page = self.paginate_queryset(comments)
        if page is not None:
            serializer = CommentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get statistics about objects.

        GET /api/[model-names]/statistics/
        """
        from django.db.models import Count, Avg, Sum

        stats = self.get_queryset().aggregate(
            total_count=Count('id'),
            avg_view_count=Avg('view_count'),
            total_views=Sum('view_count'),
        )

        return Response(stats)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        """
        Like/unlike an object.

        POST /api/[model-names]/{id}/like/
        """
        obj = self.get_object()
        user = request.user

        # Toggle like
        if user in obj.liked_by.all():
            obj.liked_by.remove(user)
            liked = False
        else:
            obj.liked_by.add(user)
            liked = True

        return Response({
            'liked': liked,
            'like_count': obj.liked_by.count(),
        })

    # ==========================================
    # List/Retrieve Override Examples
    # ==========================================

    def list(self, request, *args, **kwargs):
        """
        Override list to add custom response data.
        """
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            # Add custom data to response
            response.data['meta'] = {
                'total_featured': self.get_queryset().filter(is_featured=True).count(),
            }

            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to add custom logic (e.g., increment view count).
        """
        instance = self.get_object()

        # Increment view count
        instance.increment_view_count()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ==========================================
# Example: ReadOnly ViewSet
# ==========================================
class ReadOnly[MODEL_NAME]ViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for read-only access to [MODEL_NAME].

    Provides only:
    - list: GET /api/[model-names]/
    - retrieve: GET /api/[model-names]/{id}/
    """

    queryset = [MODEL_NAME].objects.all()
    serializer_class = [MODEL_NAME]Serializer
    permission_classes = [AllowAny]


# ==========================================
# Example: Custom ViewSet (not ModelViewSet)
# ==========================================
from rest_framework import viewsets, mixins


class Custom[MODEL_NAME]ViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    Custom ViewSet with only create, retrieve, and list.

    No update or delete.
    """

    queryset = [MODEL_NAME].objects.all()
    serializer_class = [MODEL_NAME]Serializer
