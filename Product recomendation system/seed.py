"""
Seed the database with demo products, users and interactions.
Run:  python seed.py
"""
import os, sys, django

sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
django.setup()

from recommender.models import (
    Category, Product, User,
    ProductRating, PurchaseHistory, BrowsingEvent,
)

# ── Categories ────────────────────────────────────────────
cats = {}
for name, slug in [
    ('Electronics', 'electronics'), ('Books', 'books'),
    ('Clothing', 'clothing'), ('Home & Kitchen', 'home-kitchen'),
    ('Sports', 'sports'),
]:
    c, _ = Category.objects.get_or_create(slug=slug, defaults={'name': name})
    cats[slug] = c

# ── Products ──────────────────────────────────────────────
products_data = [
    ('Sony WH-1000XM5 Headphones', 'Premium wireless noise-cancelling headphones with 30hr battery.', 'electronics', ['wireless', 'noise-cancelling', 'audio', 'bluetooth'], 349.99),
    ('Apple AirPods Pro', 'Active noise cancellation earbuds with spatial audio support.', 'electronics', ['wireless', 'earbuds', 'audio', 'bluetooth', 'apple'], 249.00),
    ('Bose QuietComfort 45', 'Comfortable over-ear headphones with legendary Bose noise cancellation.', 'electronics', ['wireless', 'noise-cancelling', 'audio', 'over-ear'], 329.00),
    ('Kindle Paperwhite', 'Waterproof e-reader with adjustable warm light and 6-week battery.', 'electronics', ['e-reader', 'kindle', 'reading', 'waterproof'], 139.99),
    ('iPad Air', 'Powerful tablet with M2 chip, great for creative work.', 'electronics', ['tablet', 'apple', 'M2', 'creative'], 749.00),
    ('Deep Work – Cal Newport', 'Rules for focused success in a distracted world.', 'books', ['productivity', 'focus', 'non-fiction', 'career'], 18.00),
    ('Atomic Habits – James Clear', 'An easy and proven way to build good habits and break bad ones.', 'books', ['habits', 'self-improvement', 'non-fiction', 'psychology'], 16.99),
    ('The Art of War – Sun Tzu', 'Ancient Chinese military text on strategy and tactics.', 'books', ['strategy', 'classic', 'philosophy', 'non-fiction'], 9.99),
    ('Nike Dri-FIT T-Shirt', 'Moisture-wicking performance tee for workouts.', 'clothing', ['nike', 'workout', 'dri-fit', 'running'], 35.00),
    ('Levi\'s 501 Jeans', 'Classic straight-leg denim jeans.', 'clothing', ['denim', 'casual', 'levis', 'jeans'], 69.99),
    ('Instant Pot Duo 7-in-1', 'Multi-use pressure cooker, slow cooker, rice cooker and more.', 'home-kitchen', ['cooking', 'pressure-cooker', 'kitchen', 'instant-pot'], 99.95),
    ('Ninja Air Fryer', 'Compact air fryer with 4-qt basket for crispy results.', 'home-kitchen', ['air-fryer', 'ninja', 'cooking', 'kitchen'], 109.99),
    ('Yoga Mat – Liforme', 'Eco-friendly alignment mat with superior grip.', 'sports', ['yoga', 'fitness', 'mat', 'eco'], 150.00),
    ('Resistance Bands Set', 'Set of 5 latex resistance bands for home workouts.', 'sports', ['resistance', 'fitness', 'home-workout', 'bands'], 29.99),
    ('Garmin Forerunner 265', 'GPS running watch with AMOLED display and advanced training metrics.', 'sports', ['gps', 'running', 'watch', 'garmin', 'fitness'], 449.99),
]

products = []
for name, desc, cat_slug, tags, price in products_data:
    p, _ = Product.objects.get_or_create(
        name=name,
        defaults={'description': desc, 'category': cats[cat_slug], 'tags': tags, 'price': price},
    )
    products.append(p)

print(f"Created {len(products)} products.")

# ── Users ─────────────────────────────────────────────────
users = []
for uid in ['user_alice', 'user_bob', 'user_carol']:
    u, _ = User.objects.get_or_create(external_id=uid)
    users.append(u)

alice, bob, carol = users

# ── Interactions ──────────────────────────────────────────
# Alice likes audio + fitness
for p, score, review in [
    (products[0], 5.0, 'Best headphones I have ever owned. Amazing noise cancellation.'),
    (products[1], 4.0, 'Great sound, very comfortable for long use.'),
    (products[12], 4.5, 'Really grippy mat, helps a lot with my yoga practice.'),
]:
    ProductRating.objects.get_or_create(user=alice, product=p, defaults={'score': score, 'review_text': review})

for p, qty in [(products[0], 1), (products[12], 1)]:
    PurchaseHistory.objects.get_or_create(user=alice, product=p, defaults={'quantity': qty})

for p, evt in [(products[2], 'view'), (products[3], 'click'), (products[13], 'add_to_cart')]:
    BrowsingEvent.objects.create(user=alice, product=p, event_type=evt)

# Bob likes books + home
for p, score, review in [
    (products[5], 5.0, 'Life-changing book. I restructured my entire workday after reading this.'),
    (products[6], 5.0, 'Practical and well researched. Highly recommended.'),
    (products[10], 4.0, 'Great pressure cooker. Saves so much time in the kitchen.'),
]:
    ProductRating.objects.get_or_create(user=bob, product=p, defaults={'score': score, 'review_text': review})

for p, qty in [(products[5], 1), (products[6], 1), (products[10], 1)]:
    PurchaseHistory.objects.get_or_create(user=bob, product=p, defaults={'quantity': qty})

for p, evt in [(products[7], 'click'), (products[11], 'view')]:
    BrowsingEvent.objects.create(user=bob, product=p, event_type=evt)

# Carol likes electronics broadly
for p, score, review in [
    (products[3], 5.0, 'Perfect reading device. Waterproofing is a bonus.'),
    (products[4], 4.5, 'Superb tablet, M2 chip is blazing fast.'),
    (products[14], 4.0, 'Very accurate GPS. Excellent for marathon training.'),
]:
    ProductRating.objects.get_or_create(user=carol, product=p, defaults={'score': score, 'review_text': review})

for p, qty in [(products[3], 1), (products[4], 1)]:
    PurchaseHistory.objects.get_or_create(user=carol, product=p, defaults={'quantity': qty})

for p, evt in [(products[0], 'wishlist'), (products[1], 'add_to_cart')]:
    BrowsingEvent.objects.create(user=carol, product=p, event_type=evt)

# Refresh avg ratings on products
from django.db.models import Avg, Count
for prod in products:
    agg = ProductRating.objects.filter(product=prod).aggregate(avg=Avg('score'), cnt=Count('id'))
    Product.objects.filter(pk=prod.pk).update(
        avg_rating=round(agg['avg'] or 0, 2),
        rating_count=agg['cnt'] or 0,
    )

print("Seed complete. Users: alice, bob, carol.")
print("Run:  python manage.py train_recommender")
