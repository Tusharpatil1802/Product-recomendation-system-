import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Product, User, ProductRating, PurchaseHistory,
    BrowsingEvent, RecommendationLog,
)
from .serializers import (
    ProductSerializer, ProductRatingSerializer,
    PurchaseHistorySerializer, BrowsingEventSerializer,
    RecommendationSerializer,
)
from .ml_engine import ContentBasedRecommender

logger = logging.getLogger(__name__)

# ── Lazy-loaded singleton model ────────────────────────────
_recommender: ContentBasedRecommender | None = None


def get_recommender() -> ContentBasedRecommender:
    global _recommender
    if _recommender is None or not _recommender._is_fitted:
        _recommender = ContentBasedRecommender.load()
    return _recommender


# ── Helper ─────────────────────────────────────────────────
def _get_or_create_user(external_id: str) -> User:
    user, _ = User.objects.get_or_create(external_id=external_id)
    return user


def _parse_positive_int(value: str | None, *, default: int, param_name: str, max_value: int = 100) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'"{param_name}" must be an integer.') from exc
    if parsed < 1:
        raise ValueError(f'"{param_name}" must be greater than 0.')
    if parsed > max_value:
        raise ValueError(f'"{param_name}" must be less than or equal to {max_value}.')
    return parsed


class StandardResultsSetPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


# ══════════════════════════════════════════════════════════
# Product endpoints
# ══════════════════════════════════════════════════════════

class ProductListCreateView(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        products = Product.objects.select_related("category").order_by("id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(products, request, view=self)
        serializer = ProductSerializer(products, many=True)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return Response(ProductSerializer(product).data)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        get_object_or_404(Product, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════
# User-signal ingestion endpoints
# ══════════════════════════════════════════════════════════

class RatingCreateView(APIView):
    """POST /api/users/<user_id>/ratings/"""

    def post(self, request, user_id):
        user = _get_or_create_user(user_id)
        serializer = ProductRatingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            rating, created = ProductRating.objects.update_or_create(
                user=user,
                product=serializer.validated_data["product"],
                defaults={
                    "score": serializer.validated_data["score"],
                    "review_text": serializer.validated_data.get("review_text", ""),
                },
            )
            _refresh_product_rating(rating.product)

        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(ProductRatingSerializer(rating).data, status=code)


class PurchaseCreateView(APIView):
    """POST /api/users/<user_id>/purchases/"""

    def post(self, request, user_id):
        user = _get_or_create_user(user_id)
        serializer = PurchaseHistorySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        purchase = serializer.save(user=user)
        return Response(PurchaseHistorySerializer(purchase).data, status=status.HTTP_201_CREATED)


class BrowsingEventCreateView(APIView):
    """POST /api/users/<user_id>/browse/"""

    def post(self, request, user_id):
        user = _get_or_create_user(user_id)
        serializer = BrowsingEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        event = serializer.save(user=user)
        return Response(BrowsingEventSerializer(event).data, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════
# Recommendation endpoints
# ══════════════════════════════════════════════════════════

class UserRecommendationsView(APIView):
    """
    GET /api/users/<user_id>/recommendations/?top_n=10&exclude_seen=true
    Returns personalised product recommendations for a user.
    """

    def get(self, request, user_id):
        user = _get_or_create_user(user_id)
        try:
            top_n = _parse_positive_int(
                request.query_params.get("top_n"),
                default=10,
                param_name="top_n",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        exclude_seen = request.query_params.get("exclude_seen", "true").strip().lower() != "false"

        recommender = get_recommender()
        if not recommender._is_fitted:
            return Response(
                {"detail": "Recommendation model not trained. Run: python manage.py train_recommender"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        purchases_qs = PurchaseHistory.objects.filter(user=user)
        browsing_qs = BrowsingEvent.objects.filter(user=user)
        ratings_qs = ProductRating.objects.filter(user=user)

        try:
            raw_recs = recommender.get_recommendations(
                user, purchases_qs, browsing_qs, ratings_qs,
                top_n=top_n, exclude_seen=exclude_seen,
            )
        except Exception as exc:
            logger.exception("Recommendation error for user %s", user_id)
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        product_ids = [recommendation["product_id"] for recommendation in raw_recs]
        products = {
            product.id: product
            for product in Product.objects.filter(id__in=product_ids).select_related("category")
        }
        enriched = [
            {**recommendation, "product": products[recommendation["product_id"]]}
            for recommendation in raw_recs if recommendation["product_id"] in products
        ]

        RecommendationLog.objects.create(
            user=user,
            recommended_products=product_ids,
            strategy="content_based",
            context={"top_n": top_n, "exclude_seen": exclude_seen},
        )

        serializer = RecommendationSerializer(enriched, many=True)
        return Response({"user_id": user_id, "recommendations": serializer.data})


class SimilarProductsView(APIView):
    """
    GET /api/products/<pk>/similar/?top_n=10
    Returns products most similar to the given product.
    """

    def get(self, request, pk):
        get_object_or_404(Product, pk=pk)
        try:
            top_n = _parse_positive_int(
                request.query_params.get("top_n"),
                default=10,
                param_name="top_n",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        recommender = get_recommender()
        if not recommender._is_fitted:
            return Response(
                {"detail": "Model not trained."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        raw_similar = recommender.get_similar_products(pk, top_n=top_n)
        product_ids = [recommendation["product_id"] for recommendation in raw_similar]
        products = {
            product.id: product
            for product in Product.objects.filter(id__in=product_ids).select_related("category")
        }
        enriched = [
            {**recommendation, "product": products[recommendation["product_id"]]}
            for recommendation in raw_similar if recommendation["product_id"] in products
        ]

        serializer = RecommendationSerializer(enriched, many=True)
        return Response({"product_id": pk, "similar": serializer.data})


# ══════════════════════════════════════════════════════════
# Model management endpoints
# ══════════════════════════════════════════════════════════

@api_view(['POST'])
def retrain_model(request):
    """
    POST /api/admin/retrain/
    Retrains the model in-process (for dev/small datasets).
    For production use the management command via Celery instead.
    """
    products_qs = Product.objects.all()
    ratings_qs = ProductRating.objects.all()

    if not products_qs.exists():
        return Response({"detail": "No products to train on."}, status=status.HTTP_400_BAD_REQUEST)

    corpus_df = ContentBasedRecommender.build_product_corpus(products_qs, ratings_qs)
    recommender = ContentBasedRecommender()
    recommender.fit(corpus_df)
    recommender.save()

    global _recommender
    _recommender = recommender

    return Response({
        "detail": "Model retrained successfully.",
        "products": len(corpus_df),
        "vocab_size": len(recommender.vectorizer.vocabulary_),
    })


@api_view(['GET'])
def model_status(request):
    """GET /api/admin/model-status/"""
    recommender = get_recommender()
    return Response({
        "is_fitted": recommender._is_fitted,
        "product_count": len(recommender.product_ids) if recommender._is_fitted else 0,
        "vocab_size": (
            len(recommender.vectorizer.vocabulary_) if recommender._is_fitted else 0
        ),
    })


# ── Internal helper ────────────────────────────────────────
def _refresh_product_rating(product: Product):
    from django.db.models import Avg, Count
    agg = ProductRating.objects.filter(product=product).aggregate(
        avg=Avg("score"),
        cnt=Count("id"),
    )
    Product.objects.filter(pk=product.pk).update(
        avg_rating=round(agg["avg"] or 0, 2),
        rating_count=agg["cnt"] or 0,
    )
