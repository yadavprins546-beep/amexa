from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from .models import IndiaOrderItem, IndiaProduct, ResellingProduct


SUPPLIER_STOCK_MAX_AGE = timedelta(hours=24)


def reserve_stock_for_products(lines):
    """
    Validate all product quantities before decrementing any.
    Caller must be inside transaction.atomic().
    Returns (product_id_to_pool, error_message).
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Stock reservation must run inside transaction.atomic().")

    required = {}
    for product_id, quantity in lines:
        if quantity is None or quantity < 1:
            return None, "Cart contains an invalid product quantity."
        required[product_id] = required.get(product_id, 0) + quantity

    if not required:
        return {}, None

    products = list(
        ResellingProduct.objects.select_for_update()
        .filter(pk__in=sorted(required))
        .order_by("pk")
    )
    product_by_id = {product.pk: product for product in products}
    if len(product_by_id) != len(required):
        return None, "A product was removed or is no longer available. Review your cart."

    now = timezone.now()
    deductions = {}
    pools = {}

    # Validate the entire cart first. No quantity changes happen in this loop.
    for product_id, quantity in required.items():
        product = product_by_id[product_id]

        if product.listing_status != "active" or product.source_status != "available":
            return None, f"{product.name} is no longer available. Review your cart."
        if "DEMO" in (product.source_name or "").upper() or "DEMO PRODUCT" in (product.description or "").upper():
            return None, f"{product.name} is a test listing and cannot be ordered."
        if product.selling_price is None or product.selling_price <= 0:
            return None, f"{product.name} does not have a valid selling price."

        if product.fulfillment_method == "byxom":
            stock_field = "inventory_quantity"
            available = product.inventory_quantity
            pool = "byxom"
            if available is None:
                return None, f"BYXOM stock for {product.name} has not been counted. Please try again after stock is recorded."
        elif product.fulfillment_method == "supplier":
            stock_field = "source_quantity"
            available = product.source_quantity
            pool = "supplier"
            if available is None:
                return None, f"Supplier quantity for {product.name} has not been verified."
            if (
                product.stock_checked_at is None
                or now - product.stock_checked_at > SUPPLIER_STOCK_MAX_AGE
                or product.stock_checked_at - now > timedelta(minutes=5)
            ):
                return None, f"Supplier availability for {product.name} is stale. Admin must re-check it before ordering."
        else:
            return None, f"Fulfilment method for {product.name} is not configured."

        if available < quantity:
            return None, f"Insufficient stock for {product.name}. Available: {available}; requested: {quantity}."

        deductions[product_id] = (product, stock_field, quantity)
        pools[product_id] = pool

    # Apply deductions only after every item passed validation.
    for product, stock_field, quantity in deductions.values():
        setattr(product, stock_field, getattr(product, stock_field) - quantity)
        product.save(update_fields=[stock_field, "updated_at"])

    return pools, None


def reserve_stock_for_cart_items(cart_items):
    """Atomically validate and reserve mixed IndiaProduct/ResellingProduct cart lines.

    Caller must be inside transaction.atomic(). Returns a mapping from cart-item
    primary key to stock pool plus an error message. No stock is changed unless
    every line passes validation.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Stock reservation must run inside transaction.atomic().")

    items = list(cart_items)
    if not items:
        return {}, None

    reseller_ids = sorted({item.product_id for item in items if item.product_id is not None})
    own_ids = sorted({item.own_product_id for item in items if item.own_product_id is not None})
    if any((item.product_id is None) == (item.own_product_id is None) for item in items):
        return None, "A cart line has an invalid product reference. Remove it and add the product again."
    if any(item.quantity is None or item.quantity < 1 for item in items):
        return None, "Cart contains an invalid product quantity."

    reseller_products = {
        product.pk: product
        for product in ResellingProduct.objects.select_for_update()
        .filter(pk__in=reseller_ids).order_by("pk")
    }
    own_products = {
        product.pk: product
        for product in IndiaProduct.objects.select_for_update()
        .filter(pk__in=own_ids).order_by("pk")
    }
    if len(reseller_products) != len(reseller_ids) or len(own_products) != len(own_ids):
        return None, "A product was removed or is no longer available. Review your cart."

    now = timezone.now()
    deductions = []
    pools = {}
    reseller_required = {}
    own_required = {}
    for item in items:
        target = own_required if item.own_product_id is not None else reseller_required
        product_id = item.own_product_id if item.own_product_id is not None else item.product_id
        target[product_id] = target.get(product_id, 0) + item.quantity

    # Validate reseller listings and source inventory without mutating stock.
    for product_id, quantity in reseller_required.items():
        product = reseller_products[product_id]
        if product.listing_status != "active" or product.source_status != "available":
            return None, f"{product.name} is no longer available. Review your cart."
        if "DEMO" in (product.source_name or "").upper() or "DEMO PRODUCT" in (product.description or "").upper():
            return None, f"{product.name} is a test listing and cannot be ordered."
        if product.selling_price is None or product.selling_price <= 0:
            return None, f"{product.name} does not have a valid selling price."
        if product.fulfillment_method == "byxom":
            field, available, pool = "inventory_quantity", product.inventory_quantity, "byxom"
            if available is None:
                return None, f"BYXOM stock for {product.name} has not been counted."
        elif product.fulfillment_method == "supplier":
            field, available, pool = "source_quantity", product.source_quantity, "supplier"
            if available is None:
                return None, f"Supplier quantity for {product.name} has not been verified."
            if (product.stock_checked_at is None or now - product.stock_checked_at > SUPPLIER_STOCK_MAX_AGE
                    or product.stock_checked_at - now > timedelta(minutes=5)):
                return None, f"Supplier availability for {product.name} is stale. Admin must re-check it before ordering."
        else:
            return None, f"Fulfilment method for {product.name} is not configured."
        if available < quantity:
            return None, f"Insufficient stock for {product.name}. Available: {available}; requested: {quantity}."
        deductions.append((product, field, quantity))
        for item in items:
            if item.product_id == product_id:
                pools[item.pk] = pool

    # Validate BYXOM's IndiaProduct stock; these have a separate stock column.
    for product_id, quantity in own_required.items():
        product = own_products[product_id]
        if not product.is_active or not product.category.is_active:
            return None, f"{product.name} is no longer available. Review your cart."
        if product.selling_price is None or product.selling_price <= 0:
            return None, f"{product.name} does not have a valid selling price."
        if product.stock < quantity:
            return None, f"Insufficient stock for {product.name}. Available: {product.stock}; requested: {quantity}."
        deductions.append((product, "stock", quantity))
        for item in items:
            if item.own_product_id == product_id:
                pools[item.pk] = "own"

    # All lines are valid. Apply deductions only now, under the outer transaction.
    for product, field, quantity in deductions:
        setattr(product, field, getattr(product, field) - quantity)
        product.save(update_fields=[field, "updated_at"])

    return pools, None


