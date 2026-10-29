
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q, Sum
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from decimal import Decimal
from uuid import uuid4

import logging
import razorpay

logger = logging.getLogger(__name__)

from customer.models import Address
from .models import (
    IndiaCart,
    IndiaCartItem,
    IndiaCategory,
    IndiaOrder,
    IndiaOrderItem,
    IndiaOrderNotification,
    IndiaProductReview,
    IndiaWishlistItem,
    IndiaProduct,
    ResellingProduct,
)

from .notifications import notify_order_status, notify_payment_success
from .stock_services import reserve_stock_for_cart_items, reserve_stock_for_products, release_order_stock



from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from .models import IndiaReturnRequest, IndiaShoppingSettings

from customer.models import Banner as CustomerBanner


def india_search_view(request):
    query = (request.GET.get("q") or "").strip()[:100]
    category_slug = (request.GET.get("category") or "").strip()[:140]
    sort = (request.GET.get("sort") or "newest").strip()
    min_raw = (request.GET.get("min_price") or "").strip()[:30]
    max_raw = (request.GET.get("max_price") or "").strip()[:30]

    qs = (
        ResellingProduct.objects
        .filter(listing_status="active", source_status="available")
        # BYXOM-DEMO-LISTING-SEARCH-GUARD-V1
        .exclude(source_name__icontains="DEMO")
        .exclude(description__icontains="DEMO PRODUCT")
        .filter(Q(category__is_active=True) | Q(category__isnull=True))
        .select_related("category")
    )

    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(source_name__icontains=query)
        )

    categories = IndiaCategory.objects.filter(is_active=True).order_by("name")
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    try:
        low = Decimal(min_raw) if min_raw else None
        if low is not None and (not low.is_finite() or low < 0):
            low, min_raw = None, ""
    except Exception:
        low, min_raw = None, ""

    try:
        high = Decimal(max_raw) if max_raw else None
        if high is not None and (not high.is_finite() or high < 0):
            high, max_raw = None, ""
    except Exception:
        high, max_raw = None, ""

    if low is not None:
        qs = qs.filter(selling_price__gte=low)
    if high is not None:
        qs = qs.filter(selling_price__lte=high)

    if sort == "price-low":
        qs = qs.order_by("selling_price", "name")
    elif sort == "price-high":
        qs = qs.order_by("-selling_price", "name")
    elif sort == "featured":
        qs = qs.order_by("-is_featured", "-created_at")
    else:
        sort = "newest"
        qs = qs.order_by("-created_at", "-pk")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "india_store/search.html", {
        "query": query,
        "categories": categories,
        "selected_category": category_slug,
        "sort": sort,
        "min_price": min_raw,
        "max_price": max_raw,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "result_count": paginator.count,
    })


def india_category_detail_view(request, slug):
    category = get_object_or_404(
        IndiaCategory,
        slug=slug,
        is_active=True,
    )

    products = IndiaProduct.objects.filter(
        category=category,
        is_active=True,
        stock__gt=0,
    ).select_related("category").order_by("-is_featured", "-created_at")

    reselling_products = ResellingProduct.objects.filter(
        category=category,
        listing_status="active",
        source_status="available",
    ).exclude(
        source_name__icontains="DEMO"
    ).exclude(
        description__icontains="DEMO PRODUCT"
    ).select_related("category").order_by(
        "-is_featured", "-created_at"
    )

    return render(
        request,
        "india_store/category_detail.html",
        {
            "category": category,
            "products": products,
            "reselling_products": reselling_products,
        },
    )


def india_home(request):
    categories = IndiaCategory.objects.filter(
        is_active=True,
        show_on_home=True,
    ).order_by("sort_order", "name")

    products = IndiaProduct.objects.filter(
        is_active=True,
        stock__gt=0,
        category__is_active=True,
    ).select_related("category").order_by("-created_at")

    reselling_products = (
        ResellingProduct.objects.filter(
            listing_status="active",
            source_status="available",
        )
        .exclude(source_name__icontains="DEMO")
        .exclude(description__icontains="DEMO PRODUCT")
        .filter(
            Q(category__is_active=True) | Q(category__isnull=True)
        )
        .select_related("category")
        .annotate(
            sold_quantity=Coalesce(
                Sum(
                    "india_order_items__quantity",
                    filter=Q(india_order_items__order__status="Delivered"),
                ),
                0,
            )
        )
        .order_by("-sold_quantity", "-is_featured", "-created_at")[:16]
    )

    cart_count = 0
    if request.user.is_authenticated:
        cart_count = (
            IndiaCartItem.objects.filter(cart__user=request.user)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )

    store_banners = (
        CustomerBanner.objects.filter(is_active=True)
        .exclude(image="")
        .order_by("display_order", "-created_at")[:8]
    )

    context = {
        "categories": categories,
        "products": products,
        "reselling_products": reselling_products,
        "store_banners": store_banners,
        "cart_count": cart_count,
    }




    festival_products = (

        IndiaProduct.objects.filter(

            is_active=True,

            stock__gt=0,

            category__is_active=True,

        )

        .filter(

            Q(name__icontains="diwali")

            | Q(name__icontains="festive")

            | Q(name__icontains="diyas")

            | Q(name__icontains="light")

            | Q(name__icontains="decor")

            | Q(name__icontains="gift")

            | Q(description__icontains="diwali")

            | Q(description__icontains="festive")

            | Q(description__icontains="decor")

            | Q(category__name__icontains="festive")

            | Q(category__name__icontains="decor")

            | Q(category__name__icontains="home")

        )

        .select_related("category")

        .order_by("-created_at", "name")[:12]

    )

    context["festival_products"] = festival_products


    return render(
        request,
        "india_store/home.html",
        context,
    )


