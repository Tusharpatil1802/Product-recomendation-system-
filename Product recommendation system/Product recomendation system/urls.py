from django.urls import path
from recommender import views

urlpatterns = [
    # ── Products ──────────────────────────────────────────
    path('api/products/', views.ProductListCreateView.as_view()),
    path('api/products/<int:pk>/', views.ProductDetailView.as_view()),
    path('api/products/<int:pk>/similar/', views.SimilarProductsView.as_view()),

    # ── User signals ──────────────────────────────────────
    path('api/users/<str:user_id>/ratings/', views.RatingCreateView.as_view()),
    path('api/users/<str:user_id>/purchases/', views.PurchaseCreateView.as_view()),
    path('api/users/<str:user_id>/browse/', views.BrowsingEventCreateView.as_view()),

    # ── Recommendations ───────────────────────────────────
    path('api/users/<str:user_id>/recommendations/', views.UserRecommendationsView.as_view()),

    # ── Model management ──────────────────────────────────
    path('api/admin/retrain/', views.retrain_model),
    path('api/admin/model-status/', views.model_status),
]
