# Product Recommendation System

A clean Django REST API for product recommendations using a content-based filtering model built with scikit-learn.

## Features

- Product catalog APIs for create, read, update, delete, and similar-product lookup
- User interaction APIs for ratings, purchases, and browsing events
- Personalized recommendations based on product text, reviews, ratings, and engagement
- In-app retraining endpoint for development
- CLI training workflow for repeatable model generation
- Demo data seeding for quick local testing

## Tech Stack

- Django
- Django REST Framework
- SQLite
- pandas
- numpy
- scikit-learn

## Project Structure

```text
.
├── manage.py
├── settings.py
├── urls.py
├── seed.py
├── train_recommender.py
├── requirements.txt
├── recommender/
│   ├── management/commands/train_recommender.py
│   ├── migrations/
│   ├── ml_engine.py
│   ├── models.py
│   ├── serializers.py
│   └── views.py
└── ml_models/
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Apply migrations.
4. Seed demo data.
5. Train the recommendation model.
6. Start the development server.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 manage.py migrate
python3 seed.py
python3 manage.py train_recommender
python3 manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`.

## How Recommendations Work

Each product is converted into a text corpus made from:

- product name
- description
- category
- tags
- review text left by users

The training step creates TF-IDF vectors and a cosine similarity matrix. At request time, the recommender combines:

- explicit ratings
- purchase history
- browsing behavior
- product quality score from average rating

This keeps the implementation simple while still giving personalized results.

## API Endpoints

### Products

- `GET /api/products/`
- `POST /api/products/`
- `GET /api/products/<id>/`
- `PUT /api/products/<id>/`
- `DELETE /api/products/<id>/`
- `GET /api/products/<id>/similar/?top_n=10`

### User Signals

- `POST /api/users/<user_id>/ratings/`
- `POST /api/users/<user_id>/purchases/`
- `POST /api/users/<user_id>/browse/`

`event_type` supports:

- `view`
- `click`
- `add_to_cart`
- `wishlist`

### Recommendations

- `GET /api/users/<user_id>/recommendations/?top_n=10&exclude_seen=true`

### Model Operations

- `GET /api/admin/model-status/`
- `POST /api/admin/retrain/`

## Example Requests

Create a product:

```bash
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mechanical Keyboard",
    "description": "Compact keyboard with tactile switches",
    "category_id": 1,
    "tags": ["keyboard", "mechanical", "productivity"],
    "price": "89.99"
  }'
```

Add a rating:

```bash
curl -X POST http://127.0.0.1:8000/api/users/user_alice/ratings/ \
  -H "Content-Type: application/json" \
  -d '{
    "product": 1,
    "score": 4.5,
    "review_text": "Very comfortable and great sound quality."
  }'
```

Get recommendations:

```bash
curl "http://127.0.0.1:8000/api/users/user_alice/recommendations/?top_n=5"
```

Retrain the model:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/retrain/
```

## Notes

- The saved model is written to `ml_models/content_based.pkl`.
- `seed.py` is idempotent for products, users, ratings, and purchases, so you can run it repeatedly while developing.
- Browsing seed events also use a stable session id to avoid unnecessary duplication.

## Suggested Next Improvements

- Add authentication and permissions for admin and user endpoints
- Add automated tests for the API and recommender flow
- Move retraining into a background task queue for production
- Switch to PostgreSQL for larger datasets