@login_required
def india_cart_view(request):
    cart = IndiaCart.objects.filter(user=request.user).first()
    items = (
        cart.items.select_related("product", "own_product").all()
        if cart is not None
        else []
    )
    subtotal = cart.subtotal if cart is not None else 0
    cart_item_count = sum(int(item.quantity) for item in items)
    estimated_coins_total = sum(
        max(0, int(getattr(item.display_product, "reward_coins", 0) or 0)) * int(item.quantity)
        for item in items
    )
    coins_enabled = IndiaShoppingSettings.get_settings().coins_enabled

    return render(
        request,
        "india_store/cart.html",
        {
            "cart": cart,
            "items": items,
            "subtotal": subtotal,
            "cart_item_count": cart_item_count,
            "coins_enabled": coins_enabled,
            "estimated_coins_total": estimated_coins_total,
        },
    )


@login_required
@require_POST
def india_cart_add_view(request, product_id):
    product = get_object_or_404(
        ResellingProduct,
        pk=product_id,
        listing_status="active",
        source_status="available",
    )
    if (
        "DEMO" in (product.source_name or "").upper()
        or "DEMO PRODUCT" in (product.description or "").upper()
    ):
        messages.error(request, "This demo product is not available for ordering.")
        return redirect("india_store:india_home")

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(1, min(quantity, 99))
    cart, _ = IndiaCart.objects.get_or_create(user=request.user)

    with transaction.atomic():
        item = (
            IndiaCartItem.objects.select_for_update()
            .filter(cart=cart, product=product)
            .first()
        )

        if item is None:
            IndiaCartItem.objects.create(
                cart=cart,
                product=product,
                quantity=quantity,
                price=product.selling_price,
            )
        else:
            item.quantity = min(item.quantity + quantity, 99)
            item.price = product.selling_price
            item.save(
                update_fields=["quantity", "price", "updated_at"]
            )

    messages.success(request, f"{product.name} added to your All India Cart.")
    return redirect("india_store:cart")


@login_required
@require_POST
def india_stock_cart_add_view(request, product_id):
    """Add a sellable BYXOM-owned IndiaProduct to the same customer cart."""
    product = get_object_or_404(
        IndiaProduct.objects.select_related("category"),
        pk=product_id,
        is_active=True,
        stock__gt=0,
        category__is_active=True,
    )
    if product.selling_price is None or product.selling_price <= 0:
        messages.error(request, "This product does not have a valid selling price yet.")
        return redirect("india_store:stock_product_detail", product_id=product_id)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, min(quantity, 99))
    if quantity > product.stock:
        messages.error(request, f"Only {product.stock} unit(s) are currently available.")
        return redirect("india_store:stock_product_detail", product_id=product_id)

    cart, _ = IndiaCart.objects.get_or_create(user=request.user)
    with transaction.atomic():
        item = IndiaCartItem.objects.select_for_update().filter(
            cart=cart, own_product=product
        ).first()
        new_quantity = min((item.quantity if item else 0) + quantity, 99)
        if new_quantity > product.stock:
            messages.error(request, f"Only {product.stock} unit(s) are currently available.")
            return redirect("india_store:stock_product_detail", product_id=product_id)
        if item is None:
            IndiaCartItem.objects.create(
                cart=cart, own_product=product, quantity=quantity,
                price=product.selling_price,
            )
        else:
            item.quantity = new_quantity
            item.price = product.selling_price
            item.save(update_fields=["quantity", "price", "updated_at"])

    messages.success(request, f"{product.name} added to your All India Cart.")
    return redirect("india_store:cart")


@login_required
@require_POST
def india_cart_update_view(request, item_id):
    item = get_object_or_404(
        IndiaCartItem.objects.select_related("product", "own_product"),
        pk=item_id,
        cart__user=request.user,
    )

    try:
        quantity = int(request.POST.get("quantity", ""))
    except (TypeError, ValueError):
        messages.error(request, "Enter a valid quantity.")
        return redirect("india_store:cart")

    if quantity < 1:
        messages.error(request, "Quantity must be at least 1.")
        return redirect("india_store:cart")

    product = item.display_product
    if item.is_own_inventory:
        available = (
            product.is_active and product.category.is_active
            and product.stock >= quantity and product.selling_price is not None
            and product.selling_price > 0
        )
    else:
        available = (
            product.listing_status == "active"
            and product.source_status == "available"
            and "DEMO" not in (product.source_name or "").upper()
            and "DEMO PRODUCT" not in (product.description or "").upper()
            and product.selling_price is not None and product.selling_price > 0
        )
    if not available:
        messages.error(request, "This product is currently unavailable or the requested quantity exceeds stock. Remove it or reduce the quantity.")
        return redirect("india_store:cart")

    if quantity > 99:
        quantity = 99
        messages.warning(request, "Maximum quantity is 99.")

    item.quantity = quantity
    item.price = product.selling_price
    item.save(update_fields=["quantity", "price", "updated_at"])
    messages.success(request, "Cart quantity updated.")
    return redirect("india_store:cart")


@login_required
@require_POST
def india_cart_remove_view(request, item_id):
    item = get_object_or_404(
        IndiaCartItem,
        pk=item_id,
        cart__user=request.user,
    )
    item_name = item.display_product.name
    item.delete()

    messages.success(request, f"{item_name} removed from your All India Cart.")
    return redirect("india_store:cart")


