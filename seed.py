"""
Seed the database with demo products, users, and interactions.

Run:
    python seed.py
"""

import os
import sys

import django


BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from django.db.models import Avg, Count

from recommender.models import (
    BrowsingEvent,
    Category,
    Product,
    ProductRating,
    PurchaseHistory,
    User,
)


CATEGORY_DATA = [
    ("Electronics", "electronics"),
    ("Books", "books"),
    ("Clothing", "clothing"),
    ("Home & Kitchen", "home-kitchen"),
    ("Sports", "sports"),
]

PRODUCTS_DATA = [
    ("Sony WH-1000XM5 Headphones", "Premium wireless noise-cancelling headphones with 30hr battery.", "electronics", ["wireless", "noise-cancelling", "audio", "bluetooth"], 349.99),
    ("Apple AirPods Pro", "Active noise cancellation earbuds with spatial audio support.", "electronics", ["wireless", "earbuds", "audio", "bluetooth", "apple"], 249.00),
    ("Bose QuietComfort 45", "Comfortable over-ear headphones with legendary Bose noise cancellation.", "electronics", ["wireless", "noise-cancelling", "audio", "over-ear"], 329.00),
    ("Kindle Paperwhite", "Waterproof e-reader with adjustable warm light and 6-week battery.", "electronics", ["e-reader", "kindle", "reading", "waterproof"], 139.99),
    ("iPad Air", "Powerful tablet with M2 chip, great for creative work.", "electronics", ["tablet", "apple", "M2", "creative"], 749.00),
    ("Deep Work - Cal Newport", "Rules for focused success in a distracted world.", "books", ["productivity", "focus", "non-fiction", "career"], 18.00),
    ("Atomic Habits - James Clear", "An easy and proven way to build good habits and break bad ones.", "books", ["habits", "self-improvement", "non-fiction", "psychology"], 16.99),
    ("The Art of War - Sun Tzu", "Ancient Chinese military text on strategy and tactics.", "books", ["strategy", "classic", "philosophy", "non-fiction"], 9.99),
    ("Nike Dri-FIT T-Shirt", "Moisture-wicking performance tee for workouts.", "clothing", ["nike", "workout", "dri-fit", "running"], 35.00),
    ("Levi's 501 Jeans", "Classic straight-leg denim jeans.", "clothing", ["denim", "casual", "levis", "jeans"], 69.99),
    ("Instant Pot Duo 7-in-1", "Multi-use pressure cooker, slow cooker, rice cooker and more.", "home-kitchen", ["cooking", "pressure-cooker", "kitchen", "instant-pot"], 99.95),
    ("Ninja Air Fryer", "Compact air fryer with 4-qt basket for crispy results.", "home-kitchen", ["air-fryer", "ninja", "cooking", "kitchen"], 109.99),
    ("Yoga Mat - Liforme", "Eco-friendly alignment mat with superior grip.", "sports", ["yoga", "fitness", "mat", "eco"], 150.00),
    ("Resistance Bands Set", "Set of 5 latex resistance bands for home workouts.", "sports", ["resistance", "fitness", "home-workout", "bands"], 29.99),
    ("Garmin Forerunner 265", "GPS running watch with AMOLED display and advanced training metrics.", "sports", ["gps", "running", "watch", "garmin", "fitness"], 449.99),
]

USER_IDS = ["user_alice", "user_bob", "user_carol"]


def seed_categories() -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for name, slug in CATEGORY_DATA:
        category, _ = Category.objects.update_or_create(slug=slug, defaults={"name": name})
        categories[slug] = category
    return categories


def seed_products(categories: dict[str, Category]) -> list[Product]:
    products: list[Product] = []
    for name, description, category_slug, tags, price in PRODUCTS_DATA:
        product, _ = Product.objects.update_or_create(
            name=name,
            defaults={
                "description": description,
                "category": categories[category_slug],
                "tags": tags,
                "price": price,
            },
        )
        products.append(product)
    return products


def seed_users() -> list[User]:
    users: list[User] = []
    for user_id in USER_IDS:
        user, _ = User.objects.get_or_create(external_id=user_id)
        users.append(user)
    return users


def seed_ratings_and_purchases(products: list[Product], users: list[User]) -> None:
    alice, bob, carol = users

    for product, score, review in [
        (products[0], 5.0, "Best headphones I have ever owned. Amazing noise cancellation."),
        (products[1], 4.0, "Great sound, very comfortable for long use."),
        (products[12], 4.5, "Really grippy mat, helps a lot with my yoga practice."),
    ]:
        ProductRating.objects.update_or_create(
            user=alice,
            product=product,
            defaults={"score": score, "review_text": review},
        )

    for product, quantity in [(products[0], 1), (products[12], 1)]:
        PurchaseHistory.objects.update_or_create(
            user=alice,
            product=product,
            defaults={"quantity": quantity},
        )

    for product, score, review in [
        (products[5], 5.0, "Life-changing book. I restructured my entire workday after reading this."),
        (products[6], 5.0, "Practical and well researched. Highly recommended."),
        (products[10], 4.0, "Great pressure cooker. Saves so much time in the kitchen."),
    ]:
        ProductRating.objects.update_or_create(
            user=bob,
            product=product,
            defaults={"score": score, "review_text": review},
        )

    for product, quantity in [(products[5], 1), (products[6], 1), (products[10], 1)]:
        PurchaseHistory.objects.update_or_create(
            user=bob,
            product=product,
            defaults={"quantity": quantity},
        )

    for product, score, review in [
        (products[3], 5.0, "Perfect reading device. Waterproofing is a bonus."),
        (products[4], 4.5, "Superb tablet, M2 chip is blazing fast."),
        (products[14], 4.0, "Very accurate GPS. Excellent for marathon training."),
    ]:
        ProductRating.objects.update_or_create(
            user=carol,
            product=product,
            defaults={"score": score, "review_text": review},
        )

    for product, quantity in [(products[3], 1), (products[4], 1)]:
        PurchaseHistory.objects.update_or_create(
            user=carol,
            product=product,
            defaults={"quantity": quantity},
        )


def seed_browsing_events(products: list[Product], users: list[User]) -> None:
    alice, bob, carol = users
    browsing_events = [
        (alice, products[2], "view"),
        (alice, products[3], "click"),
        (alice, products[13], "add_to_cart"),
        (bob, products[7], "click"),
        (bob, products[11], "view"),
        (carol, products[0], "wishlist"),
        (carol, products[1], "add_to_cart"),
    ]

    for user, product, event_type in browsing_events:
        BrowsingEvent.objects.get_or_create(
            user=user,
            product=product,
            event_type=event_type,
            session_id="demo-seed",
        )


def refresh_product_ratings(products: list[Product]) -> None:
    for product in products:
        aggregate = ProductRating.objects.filter(product=product).aggregate(
            avg=Avg("score"),
            cnt=Count("id"),
        )
        Product.objects.filter(pk=product.pk).update(
            avg_rating=round(aggregate["avg"] or 0, 2),
            rating_count=aggregate["cnt"] or 0,
        )


def main() -> None:
    categories = seed_categories()
    products = seed_products(categories)
    users = seed_users()
    seed_ratings_and_purchases(products, users)
    seed_browsing_events(products, users)
    refresh_product_ratings(products)

    print(f"Seeded {len(products)} products across {len(categories)} categories.")
    print("Seed complete. Demo users: user_alice, user_bob, user_carol.")
    print("Next step: python manage.py train_recommender")


if __name__ == "__main__":
    main()
