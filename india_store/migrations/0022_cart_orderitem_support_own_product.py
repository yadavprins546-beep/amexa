# BYXOM mixed reseller/own-stock cart and order item compatibility.
# Existing historical rows retain their ResellingProduct foreign keys.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("india_store", "0021_indiaorderitem_stock_deducted_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="indiacartitem",
            name="own_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="india_cart_items",
                to="india_store.indiaproduct",
            ),
        ),
        migrations.AlterField(
            model_name="indiacartitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="india_cart_items",
                to="india_store.resellingproduct",
            ),
        ),
        migrations.AddConstraint(
            model_name="indiacartitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(own_product__isnull=False),
                fields=("cart", "own_product"),
                name="uniq_india_cart_own_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="indiacartitem",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, own_product__isnull=True)
                    | models.Q(product__isnull=True, own_product__isnull=False)
                ),
                name="india_cart_item_exactly_one_product",
            ),
        ),
        migrations.AddField(
            model_name="indiaorderitem",
            name="own_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="india_order_items",
                to="india_store.indiaproduct",
            ),
        ),
        migrations.AlterField(
            model_name="indiaorderitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="india_order_items",
                to="india_store.resellingproduct",
            ),
        ),
        migrations.AlterField(
            model_name="indiaorderitem",
            name="stock_pool",
            field=models.CharField(
                choices=[
                    ("byxom", "BYXOM Inventory"),
                    ("supplier", "Supplier-Reported Stock"),
                    ("own", "BYXOM India Product Stock"),
                    ("none", "Not Reserved"),
                ],
                default="none",
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="indiaorderitem",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, own_product__isnull=True)
                    | models.Q(product__isnull=True, own_product__isnull=False)
                ),
                name="india_order_item_exactly_one_product",
            ),
        ),
    ]