@login_required
@require_http_methods(["GET", "POST"])
def india_checkout_view(request):
    cart = IndiaCart.objects.filter(user=request.user).first()
    if cart is None or not cart.items.exists():
        messages.info(request, "Your All India Cart is empty.")
        return redirect("india_store:cart")

    addresses = request.user.addresses.all().order_by(
        "-is_default", "-created_at"
    )

    if request.method == "POST":
        payment_method = (request.POST.get("payment_method") or "COD").strip().upper()
        if payment_method == "ONLINE":
            if not getattr(settings, "INDIA_ONLINE_CHECKOUT_ENABLED", False):
                messages.info(
                    request,
                    "Online payment is not available at the request stage. "
                    "Our team will call to confirm availability and the final price first.",
                )
                return redirect("india_store:checkout")
            return india_razorpay_start_view(request)
        if payment_method != "COD":
            messages.error(request, "Please select a valid payment method.")
            return redirect("india_store:checkout")

        try:
            address_id = int(request.POST.get("address_id", ""))
        except (TypeError, ValueError):
            messages.error(request, "Please select a delivery address.")
            return redirect("india_store:checkout")

        address = get_object_or_404(
            Address, pk=address_id, user=request.user
        )

        with transaction.atomic():
            cart = IndiaCart.objects.select_for_update().filter(
                user=request.user
            ).first()

            if cart is None:
                messages.info(request, "Your cart is empty.")
                return redirect("india_store:cart")

            items = list(
                cart.items.select_related("product", "own_product", "own_product__category").select_for_update()
            )
            if not items:
                messages.info(request, "Your cart is empty.")
                return redirect("india_store:cart")

            stock_pools, stock_error = reserve_stock_for_cart_items(items)
            if stock_error:
                messages.error(request, stock_error)
                return redirect("india_store:cart")

            subtotal = sum(
                (
                    item.display_product.selling_price * item.quantity
                    for item in items
                ),
                Decimal("0.00"),
            )

            # Development placeholder: configure shipping before production.
            delivery_fee = Decimal("0.00")
            order = IndiaOrder.objects.create(
                user=request.user,
                address=address,
                shipping_full_name=address.full_name,
                shipping_mobile=address.mobile,
                shipping_address_line=address.address_line,
                shipping_city=address.city,
                shipping_state=address.state,
                shipping_pincode=address.pincode,
                order_number=f"BYX-IN-{uuid4().hex[:16].upper()}",
                status="Pending",
                payment_method="COD",
                payment_status="Pending",
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total_amount=subtotal + delivery_fee,
            )

            for item in items:
                IndiaOrderItem.objects.create(
                    order=order,
                    product=item.product,
                    own_product=item.own_product,
                    product_name=item.display_product.name,
                    quantity=item.quantity,
                    price=item.display_product.selling_price,
                    stock_pool=stock_pools[item.pk],
                    stock_deducted=True,
                    stock_restored=False,
                    stock_deducted_at=timezone.now(),
                )


            notify_order_status(order)
            cart.items.all().delete()

        return render(
            request,
            "india_store/order_success.html",
            {"order": order},
        )

    items = list(cart.items.select_related("product", "own_product").all())
    checkout_lines = [
        {
            "item": item,
            "line_total": item.display_product.selling_price * item.quantity,
        }
        for item in items
    ]
    subtotal = sum(
        (line["line_total"] for line in checkout_lines),
        Decimal("0.00"),
    )
    delivery_fee = Decimal("0.00")

    return render(
        request,
        "india_store/checkout.html",
        {
            "checkout_lines": checkout_lines,
            "addresses": addresses,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total_amount": subtotal + delivery_fee,
        },
    )


@login_required
def india_orders_view(request):
    orders = (
        IndiaOrder.objects
        .filter(user=request.user)
        .select_related("reward_record")
        .prefetch_related("return_requests")
        .order_by("-created_at")
    )
    policy = IndiaShoppingSettings.get_settings()
    return render(
        request,
        "india_store/orders.html",
        {
            "orders": orders,
            "return_window_days": policy.return_window_days,
            "coins_enabled": policy.coins_enabled,
        },
    )


@login_required
@require_POST
def india_order_cancel_view(request, order_number):
    with transaction.atomic():
        order = get_object_or_404(
            IndiaOrder.objects.select_for_update(),
            order_number=order_number,
            user=request.user,
        )

        # Only unpaid, pending COD orders can be cancelled by customers.
        if (
            order.status != "Pending"
            or order.payment_method != "COD"
            or order.payment_status != "Pending"
            or bool((order.supplier_order_id or "").strip())
        ):
            messages.error(
                request,
                "This order can no longer be cancelled from your account.",
            )
        else:
            release_order_stock(order)
            order.status = "Cancelled"
            order.save(update_fields=["status", "updated_at"])
            notify_order_status(order)
            messages.success(
                request,
                f"Order {order.order_number} has been cancelled.",
            )

    return redirect(
        "india_store:order_detail",
        order_number=order_number,
    )



