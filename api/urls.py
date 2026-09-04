from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BrandViewSet,
    CategoryViewSet,
    ProductViewSet,
    ShopProductViewSet,
    ShopViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brands", BrandViewSet, basename="brand")
router.register("products", ProductViewSet, basename="product")
router.register("shops", ShopViewSet, basename="shop")
router.register("shop-products", ShopProductViewSet, basename="shop-product")

urlpatterns = [
    path("", include(router.urls)),
]