def release_order_stock(order):
    """
    Restore stock once for order items that were explicitly deducted.
    Caller must be inside transaction.atomic(). Historical items and already
    restored reservations are intentionally ignored.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Stock restoration must run inside transaction.atomic().")

    items = list(
        IndiaOrderItem.objects.select_for_update()
        .filter(order=order, stock_deducted=True, stock_restored=False)
        .order_by("product_id", "pk")
    )
    if not items:
        return 0

    reseller_ids = sorted({item.product_id for item in items if item.product_id is not None})
    own_ids = sorted({item.own_product_id for item in items if item.own_product_id is not None})
    reseller_products = {
        product.pk: product
        for product in ResellingProduct.objects.select_for_update()
        .filter(pk__in=reseller_ids).order_by("pk")
    }
    own_products = {
        product.pk: product
        for product in IndiaProduct.objects.select_for_update()
        .filter(pk__in=own_ids).order_by("pk")
    }

    for item in items:
        if item.own_product_id is not None:
            product = own_products.get(item.own_product_id)
            if product is None:
                raise RuntimeError(
                    f"Cannot restore stock for order {order.order_number}: own product {item.own_product_id} is missing."
                )
            if item.stock_pool != "own":
                raise RuntimeError(
                    f"Own-inventory order item {item.pk} has an unexpected stock pool; manual reconciliation is required."
                )
            stock_field = "stock"
        else:
            product = reseller_products.get(item.product_id)
            if product is None:
                raise RuntimeError(
                    f"Cannot restore stock for order {order.order_number}: product {item.product_id} is missing."
                )
            if item.stock_pool == "byxom":
                stock_field = "inventory_quantity"
            elif item.stock_pool == "supplier":
                if (order.supplier_order_id or "").strip():
                    raise RuntimeError(
                        f"Supplier order ID exists for {order.order_number}. Verify supplier cancellation before restoring supplier stock."
                    )
                stock_field = "source_quantity"
            else:
                raise RuntimeError(
                    f"Stock pool is not recorded for order item {item.pk}; manual reconciliation is required."
                )

        current = getattr(product, stock_field)
        if current is None:
            raise RuntimeError(
                f"Stock quantity is blank for {product.name}; manual stock reconciliation is required."
            )

        setattr(product, stock_field, current + item.quantity)
        product.save(update_fields=[stock_field, "updated_at"])

        item.stock_restored = True
        item.stock_restored_at = timezone.now()
        item.save(update_fields=["stock_restored", "stock_restored_at"])

    return len(items)
