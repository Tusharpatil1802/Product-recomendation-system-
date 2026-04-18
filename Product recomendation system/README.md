# Product Recommendation Backend — Django + Content-Based Filtering

## Stack
- **Django** (no admin, no auth — pure API backend)
- **Django REST Framework** for REST endpoints
- **scikit-learn** — TF-IDF vectoriser + cosine similarity matrix
- **SQLite** (swap to PostgreSQL in production via `DATABASES`)

---

## Quick Start

```bash
pip install django djangorestframework scikit-learn pandas numpy

# 1. Run migrations
python manage.py migrate --run-syncdb

# 2. Seed demo data (15 products, 3 users, interactions)
python seed.py

# 3. Train the ML model
python manage.py train_recommender

# 4. Start the dev server
python manage.py runserver
```

---

## ML Architecture

### Content-Based Filtering
Each product is represented as a **TF-IDF vector** built from:
- Product `name` + `description`
- `tags` (e.g. `["wireless", "noise-cancelling"]`)
- `category` name
- All user **review texts** for that product

Pairwise **cosine similarity** is precomputed at train time and persisted to `ml_models/content_based.pkl`.

### User Signal Weighting
| Signal | Weight |
|--------|--------|
| Explicit rating (1–5 ★) | 3× |
| Purchase history | 2× |
| Browsing (wishlist=3, cart=4, click=2, view=1) | 1× |

### Final Score Formula
```
score(p) = 0.6 × similarity_score(p) + 0.4 × quality_score(p)
```
`quality_score` = normalised global average rating.

---

## API Reference

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/products/` | List all products |
| `POST` | `/api/products/` | Create product |
| `GET` | `/api/products/<id>/` | Get product detail |
| `PUT` | `/api/products/<id>/` | Update product |
| `DELETE` | `/api/products/<id>/` | Delete product |
| `GET` | `/api/products/<id>/similar/?top_n=10` | Item-to-item similarity |

### User Signals
| Method | Endpoint | Body |
|--------|----------|------|
| `POST` | `/api/users/<uid>/ratings/` | `{product, score, review_text}` |
| `POST` | `/api/users/<uid>/purchases/` | `{product, quantity}` |
| `POST` | `/api/users/<uid>/browse/` | `{product, event_type, session_id}` |

`event_type` options: `view`, `click`, `add_to_cart`, `wishlist`

### Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/<uid>/recommendations/?top_n=10&exclude_seen=true` | Personalised recs |

### Model Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/model-status/` | Is model fitted? vocab size? |
| `POST` | `/api/admin/retrain/` | Retrain in-process (dev only) |

---

## Retraining Strategy

| Environment | Approach |
|-------------|----------|
| Development | `POST /api/admin/retrain/` or `python manage.py train_recommender` |
| Production | Schedule `train_recommender` via **Celery Beat** (e.g. nightly) |

---

## Project Structure
```
product_recommender/
├── settings.py                  # Django settings
├── urls.py                      # URL routing
├── manage.py
├── seed.py                      # Demo data seeder
├── ml_models/
│   └── content_based.pkl        # Trained model (auto-created)
└── recommender/
    ├── models.py                # DB schema
    ├── serializers.py           # DRF serializers
    ├── views.py                 # API views
    ├── ml_engine.py             # ContentBasedRecommender class
    └── management/commands/
        └── train_recommender.py # Training CLI command
```

---

## Production Checklist
- [ ] Replace `SECRET_KEY` in `settings.py`
- [ ] Switch `DATABASES` to PostgreSQL
- [ ] Add authentication (JWT / session) to views
- [ ] Move model retraining to a Celery task
- [ ] Store `ml_models/` on persistent volume (not ephemeral filesystem)
- [ ] Add caching (Redis) for recommendation results
