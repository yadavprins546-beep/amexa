from rest_framework import permissions, viewsets

from customer.models import Brand, Category, Product, Shop, ShopProduct

from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductSerializer,
    ShopProductSerializer,
    ShopSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
    )
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]


class ShopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.AllowAny]


class ShopProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShopProduct.objects.all()
    serializer_class = ShopProductSerializer
    permission_classes = [permissions.AllowAny]