@login_required
@require_POST
def india_return_request_view(request, order_number, item_id):
    """Submit a return request for an eligible item in the customer's order."""
    try:
        quantity = int((request.POST.get("quantity") or "1").strip())
    except (TypeError, ValueError):
        messages.error(request, "Please enter a valid return quantity.")
        return redirect("india_store:order_detail", order_number=order_number)

    reason = (request.POST.get("reason") or "").strip()[:1000]
    if quantity < 1 or len(reason) < 3:
        messages.error(
            request,
            "Enter a valid quantity and a return reason of at least 3 characters.",
        )
        return redirect("india_store:order_detail", order_number=order_number)

    active_statuses = ["REQUESTED", "APPROVED", "PICKUP_SCHEDULED", "RECEIVED"]

    try:
        with transaction.atomic():
            order = get_object_or_404(
                IndiaOrder.objects.select_for_update(),
                order_number=order_number,
                user=request.user,
            )
            item = get_object_or_404(
                IndiaOrderItem.objects.select_for_update(),
                pk=item_id,
                order=order,
            )

            policy = IndiaShoppingSettings.get_settings()
            window_days = max(1, min(int(policy.return_window_days or 7), 30))

            if order.status != "Delivered":
                messages.error(request, "Returns can only be requested after delivery.")
                return redirect("india_store:order_detail", order_number=order_number)

            if not order.delivered_at:
                messages.error(
                    request,
                    "The order's delivery date is not recorded. Contact BYXOM support "
                    "to check return eligibility.",
                )
                return redirect("india_store:order_detail", order_number=order_number)

            if timezone.now() > order.delivered_at + timedelta(days=window_days):
                messages.error(
                    request,
                    f"The {window_days}-day return window has closed.",
                )
                return redirect("india_store:order_detail", order_number=order_number)

            item_requests = IndiaReturnRequest.objects.filter(order_item=item)
            if item_requests.filter(status__in=active_statuses).exists():
                messages.error(
                    request,
                    "A return request for this item is already being processed.",
                )
                return redirect("india_store:order_detail", order_number=order_number)

            used_quantity = (
                item_requests.exclude(status="REJECTED")
                .aggregate(total=Sum("quantity"))["total"] or 0
            )
            remaining = max(0, item.quantity - used_quantity)

            if remaining < 1 or quantity > remaining:
                messages.error(
                    request,
                    f"Return quantity cannot exceed {remaining} remaining item(s).",
                )
                return redirect("india_store:order_detail", order_number=order_number)

            return_request = IndiaReturnRequest(
                order=order,
                order_item=item,
                user=request.user,
                quantity=quantity,
                reason=reason,
                status="REQUESTED",
            )
            return_request.full_clean()
            return_request.save()

    except IntegrityError:
        messages.error(
            request,
            "A return request already exists for this item. Refresh the order and check its status.",
        )
        return redirect("india_store:order_detail", order_number=order_number)
    except ValidationError as exc:
        messages.error(
            request,
            "Return request could not be saved: " + " ".join(exc.messages),
        )
        return redirect("india_store:order_detail", order_number=order_number)

    messages.success(request, "Return request submitted for BYXOM review.")
    return redirect("india_store:order_detail", order_number=order_number)



@login_required
def india_order_detail_view(request, order_number):
    order = get_object_or_404(
        IndiaOrder.objects.select_related("address", "reward_record").prefetch_related("items"),
        order_number=order_number,
        user=request.user,
    )
    policy = IndiaShoppingSettings.get_settings()
    window_days = max(1, min(int(policy.return_window_days or 7), 30))
    now = timezone.now()
    deadline = (
        order.delivered_at + timedelta(days=window_days)
        if order.delivered_at else None
    )
    in_return_window = (
        order.status == "Delivered"
        and deadline is not None
        and now <= deadline
    )

    item_rows = []
    for item in order.items.all():
        item_requests = list(
            item.return_requests.filter(user=request.user).order_by("-created_at")
        )
        has_active = any(
            r.status in IndiaReturnRequest.ACTIVE_STATUSES for r in item_requests
        )
        used_quantity = sum(
            r.quantity for r in item_requests if r.status != "REJECTED"
        )
        remaining = max(0, item.quantity - used_quantity)
        can_return = in_return_window and not has_active and remaining > 0

        return_message = ""
        if order.status == "Delivered":
            if not order.delivered_at:
                return_message = "Delivery date is not recorded; contact BYXOM support."
            elif now > deadline:
                return_message = f"The {window_days}-day return window has closed."
            elif has_active:
                return_message = "A return request is already being processed."
            elif remaining <= 0:
                return_message = "No return quantity remains available."

        item_rows.append({
            "item": item,
            "requests": item_requests,
            "can_return": can_return,
            "remaining_quantity": remaining,
            "return_message": return_message,
        })

    return render(
        request,
        "india_store/order_detail.html",
        {
            "order": order,
            "reward": getattr(order, "reward_record", None),
            "item_rows": item_rows,
            "return_window_days": window_days,
        },
    )


