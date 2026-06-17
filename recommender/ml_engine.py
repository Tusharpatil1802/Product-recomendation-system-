"""
Content-based recommendation engine built on TF-IDF and cosine similarity.
"""

import pickle
import logging
from pathlib import Path

import numpy as np
import pandas as pd
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

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml_models"


class ContentBasedRecommender:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self.product_matrix = None
        self.similarity_matrix = None
        self.product_ids = []
        self.product_index = {}
        self.scaler = MinMaxScaler()
        self.rating_scores = np.array([])
        self._is_fitted = False

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return " ".join(value.split())
        if isinstance(value, list):
            return " ".join(ContentBasedRecommender._normalize_text(item) for item in value)
        return str(value).strip()

    @staticmethod
    def build_product_corpus(products_qs, ratings_qs) -> pd.DataFrame:
        review_map: dict[int, list[str]] = {}
        for rating in ratings_qs.values("product_id", "review_text"):
            review_text = ContentBasedRecommender._normalize_text(rating["review_text"])
            if review_text:
                review_map.setdefault(rating["product_id"], []).append(review_text)

        rows = []
        for product in products_qs.select_related("category"):
            tags = product.tags if isinstance(product.tags, list) else []
            corpus_parts = [
                ContentBasedRecommender._normalize_text(product.name),
                ContentBasedRecommender._normalize_text(product.description),
                ContentBasedRecommender._normalize_text(tags),
                ContentBasedRecommender._normalize_text(product.category.name if product.category else ""),
                ContentBasedRecommender._normalize_text(review_map.get(product.id, [])),
            ]
            corpus_text = " ".join(part for part in corpus_parts if part).strip() or f"product-{product.id}"

            rows.append({
                "product_id": product.id,
                "corpus": corpus_text,
                "avg_rating": product.avg_rating,
                "rating_count": product.rating_count,
                "category_id": product.category_id,
                "tags": tags,
            })

        return pd.DataFrame(rows)

    def fit(self, corpus_df: pd.DataFrame):
        if corpus_df.empty:
            logger.warning("ContentBasedRecommender.fit() received an empty corpus.")
            return

        self.product_ids = corpus_df["product_id"].tolist()
        self.product_index = {pid: idx for idx, pid in enumerate(self.product_ids)}

        self.product_matrix = self.vectorizer.fit_transform(corpus_df["corpus"].fillna(""))
        self.similarity_matrix = cosine_similarity(self.product_matrix)

        ratings = corpus_df[["avg_rating"]].fillna(0).copy()
        self.rating_scores = self.scaler.fit_transform(ratings).flatten()

        self._is_fitted = True
        logger.info(
            "Model fitted on %d products, vocab size %d",
            len(self.product_ids),
            len(self.vectorizer.vocabulary_),
        )

    @staticmethod
    def _purchase_profile(purchases_qs) -> dict[int, float]:
        profile: dict[int, float] = {}
        for purchase in purchases_qs.values("product_id", "quantity"):
            pid = purchase["product_id"]
            profile[pid] = profile.get(pid, 0) + purchase["quantity"]
        return profile

    @staticmethod
    def _browsing_profile(browsing_qs) -> dict[int, float]:
        profile: dict[int, float] = {}
        for event in browsing_qs.values("product_id", "event_type"):
            pid = event["product_id"]
            weight = BROWSING_WEIGHTS.get(event["event_type"], 1)
            profile[pid] = profile.get(pid, 0) + weight
        return profile

    @staticmethod
    def _rating_profile(ratings_qs) -> dict[int, float]:
        profile: dict[int, float] = {}
        for rating in ratings_qs.values("product_id", "score"):
            profile[rating["product_id"]] = rating["score"] / 5.0
        return profile

    def get_recommendations(
        self,
        user,
        purchases_qs,
        browsing_qs,
        ratings_qs,
        top_n: int = 10,
        exclude_seen: bool = True,
    ) -> list[dict]:
        if not self._is_fitted:
            raise RuntimeError("Recommender is not fitted. Run fit() first.")

        purchase_profile = self._purchase_profile(purchases_qs)
        browse_profile = self._browsing_profile(browsing_qs)
        rating_profile = self._rating_profile(ratings_qs)

        seen_ids = set(purchase_profile) | set(browse_profile) | set(rating_profile)

        seed_ids = list(rating_profile) or list(purchase_profile) or list(browse_profile)
        seed_ids = [pid for pid in seed_ids if pid in self.product_index]

        if not seed_ids:
            logger.info("No seed products for user %s — returning top-rated.", user)
            return self._fallback_top_rated(top_n)

        n = len(self.product_ids)
        agg_similarity = np.zeros(n)

        for pid in seed_ids:
            idx = self.product_index[pid]
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

        quality = self.rating_scores
        final_scores = 0.6 * agg_similarity + 0.4 * quality

        results = []
        for idx, score in enumerate(final_scores):
            pid = self.product_ids[idx]
            if exclude_seen and pid in seen_ids:
                continue
            results.append({"product_id": pid, "score": float(score)})

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_n]

    def _fallback_top_rated(self, top_n: int) -> list[dict]:
        pairs = sorted(
            zip(self.product_ids, self.rating_scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [{"product_id": pid, "score": float(score)} for pid, score in pairs[:top_n]]

    def get_similar_products(self, product_id: int, top_n: int = 10) -> list[dict]:
        if not self._is_fitted:
            raise RuntimeError("Recommender is not fitted.")
        if product_id not in self.product_index:
            return []

        idx = self.product_index[product_id]
        scores = self.similarity_matrix[idx].copy()
        scores[idx] = 0

        top_indices = np.argsort(scores)[::-1][:top_n]
        return [
            {"product_id": self.product_ids[i], "score": float(scores[i])}
            for i in top_indices
        ]

    def save(self, name: str = "content_based"):
        MODEL_PATH.mkdir(exist_ok=True)
        path = MODEL_PATH / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("Model saved to %s", path)

    @classmethod
    def load(cls, name: str = "content_based") -> "ContentBasedRecommender":
        path = MODEL_PATH / f"{name}.pkl"
        if not path.exists():
            logger.warning("No saved model at %s — returning untrained instance.", path)
            return cls()

        try:
            with open(path, "rb") as f:
                obj = pickle.load(f)
        except Exception:
            logger.exception("Failed to load model at %s. Returning a fresh instance.", path)
            return cls()

        logger.info("Model loaded from %s", path)
        return obj
