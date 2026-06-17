from rest_framework import serializers
from .models import Product, Category, ProductRating, PurchaseHistory, BrowsingEvent


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'category', 'category_id',
            'tags', 'price', 'avg_rating', 'rating_count', 'created_at',
        ]
        read_only_fields = ['avg_rating', 'rating_count', 'created_at']

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list of strings.")
        cleaned_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("Each tag must be a string.")
            normalized = tag.strip()
            if normalized:
                cleaned_tags.append(normalized)
        return cleaned_tags


class ProductRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = ['id', 'product', 'score', 'review_text', 'created_at']
        read_only_fields = ['created_at']

    def validate_score(self, value):
        if not (1.0 <= value <= 5.0):
            raise serializers.ValidationError("Score must be between 1.0 and 5.0.")
        return value


class PurchaseHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseHistory
        fields = ['id', 'product', 'quantity', 'purchased_at']
        read_only_fields = ['purchased_at']

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class BrowsingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrowsingEvent
        fields = ['id', 'product', 'event_type', 'session_id', 'created_at']
        read_only_fields = ['created_at']

    def validate_session_id(self, value):
        return value.strip()


class RecommendationSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    score = serializers.FloatField()
    product = ProductSerializer()