@login_required
@require_POST
def india_razorpay_start_view(request):
    """Create a separate Razorpay order for an All India cart."""

    if not getattr(settings, "INDIA_ONLINE_CHECKOUT_ENABLED", False):
        messages.info(
            request,
            "Online payment is paused until the order request is confirmed by phone.",
        )
        return redirect("india_store:checkout")

    # BYXOM-ONLINE-STOCK-RESERVATION-GUARD-V1
    # Do not enable online checkout until pending/abandoned payment reservations
    # can be reconciled safely with the gateway.
    messages.info(
        request,
        "Online checkout remains paused while stock reservation and payment reconciliation are completed.",
    )
    return redirect("india_store:checkout")

    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        messages.error(request, "Razorpay configuration is missing.")
        return redirect("india_store:checkout")

    # Local development must use Razorpay test credentials.
    if settings.DEBUG and not key_id.startswith("rzp_test_"):
        messages.error(
            request,
            "For local testing, configure a Razorpay test key (rzp_test_...). "
            "Live-key checkout is blocked while DEBUG is enabled.",
        )
        return redirect("india_store:checkout")

    try:
        address_id = int(request.POST.get("address_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "Please select a delivery address.")
        return redirect("india_store:checkout")

    address = get_object_or_404(
        Address,
        pk=address_id,
        user=request.user,
    )

    cart = IndiaCart.objects.filter(user=request.user).first()
    if cart is None:
        messages.error(request, "Your All India Cart is empty.")
        return redirect("india_store:cart")

    items = list(
        cart.items.select_related("product").order_by("product_id")
    )
    if not items:
        messages.error(request, "Your All India Cart is empty.")
        return redirect("india_store:cart")

    def snapshot_lines(cart_items):
        return tuple(
            (
                item.product_id,
                item.quantity,
                item.product.selling_price,
            )
            for item in cart_items
        )

    def items_available(cart_items):
        return all(
            item.quantity >= 1
            and item.product.listing_status == "active"
            and item.product.source_status == "available"
            # BYXOM-DEMO-PAYMENT-CART-GUARD-V1
            and "DEMO" not in (item.product.source_name or "").upper()
            and "DEMO PRODUCT" not in (item.product.description or "").upper()
            and item.product.selling_price is not None
            and item.product.selling_price > 0
            for item in cart_items
        )

    if not items_available(items):
        messages.error(
            request,
            "One or more products are unavailable. Please review your cart.",
        )
        return redirect("india_store:cart")

    initial_snapshot = snapshot_lines(items)
    subtotal = sum(
        (
            item.product.selling_price * item.quantity
            for item in items
        ),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    # Configure the real shipping amount before production launch.
    delivery_fee = Decimal("0.00")
    total_amount = subtotal + delivery_fee

    if total_amount <= 0:
        messages.error(request, "Online payment amount must be greater than zero.")
        return redirect("india_store:checkout")

    amount_paise = int(
        (total_amount * Decimal("100")).quantize(Decimal("1"))
    )
    order_number = f"BYX-IN-{uuid4().hex[:16].upper()}"

    client = razorpay.Client(auth=(key_id, key_secret))

    try:
        gateway_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order_number,
        })

        gateway_order_id = str(gateway_order.get("id") or "")
        if (
            not gateway_order_id
            or int(gateway_order.get("amount", 0)) != amount_paise
            or gateway_order.get("currency") != "INR"
        ):
            raise ValueError("Gateway order response did not match the expected amount.")

    except Exception:
        messages.error(
            request,
            "Could not start Razorpay checkout. No payment window was opened; please retry.",
        )
        return redirect("india_store:checkout")

    try:
        with transaction.atomic():
            fresh_cart = (
                IndiaCart.objects.select_for_update()
                .filter(user=request.user)
                .first()
            )
            if fresh_cart is None:
                raise ValueError("Cart is no longer available.")

            fresh_items = list(
                fresh_cart.items.select_related("product").order_by("product_id")
            )

            if (
                not fresh_items
                or not items_available(fresh_items)
                or snapshot_lines(fresh_items) != initial_snapshot
            ):
                raise ValueError(
                    "Your cart changed while payment was starting. "
                    "Please review your cart and try again."
                )

            order = IndiaOrder.objects.create(
                user=request.user,
                address=address,
                shipping_full_name=address.full_name,
                shipping_mobile=address.mobile,
                shipping_address_line=address.address_line,
                shipping_city=address.city,
                shipping_state=address.state,
                shipping_pincode=address.pincode,
                order_number=order_number,
                status="Pending",
                payment_method="ONLINE",
                payment_status="Pending",
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total_amount=total_amount,
                razorpay_order_id=gateway_order_id,
                razorpay_amount_paise=amount_paise,
            )

            for item in fresh_items:
                IndiaOrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    price=item.product.selling_price,
                )

    except ValueError as error:
        messages.error(request, str(error))
        return redirect("india_store:cart")
    except Exception:
        messages.error(
            request,
            "The payment order could not be saved, so checkout was not opened. "
            "Please review your cart and try again.",
        )
        return redirect("india_store:checkout")

    return render(
        request,
        "india_store/razorpay_payment.html",
        {
            "razorpay_key_id": key_id,
            "gateway_order_id": gateway_order_id,
            "amount_paise": amount_paise,
            "order": order,
            "customer_name": address.full_name,
            "customer_mobile": address.mobile,
            "customer_email": getattr(request.user, "email", "") or "",
        },
    )


