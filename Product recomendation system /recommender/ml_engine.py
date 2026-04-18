"""
Content-Based Filtering Engine
================================
Signals used:
  • Product features  → TF-IDF on (name + description + tags + category)
  • User purchase history → boost products in frequently bought categories/tags
  • Product ratings/reviews → review text enriches TF-IDF corpus; avg_rating used
    as a quality multiplier
  • Browsing behavior → weighted engagement score per product (view < click <
    add_to_cart < wishlist)
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Browsing-event weights
# ──────────────────────────────────────────────────────────
BROWSING_WEIGHTS = {
    'view': 1,
    'click': 2,
    'add_to_cart': 4,
    'wishlist': 3,
}

MODEL_PATH = Path(__file__).resolve().parent.parent / 'ml_models'


class ContentBasedRecommender:
    """
    Trains and serves content-based product recommendations.

    Workflow
    --------
    1. build_product_corpus()  – create enriched text per product
    2. fit()                   – fit TF-IDF, compute similarity matrix
    3. get_recommendations()   – score & rank for a given user
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
        )
        self.product_matrix = None      # TF-IDF matrix (n_products × vocab)
        self.similarity_matrix = None   # cosine sim (n_products × n_products)
        self.product_ids = []           # ordered list matching matrix rows
        self.product_index = {}         # product_id → row index
        self.scaler = MinMaxScaler()
        self._is_fitted = False

    # ── Corpus construction ────────────────────────────────

    @staticmethod
    def build_product_corpus(products_qs, ratings_qs) -> pd.DataFrame:
        """
        Combine product metadata + user reviews into one enriched text per product.
        """
        # Aggregate review texts per product
        review_map: dict[int, list[str]] = {}
        for r in ratings_qs.values('product_id', 'review_text'):
            review_map.setdefault(r['product_id'], []).append(r['review_text'])

        rows = []
        for p in products_qs.select_related('category'):
            tags_text = ' '.join(p.tags) if isinstance(p.tags, list) else ''
            category_text = p.category.name if p.category else ''
            reviews_text = ' '.join(review_map.get(p.id, []))

            corpus_text = ' '.join(filter(None, [
                p.name,
                p.description,
                tags_text,
                category_text,
                reviews_text,
            ]))

            rows.append({
                'product_id': p.id,
                'corpus': corpus_text,
                'avg_rating': p.avg_rating,
                'rating_count': p.rating_count,
                'category_id': p.category_id,
                'tags': p.tags if isinstance(p.tags, list) else [],
            })

        return pd.DataFrame(rows)

    # ── Training ───────────────────────────────────────────

    def fit(self, corpus_df: pd.DataFrame):
        """Fit TF-IDF vectoriser and compute pairwise cosine similarity."""
        if corpus_df.empty:
            logger.warning("ContentBasedRecommender.fit() received an empty corpus.")
            return

        self.product_ids = corpus_df['product_id'].tolist()
        self.product_index = {pid: idx for idx, pid in enumerate(self.product_ids)}

        self.product_matrix = self.vectorizer.fit_transform(corpus_df['corpus'])
        self.similarity_matrix = cosine_similarity(self.product_matrix)

        # Normalise avg_rating for quality weighting
        ratings = corpus_df[['avg_rating']].copy()
        self.rating_scores = self.scaler.fit_transform(ratings).flatten()

        self._is_fitted = True
        logger.info(
            "Model fitted on %d products, vocab size %d",
            len(self.product_ids),
            len(self.vectorizer.vocabulary_),
        )

    # ── User-profile helpers ───────────────────────────────

    @staticmethod
    def _purchase_profile(purchases_qs, product_map: dict) -> dict[int, float]:
        """
        Returns {product_id: implicit_score} from purchase history.
        More purchases of a category/tag family → higher score for related products.
        """
        profile: dict[int, float] = {}
        for purchase in purchases_qs.values('product_id', 'quantity'):
            pid = purchase['product_id']
            profile[pid] = profile.get(pid, 0) + purchase['quantity']
        return profile

    @staticmethod
    def _browsing_profile(browsing_qs) -> dict[int, float]:
        """Returns {product_id: engagement_score} from browsing events."""
        profile: dict[int, float] = {}
        for event in browsing_qs.values('product_id', 'event_type'):
            pid = event['product_id']
            weight = BROWSING_WEIGHTS.get(event['event_type'], 1)
            profile[pid] = profile.get(pid, 0) + weight
        return profile

    @staticmethod
    def _rating_profile(ratings_qs) -> dict[int, float]:
        """Returns {product_id: normalised_user_rating}."""
        profile: dict[int, float] = {}
        for r in ratings_qs.values('product_id', 'score'):
            profile[r['product_id']] = r['score'] / 5.0   # normalise to [0,1]
        return profile

    # ── Recommendation ─────────────────────────────────────

    def get_recommendations(
        self,
        user,
        purchases_qs,
        browsing_qs,
        ratings_qs,
        top_n: int = 10,
        exclude_seen: bool = True,
    ) -> list[dict]:
        """
        Score every product for a user and return top-N recommendations.

        Scoring formula (all weights normalised to [0, 1]):
            score(p) = w_sim * similarity_score(p)
                     + w_rating * quality_score(p)
                     + w_browse * browse_score(p)
                     + w_purchase * purchase_score(p)
        """
        if not self._is_fitted:
            raise RuntimeError("Recommender is not fitted. Run fit() first.")

        purchase_profile = self._purchase_profile(purchases_qs, {})
        browse_profile = self._browsing_profile(browsing_qs)
        rating_profile = self._rating_profile(ratings_qs)

        # Products the user has already interacted with
        seen_ids = set(purchase_profile) | set(browse_profile) | set(rating_profile)

        # Seed products: prefer explicit ratings, then purchases, then browses
        seed_ids = list(rating_profile) or list(purchase_profile) or list(browse_profile)
        seed_ids = [pid for pid in seed_ids if pid in self.product_index]

        if not seed_ids:
            logger.info("No seed products for user %s — returning top-rated.", user)
            return self._fallback_top_rated(top_n)

        # Aggregate similarity from all seed products (weighted by user signal)
        n = len(self.product_ids)
        agg_similarity = np.zeros(n)

        for pid in seed_ids:
            idx = self.product_index[pid]
            # Weight by strength of user signal
            signal = (
                rating_profile.get(pid, 0) * 3
                + purchase_profile.get(pid, 0) * 2
                + browse_profile.get(pid, 0)
            )
            agg_similarity += self.similarity_matrix[idx] * signal

        # Normalise aggregated similarity
        max_sim = agg_similarity.max()
        if max_sim > 0:
            agg_similarity /= max_sim

        # Quality multiplier from global average rating
        quality = self.rating_scores  # already [0,1]

        # Final score
        final_scores = 0.6 * agg_similarity + 0.4 * quality

        # Build results
        results = []
        for idx, score in enumerate(final_scores):
            pid = self.product_ids[idx]
            if exclude_seen and pid in seen_ids:
                continue
            results.append({'product_id': pid, 'score': float(score)})

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]

    def _fallback_top_rated(self, top_n: int) -> list[dict]:
        """Return top-N globally highest-rated products."""
        pairs = sorted(
            zip(self.product_ids, self.rating_scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [{'product_id': pid, 'score': float(s)} for pid, s in pairs[:top_n]]

    def get_similar_products(self, product_id: int, top_n: int = 10) -> list[dict]:
        """Return products most similar to a given product (item-to-item)."""
        if not self._is_fitted:
            raise RuntimeError("Recommender is not fitted.")
        if product_id not in self.product_index:
            return []

        idx = self.product_index[product_id]
        scores = self.similarity_matrix[idx].copy()
        scores[idx] = 0  # exclude itself

        top_indices = np.argsort(scores)[::-1][:top_n]
        return [
            {'product_id': self.product_ids[i], 'score': float(scores[i])}
            for i in top_indices
        ]

    # ── Persistence ────────────────────────────────────────

    def save(self, name: str = 'content_based'):
        path = MODEL_PATH / f'{name}.pkl'
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        logger.info("Model saved to %s", path)

    @classmethod
    def load(cls, name: str = 'content_based') -> 'ContentBasedRecommender':
        path = MODEL_PATH / f'{name}.pkl'
        if not path.exists():
            logger.warning("No saved model at %s — returning untrained instance.", path)
            return cls()
        with open(path, 'rb') as f:
            obj = pickle.load(f)
        logger.info("Model loaded from %s", path)
        return obj
