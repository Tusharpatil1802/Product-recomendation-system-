"""
Management command: train_recommender
Usage:
    python manage.py train_recommender
    python manage.py train_recommender --model-name my_model
"""
import time
import logging
from django.core.management.base import BaseCommand
from recommender.models import Product, ProductRating
from recommender.ml_engine import ContentBasedRecommender

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train and persist the content-based recommendation model.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-name',
            default='content_based',
            help='Filename stem for the saved model (default: content_based)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Building product corpus …'))
        t0 = time.perf_counter()

        products_qs = Product.objects.all()
        ratings_qs = ProductRating.objects.all()

        if not products_qs.exists():
            self.stdout.write(self.style.WARNING('No products found. Seed the database first.'))
            return

        corpus_df = ContentBasedRecommender.build_product_corpus(products_qs, ratings_qs)
        self.stdout.write(f'  Corpus built: {len(corpus_df)} products.')

        recommender = ContentBasedRecommender()
        recommender.fit(corpus_df)

        model_name = options['model_name']
        recommender.save(model_name)

        elapsed = time.perf_counter() - t0
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Model "{model_name}" trained and saved in {elapsed:.2f}s.'
            )
        )