@login_required
@require_POST
def india_razorpay_verify_view(request):
    """Verify and capture Razorpay payment for the user's All India order."""

    order_number = (request.POST.get("order_number") or "").strip()
    payment_id = (request.POST.get("razorpay_payment_id") or "").strip()
    returned_order_id = (request.POST.get("razorpay_order_id") or "").strip()
    signature = (request.POST.get("razorpay_signature") or "").strip()

    if not order_number:
        messages.error(request, "Order reference is missing.")
        return redirect("india_store:orders")

    order = get_object_or_404(
        IndiaOrder,
        order_number=order_number,
        user=request.user,
        payment_method="ONLINE",
    )

    detail_url = "india_store:order_detail"
    detail_kwargs = {"order_number": order.order_number}

    # Idempotent response: this exact payment has already been applied.
    if order.payment_status == "Paid":
        if order.razorpay_payment_id == payment_id and payment_id:
            messages.info(request, "Payment was already verified for this order.")
        else:
            messages.error(request, "This order already has a verified payment.")
        return redirect(detail_url, **detail_kwargs)

    if order.payment_status != "Pending":
        messages.error(request, "This order is not awaiting an online payment.")
        return redirect(detail_url, **detail_kwargs)

    if (
        not payment_id
        or not returned_order_id
        or not signature
        or not order.razorpay_order_id
        or returned_order_id != order.razorpay_order_id
        or not order.razorpay_amount_paise
    ):
        messages.error(request, "The Razorpay payment response is incomplete or does not match.")
        return redirect(detail_url, **detail_kwargs)

    expected_paise = int(order.razorpay_amount_paise)
    saved_total_paise = int(
        (order.total_amount * Decimal("100")).quantize(Decimal("1"))
    )
    if expected_paise <= 0 or expected_paise != saved_total_paise:
        messages.error(
            request,
            f"Saved order amount does not match the payment reference. "
            f"Please contact support with order {order.order_number}.",
        )
        return redirect(detail_url, **detail_kwargs)

    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        messages.error(request, "Razorpay verification is not configured.")
        return redirect(detail_url, **detail_kwargs)

    client = razorpay.Client(auth=(key_id, key_secret))

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order.razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
    except Exception:
        messages.error(
            request,
            "Razorpay signature verification failed. The order remains unpaid.",
        )
        return redirect(detail_url, **detail_kwargs)

    try:
        gateway_payment = client.payment.fetch(payment_id)
    except Exception:
        messages.error(
            request,
            f"Could not confirm payment with Razorpay. Keep order "
            f"{order.order_number} pending and contact support if money was deducted.",
        )
        return redirect(detail_url, **detail_kwargs)

    if gateway_payment.get("order_id") != order.razorpay_order_id:
        messages.error(request, "Gateway order ID does not match this order.")
        return redirect(detail_url, **detail_kwargs)

    actual_paise = int(gateway_payment.get("amount", 0) or 0)
    currency = gateway_payment.get("currency")
    status = gateway_payment.get("status")

    if actual_paise != expected_paise or currency != "INR":
        if status == "captured" and actual_paise > 0:
            try:
                client.payment.refund(payment_id, {"amount": actual_paise})
                messages.error(
                    request,
                    "Captured payment amount/currency did not match. "
                    f"A refund was requested. Reference: {payment_id}.",
                )
            except Exception:
                messages.error(
                    request,
                    "Captured payment did not match this order. "
                    f"Please contact support with payment ID {payment_id}.",
                )
        else:
            messages.error(
                request,
                "Payment amount or currency does not match this order. "
                "The order remains unpaid.",
            )
        return redirect(detail_url, **detail_kwargs)

    if status == "authorized":
        try:
            gateway_payment = client.payment.capture(
                payment_id,
                expected_paise,
            )
        except Exception:
            # Capture requests can time out after the gateway has processed them.
            try:
                gateway_payment = client.payment.fetch(payment_id)
            except Exception:
                messages.error(
                    request,
                    f"Payment capture is not confirmed. Order remains unpaid. "
                    f"Payment reference: {payment_id}.",
                )
                return redirect(detail_url, **detail_kwargs)

        status = gateway_payment.get("status")

    if (
        gateway_payment.get("order_id") != order.razorpay_order_id
        or int(gateway_payment.get("amount", 0) or 0) != expected_paise
        or gateway_payment.get("currency") != "INR"
        or status != "captured"
    ):
        messages.error(
            request,
            "Razorpay has not confirmed a captured payment. "
            "The order has not been marked paid.",
        )
        return redirect(detail_url, **detail_kwargs)

    already_paid = False
    stock_reservation_error = None

    try:
        with transaction.atomic():
            locked_order = (
                IndiaOrder.objects.select_for_update()
                .get(pk=order.pk, user=request.user)
            )

            if locked_order.payment_status == "Paid":
                if locked_order.razorpay_payment_id == payment_id:
                    already_paid = True
                else:
                    raise ValueError("A different payment is already linked to this order.")

            elif locked_order.payment_status != "Pending":
                raise ValueError("This order is no longer awaiting payment.")

            else:
                duplicate_payment = (
                    IndiaOrder.objects.filter(
                        razorpay_payment_id=payment_id
                    ).exclude(pk=locked_order.pk).exists()
                )
                if duplicate_payment:
                    raise ValueError(
                        "This payment ID is already linked to another order."
                    )

                # Reserve stock in the same transaction that marks payment paid.
                order_items = list(
                    locked_order.items.select_for_update().order_by("product_id")
                )
                if not order_items:
                    stock_reservation_error = (
                        "This order has no saved items; stock cannot be reserved."
                    )
                elif any(line.product_id is None or line.own_product_id is not None for line in order_items):
                    stock_reservation_error = (
                        "Online payment reconciliation currently supports legacy reseller orders only."
                    )
                else:
                    stock_pools, stock_reservation_error = reserve_stock_for_products(
                        [(line.product_id, line.quantity) for line in order_items]
                    )

                if stock_reservation_error:
                    raise ValueError("STOCK_RESERVATION_FAILED")

                reserved_at = timezone.now()
                for line in order_items:
                    line.stock_pool = stock_pools[line.product_id]
                    line.stock_deducted = True
                    line.stock_restored = False
                    line.stock_deducted_at = reserved_at
                    line.stock_restored_at = None
                    line.save(update_fields=[
                        "stock_pool",
                        "stock_deducted",
                        "stock_restored",
                        "stock_deducted_at",
                        "stock_restored_at",
                    ])

                locked_order.razorpay_payment_id = payment_id
                locked_order.payment_status = "Paid"
                locked_order.status = "Confirmed"
                locked_order.save(
                    update_fields=[
                        "razorpay_payment_id",
                        "payment_status",
                        "status",
                        "updated_at",
                    ]
                )

                # Clear the cart only if its product/quantity set still matches
                # the order snapshot. Keep any cart changes made during checkout.
                current_cart = (
                    IndiaCart.objects.select_for_update()
                    .filter(user=request.user)
                    .first()
                )
                if current_cart is not None:
                    order_lines = {
                        line.product_id: line.quantity
                        for line in locked_order.items.all()
                    }
                    cart_lines = {
                        line.product_id: line.quantity
                        for line in current_cart.items.all()
                    }
                    if order_lines and cart_lines == order_lines:
                        current_cart.items.all().delete()

    except IntegrityError:
        existing_order = IndiaOrder.objects.filter(
            razorpay_payment_id=payment_id
        ).first()
        if (
            existing_order is not None
            and existing_order.pk == order.pk
            and existing_order.payment_status == "Paid"
        ):
            already_paid = True
        else:
            messages.error(
                request,
                "This payment reference could not be linked uniquely. "
                f"Please contact support with payment ID {payment_id}.",
            )
            return redirect(detail_url, **detail_kwargs)

    except ValueError as error:
        if stock_reservation_error:
            # The DB transaction rolled back, so stock and local payment status
            # remain unchanged. Try to return captured funds, but do not claim
            # the refund is complete until Razorpay confirms it.
            refunded_paise = int(gateway_payment.get("amount_refunded", 0) or 0)
            if refunded_paise > 0:
                messages.error(
                    request,
                    "Stock could not be reserved for this captured payment. "
                    f"Razorpay already reports {refunded_paise} paise refunded; "
                    f"do not issue another automatic refund. Reconcile payment "
                    f"{payment_id} for order {order.order_number} in Razorpay.",
                )
            else:
                try:
                    refund_response = client.payment.refund(
                        payment_id,
                        {"amount": expected_paise},
                    )
                    refund_status = (
                        refund_response.get("status", "unknown")
                        if isinstance(refund_response, dict)
                        else "unknown"
                    )
                    messages.error(
                        request,
                        "Stock could not be reserved, so this order remains unpaid "
                        "locally and unconfirmed. A Razorpay refund request was sent "
                        f"(gateway status: {refund_status}); this is not proof that "
                        f"the refund is complete. Check Razorpay for payment "
                        f"{payment_id} and order {order.order_number}.",
                    )
                except Exception:
                    messages.error(
                        request,
                        "URGENT: Payment was captured but stock could not be reserved "
                        "and the automatic refund request failed. Do not fulfil this "
                        f"order. Check Razorpay payment {payment_id} for order "
                        f"{order.order_number} and reconcile/refund manually.",
                    )
        else:
            messages.error(request, str(error))
        return redirect(detail_url, **detail_kwargs)

    except Exception:
        # The gateway has captured funds, but the local transaction failed.
        # Attempt a refund rather than silently fulfilling an unrecorded payment.
        try:
            client.payment.refund(payment_id, {"amount": expected_paise})
            messages.error(
                request,
                "Payment was captured, but the order could not be updated. "
                f"A refund was requested. Payment reference: {payment_id}.",
            )
        except Exception:
            messages.error(
                request,
                "Payment was captured, but the order could not be updated. "
                f"Contact support urgently with payment ID {payment_id} "
                f"and order {order.order_number}.",
            )
        return redirect(detail_url, **detail_kwargs)

    # Payment is already verified and saved. Notifications are best-effort:
    # a notification failure must not trigger payment/refund error handling.
    try:
        order.refresh_from_db()
    except Exception:
        logger.exception(
            "Could not refresh verified All India order %s for notifications",
            order.order_number,
        )
    else:
        for notifier in (notify_payment_success, notify_order_status):
            try:
                notifier(order)
            except Exception:
                logger.exception(
                    "Failed to create %s notification for All India order %s",
                    notifier.__name__,
                    order.order_number,
                )

    if already_paid:
        messages.info(request, "Payment was already verified for this order.")
    else:
        messages.success(request, "Payment captured and All India order confirmed.")

    return redirect(detail_url, **detail_kwargs)


