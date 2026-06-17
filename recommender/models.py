from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    tags = models.JSONField(default=list)          # e.g. ["wireless", "noise-cancelling"]
    price = models.DecimalField(max_digits=10, decimal_places=2)
    avg_rating = models.FloatField(default=0.0)
    rating_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(models.Model):
    external_id = models.CharField(max_length=100, unique=True)  # maps to your auth system
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.external_id


class ProductRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    score = models.FloatField()                    # 1.0 – 5.0
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user} → {self.product} ({self.score})"


class PurchaseHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    quantity = models.PositiveIntegerField(default=1)
    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} bought {self.product} x{self.quantity}"


class BrowsingEvent(models.Model):
    class EventType(models.TextChoices):
        VIEW = 'view', 'View'
        CLICK = 'click', 'Click'
        ADD_TO_CART = 'add_to_cart', 'Add to Cart'
        WISHLIST = 'wishlist', 'Wishlist'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='browsing_events')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='browsing_events')
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.VIEW)
    session_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.event_type} {self.product}"


class RecommendationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendation_logs')
    recommended_products = models.JSONField()      # list of product IDs
    strategy = models.CharField(max_length=50)     # e.g. "content_based", "hybrid"
    context = models.JSONField(default=dict)       # extra metadata
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recs for {self.user} via {self.strategy} @ {self.created_at:%Y-%m-%d %H:%M}"
