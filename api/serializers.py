from rest_framework import serializers

from customer.models import (
    Brand,
    Category,
    Product,
    Shop,
    ShopProduct,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )
    shop_name = serializers.CharField(
        source="shop.name",
        read_only=True,
    )
    brand_name = serializers.CharField(
        source="brand.name",
        read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "pack_size",
            "price",
            "mrp",
            "gst_rate",
            "stock_quantity",
            "image",
            "is_active",
            "shop",
            "shop_name",
            "category",
            "category_name",
            "brand",
            "brand_name",
        ]


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = "__all__"


class ShopProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopProduct
        fields = "__all__"