def india_product_detail_view(request, product_id):
    product = get_object_or_404(
        ResellingProduct,
        pk=product_id,
        listing_status="active",
        source_status="available",
    )
    if (
        "DEMO" in (product.source_name or "").upper()
        or "DEMO PRODUCT" in (product.description or "").upper()
    ):
        from django.http import Http404
        raise Http404

    approved_reviews = (
        product.reviews.filter(is_approved=True)
        .select_related("user")
    )
    review_stats = approved_reviews.aggregate(avg_rating=Avg("rating"))
    review_count = approved_reviews.count()
    can_review = False
    user_review = None

    if request.user.is_authenticated:
        can_review = IndiaOrderItem.objects.filter(
            order__user=request.user,
            product=product,
            order__status="Delivered",
        ).exists()
        user_review = IndiaProductReview.objects.filter(
            user=request.user,
            product=product,
        ).first()

    return render(
        request,
        "india_store/product_detail.html",
        {
            "product": product,
            "is_own_inventory": False,
            "coins_enabled": IndiaShoppingSettings.get_settings().coins_enabled,
            "reviews": approved_reviews[:20],
            "review_count": review_count,
            "average_rating": review_stats["avg_rating"] or 0,
            "can_review": can_review,
            "user_review": user_review,
            "is_authenticated": request.user.is_authenticated,
            "is_wishlisted": (
                request.user.is_authenticated
                and IndiaWishlistItem.objects.filter(
                    user=request.user, product=product
                ).exists()
            ),
            "related_products": (
                ResellingProduct.objects
                .filter(listing_status="active", source_status="available")
                .exclude(source_name__icontains="DEMO")
                .exclude(description__icontains="DEMO PRODUCT")
                .exclude(pk=product.pk)
                .select_related("category")
                .order_by("-is_featured", "-created_at")[:4]
            ),
        },
    )


@login_required
def india_wishlist_view(request):
    wishlist_items = (
        IndiaWishlistItem.objects
        .filter(user=request.user)
        .exclude(product__source_name__icontains="DEMO")
        .exclude(product__description__icontains="DEMO PRODUCT")
        .select_related("product", "product__category")
    )
    return render(
        request,
        "india_store/wishlist.html",
        {"wishlist_items": wishlist_items},
    )


@require_POST
def india_wishlist_toggle_view(request, product_id):
    # Return guests to the product page after sign-in; never replay a POST
    # request automatically after login.
    if not request.user.is_authenticated:
        return redirect_to_login(
            reverse("india_store:product_detail", kwargs={"product_id": product_id})
        )

    product = get_object_or_404(ResellingProduct, pk=product_id)
    removed = False

    with transaction.atomic():
        existing = (
            IndiaWishlistItem.objects.select_for_update()
            .filter(user=request.user, product=product)
            .first()
        )

        if existing:
            existing.delete()
            removed = True
        elif (
            product.listing_status != "active"
            or product.source_status != "available"
            or "DEMO" in (product.source_name or "").upper()
            or "DEMO PRODUCT" in (product.description or "").upper()
        ):
            messages.error(request, "This product is not currently available to save.")
        else:
            IndiaWishlistItem.objects.get_or_create(
                user=request.user,
                product=product,
            )

    if removed:
        messages.info(request, "Product removed from your wishlist.")
    elif (
        product.listing_status == "active"
        and product.source_status == "available"
    ):
        messages.success(request, "Product saved to your wishlist.")

    if request.POST.get("next") == "wishlist":
        return redirect("india_store:wishlist")
    return redirect("india_store:product_detail", product_id=product_id)


@login_required
@require_POST
def india_review_add_view(request, product_id):
    product = get_object_or_404(ResellingProduct, pk=product_id)

    order_item = (
        IndiaOrderItem.objects
        .filter(
            order__user=request.user,
            product=product,
            order__status="Delivered",
        )
        .select_related("order")
        .order_by("-order__created_at")
        .first()
    )

    if order_item is None:
        messages.error(
            request,
            "You can review this product after your order is marked Delivered.",
        )
        return redirect("india_store:product_detail", product_id=product_id)

    try:
        rating = int(request.POST.get("rating", ""))
    except (TypeError, ValueError):
        rating = 0

    title = (request.POST.get("title") or "").strip()[:120]
    body = (request.POST.get("body") or "").strip()

    if rating < 1 or rating > 5:
        messages.error(request, "Choose a rating from 1 to 5 stars.")
        return redirect("india_store:product_detail", product_id=product_id)

    if not title or len(body) < 10 or len(body) > 3000:
        messages.error(
            request,
            "Add a title and a review of 10 to 3000 characters.",
        )
        return redirect("india_store:product_detail", product_id=product_id)

    review, created = IndiaProductReview.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={
            "order_item": order_item,
            "rating": rating,
            "title": title,
            "body": body,
            "is_approved": False,
        },
    )

    if not created:
        review.order_item = order_item
        review.rating = rating
        review.title = title
        review.body = body
        review.is_approved = False
        review.save(
            update_fields=[
                "order_item",
                "rating",
                "title",
                "body",
                "is_approved",
                "updated_at",
            ]
        )

    messages.success(
        request,
        "Your review was submitted for approval. It will appear after moderation.",
    )
    return redirect("india_store:product_detail", product_id=product_id)

@login_required
def india_notifications_view(request):
    notification_queryset = (
        IndiaOrderNotification.objects
        .filter(user=request.user)
        .select_related("order")
        .order_by("-created_at")
    )
    unread_count = notification_queryset.filter(is_read=False).count()
    page_obj = Paginator(notification_queryset, 20).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "india_store/notifications.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "unread_count": unread_count,
        },
    )


@login_required
@require_POST
def india_notification_read_view(request, notification_id):
    notification = get_object_or_404(
        IndiaOrderNotification,
        pk=notification_id,
        user=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect("india_store:notifications")


def india_stock_product_detail_view(request, product_id):
    """Detail page for BYXOM's own IndiaProduct inventory."""
    from django.shortcuts import get_object_or_404, render
    from .models import IndiaProduct

    product = get_object_or_404(
        IndiaProduct.objects.select_related("category"),
        pk=product_id,
        is_active=True,
        stock__gt=0,
        category__is_active=True,
    )

    related_products = (
        IndiaProduct.objects
        .filter(
            category=product.category,
            is_active=True,
            stock__gt=0,
            category__is_active=True,
        )
        .exclude(pk=product.pk)
        .order_by("name")[:8]
    )

    return render(
        request,
        "india_store/product_detail.html",
        {
            "product": product,
            "is_own_inventory": True,
            "coins_enabled": False,
            "reviews": [],
            "review_count": 0,
            "average_rating": 0,
            "can_review": False,
            "user_review": None,
            "is_authenticated": request.user.is_authenticated,
            "is_wishlisted": False,
            "related_products": related_products,
        },
    )
