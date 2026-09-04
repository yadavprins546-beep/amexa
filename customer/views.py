import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone

from .forms import (
    AddressForm,
    DeliveryBankDetailsForm,
    DeliveryDocumentsForm,
    DeliveryFinalVerificationForm,
    DeliveryPersonalDetailsForm,
    LoginForm,
    ShopkeeperBankDetailsForm,
    ShopkeeperBadStockForm,
    ShopkeeperBusinessDetailsForm,
    ShopkeeperDocumentsForm,
    ShopkeeperFinalVerificationForm,
    ShopkeeperInventoryUpdateForm,
    ShopkeeperPersonalDetailsForm,
    ShopkeeperProductForm,
    ShopkeeperProfileSettingsForm,
)

from .wallet_services import (
    expire_wallet_coins,
    redeem_coins,
    refund_redeemed_coins,
    reverse_order_reward,
)

from .models import (
    AboutPage,
    Address,
    BadInventoryRecord,
    Banner,
    Brand,
    Cart,
    CartItem,
    Category,
    Coupon,
    CouponUsage,
    DeliveryAssignment,
    DeliveryIncentive,
    DeliveryIncentiveProgress,
    DeliveryPartnerBankAccount,
    DeliveryPartnerDocument,
    DeliveryPartnerProfile,
    DeliverySupportRequest,
    InventoryBatch,
    MasterOrder,
    MonthlyPack,
    MonthlyPackItem,
    Order,
    OrderItem,
    OrderPickingItem,
    OrderPickingTask,
    OTPVerification,
    Payment,
    PickerProfile,
    Product,
    ProductBarcode,
    Referral,
    SearchAlias,
    Settlement,
    ShopkeeperBankAccount,
    ShopkeeperDocument,
    ShopkeeperProfile,
    ShopProduct,
    Wallet,
    WalletTransaction,
    Shop,
)


# =========================================================
# AMEXA BUSINESS RULES
# Later admin settings / database config me move kar sakte hain.
# =========================================================

DELIVERY_FEE_PER_SHOP = Decimal("20.00")
PLATFORM_FEE_PER_SHOP = Decimal("5.00")
DELIVERY_PARTNER_PAYOUT_PER_SHOP = Decimal("15.00")
DELIVERY_ASSIGNMENT_RADIUS_KM = 5.0
RIDER_LOCATION_FRESH_MINUTES = 5
SHOP_COMMISSION_RATE = Decimal("0.05")
TAX_RATE = Decimal("0.00")


# =========================================================
# AMEXA ADMIN CONTROL CENTER
# Read-only operational dashboard; all changes still use
# Django Admin's protected model pages.
# =========================================================

@staff_member_required(login_url="admin:login")
def admin_control_center_view(request):
    user_model = get_user_model()
    now = timezone.now()
    today = timezone.localdate()

    today_start = timezone.make_aware(
        datetime.combine(today, time.min),
        timezone.get_current_timezone(),
    )
    tomorrow_start = today_start + timedelta(days=1)

    completed_orders = MasterOrder.objects.filter(status="Completed")
    today_orders = MasterOrder.objects.filter(
        created_at__gte=today_start,
        created_at__lt=tomorrow_start,
    )

    total_revenue = completed_orders.aggregate(
        value=Sum("total_amount")
    )["value"] or Decimal("0.00")
    today_revenue = completed_orders.filter(
        updated_at__gte=today_start,
        updated_at__lt=tomorrow_start,
    ).aggregate(value=Sum("total_amount"))["value"] or Decimal("0.00")

    order_statuses = []
    for status, label in Order.STATUS_CHOICES:
        order_statuses.append(
            {
                "status": status,
                "label": label,
                "count": Order.objects.filter(status=status).count(),
            }
        )

    order_chart = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_start = timezone.make_aware(
            datetime.combine(day, time.min),
            timezone.get_current_timezone(),
        )
        day_end = day_start + timedelta(days=1)
        order_chart.append(
            {
                "label": day.strftime("%a"),
                "date": day.strftime("%d %b"),
                "count": MasterOrder.objects.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end,
                ).count(),
            }
        )

    chart_max = max(
        (point["count"] for point in order_chart),
        default=1,
    ) or 1
    for point in order_chart:
        point["height"] = max(8, round(point["count"] * 100 / chart_max))

    pending_profiles_query = DeliveryPartnerProfile.objects.filter(
        verification_status__in=["PENDING", "UNDER_REVIEW"]
    ).select_related("user")

    open_support_query = DeliverySupportRequest.objects.filter(
        status__in=["Open", "In Review"]
    )

    context = {
        "generated_at": now,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "total_orders": MasterOrder.objects.count(),
        "today_orders": today_orders.count(),
        "pending_orders": Order.objects.filter(
            status__in=["Pending", "Confirmed", "Preparing"]
        ).count(),
        "active_shops": Shop.objects.filter(is_active=True).count(),
        "inactive_shops": Shop.objects.filter(is_active=False).count(),
        "total_customers": user_model.objects.filter(
            role="CUSTOMER"
        ).count(),
        "online_riders": user_model.objects.filter(
            role="DELIVERY",
            is_active_delivery=True,
            is_active=True,
        ).count(),
        "approved_riders": DeliveryPartnerProfile.objects.filter(
            verification_status="APPROVED"
        ).count(),
        "pending_verifications": pending_profiles_query.count(),
        "low_stock_products": Product.objects.filter(
            is_active=True,
            stock_quantity__lte=5,
        ).count(),
        "open_support_count": open_support_query.count(),
        "pending_settlements": Settlement.objects.filter(
            status__in=["Pending", "Processing", "On Hold"]
        ).count(),
        "failed_payments": Payment.objects.filter(
            payment_status="Failed"
        ).count(),
        "order_statuses": order_statuses,
        "order_chart": order_chart,
        "recent_orders": Order.objects.select_related(
            "user",
            "shop",
        ).order_by("-created_at")[:8],
        "pending_profiles": pending_profiles_query[:6],
        "recent_support": open_support_query.select_related(
            "delivery_partner",
            "order",
        )[:5],
    }

    return render(
        request,
        "customer/admin_control_center.html",
        context,
    )


# =========================================================
# CART HELPERS
# =========================================================

def _get_or_create_cart(user):
    cart, created = Cart.objects.get_or_create(user=user)
    return cart


def _cart_context(request):
    cart = None
    item_count = 0

    if request.user.is_authenticated:
        cart = _get_or_create_cart(request.user)
        item_count = sum(item.quantity for item in cart.items.all())

    return {
        "cart": cart,
        "cart_count": item_count,
    }


def _group_cart_items_by_shop(items):
    """
    Cart items ko shop-wise group karta hai.
    Template me shop_groups use karke alag-alag shop ke products dikha sakte hain.
    """
    groups = {}

    for item in items:
        shop = item.product.shop

        if shop.pk not in groups:
            groups[shop.pk] = {
                "shop": shop,
                "items": [],
                "subtotal": Decimal("0.00"),
                "delivery_fee": DELIVERY_FEE_PER_SHOP,
                "platform_fee": PLATFORM_FEE_PER_SHOP,
            }

        groups[shop.pk]["items"].append(item)
        groups[shop.pk]["subtotal"] += item.quantity * item.price

    for group in groups.values():
        group["tax_amount"] = (
            group["subtotal"] * TAX_RATE
        ).quantize(Decimal("0.01"))

        group["total"] = (
            group["subtotal"]
            + group["delivery_fee"]
            + group["platform_fee"]
            + group["tax_amount"]
        )

    return list(groups.values())


def _cart_totals(items):
    groups = _group_cart_items_by_shop(items)

    subtotal = sum(
        (group["subtotal"] for group in groups),
        Decimal("0.00"),
    )

    delivery_fee = sum(
        (group["delivery_fee"] for group in groups),
        Decimal("0.00"),
    )

    platform_fee = sum(
        (group["platform_fee"] for group in groups),
        Decimal("0.00"),
    )

    tax_amount = sum(
        (group["tax_amount"] for group in groups),
        Decimal("0.00"),
    )

    total = subtotal + delivery_fee + platform_fee + tax_amount

    return {
        "shop_groups": groups,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "platform_fee": platform_fee,
        "tax_amount": tax_amount,
        "total": total,
        "shop_count": len(groups),
    }


# =========================================================
# COUPON HELPERS
# =========================================================

def _coupon_for_cart(request, subtotal):
    """
    Session me applied coupon code ko validate karke
    current discount return karta hai.
    """
    coupon_code = (
        request.session.get("applied_coupon_code", "")
        or ""
    ).strip().upper()

    coupon = None
    discount_amount = Decimal("0.00")
    coupon_error = ""

    if not coupon_code:
        return {
            "applied_coupon": None,
            "coupon_code": "",
            "discount_amount": discount_amount,
            "coupon_error": "",
        }

    coupon = (
        Coupon.objects
        .filter(code=coupon_code)
        .first()
    )

    if coupon is None:
        request.session.pop("applied_coupon_code", None)
        return {
            "applied_coupon": None,
            "coupon_code": "",
            "discount_amount": discount_amount,
            "coupon_error": "Coupon is no longer available.",
        }

    if not coupon.is_currently_valid:
        request.session.pop("applied_coupon_code", None)
        return {
            "applied_coupon": None,
            "coupon_code": "",
            "discount_amount": discount_amount,
            "coupon_error": "This coupon is expired or inactive.",
        }

    if not coupon.can_user_use(request.user):
        request.session.pop("applied_coupon_code", None)
        return {
            "applied_coupon": None,
            "coupon_code": "",
            "discount_amount": discount_amount,
            "coupon_error": "You have already used this coupon.",
        }

    if subtotal < coupon.minimum_order_amount:
        coupon_error = (
            f"Minimum order amount for {coupon.code} is "
            f"₹{coupon.minimum_order_amount}."
        )
        discount_amount = Decimal("0.00")
    else:
        discount_amount = coupon.calculate_discount(subtotal)

    return {
        "applied_coupon": coupon,
        "coupon_code": coupon.code,
        "discount_amount": discount_amount,
        "coupon_error": coupon_error,
    }


def _totals_with_coupon(request, items):
    totals = _cart_totals(items)

    coupon_data = _coupon_for_cart(
        request,
        totals["subtotal"],
    )

    before_discount_total = totals["total"]
    discount_amount = coupon_data["discount_amount"]

    payable_total = max(
        Decimal("0.00"),
        before_discount_total - discount_amount,
    )

    totals.update(
        coupon_data
    )

    totals["before_discount_total"] = before_discount_total
    totals["total"] = payable_total
    totals["payable_total"] = payable_total

    return totals


# =========================================================
# ORDER HELPERS
# =========================================================

def _short_random():
    return f"{random.randint(0, 9999):04d}"


def _build_order_number():
    return (
        f"AMX{timezone.now().strftime('%y%m%d%H%M%S')}"
        f"{_short_random()}"
    )


def _build_master_order_number():
    return (
        f"AMXM{timezone.now().strftime('%y%m%d%H%M%S')}"
        f"{_short_random()}"
    )


def _update_master_order_status(master_order):
    if not master_order:
        return

    statuses = list(
        master_order.shop_orders.values_list("status", flat=True)
    )

    if not statuses:
        return

    if all(status == "Cancelled" for status in statuses):
        new_status = "Cancelled"

    elif all(status == "Delivered" for status in statuses):
        new_status = "Completed"

    elif any(status == "Delivered" for status in statuses):
        new_status = "Partially Completed"

    elif any(
        status in {
            "Confirmed",
            "Preparing",
            "Out for Delivery",
        }
        for status in statuses
    ):
        new_status = "Confirmed"

    else:
        new_status = "Pending"

    if master_order.status != new_status:
        master_order.status = new_status
        master_order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


def _create_multi_shop_order_from_cart(
    user,
    address,
    cart,
    payment_method="COD",
    coupon=None,
    coin_discount=Decimal("0.00"),
):
    """
    One cart -> one MasterOrder -> separate shop Orders.
    Coupon discount is applied once at MasterOrder level and
    proportionally allocated across shop orders.
    """
    items = list(
        cart.items
        .select_related(
            "product",
            "product__shop",
        )
        .all()
    )

    if not items:
        raise ValueError("Cart is empty.")

    totals = _cart_totals(items)
    shop_groups = totals["shop_groups"]

    if not shop_groups:
        raise ValueError("No valid shop products found in cart.")

    discount_amount = Decimal("0.00")

    if coupon:
        if not coupon.is_currently_valid:
            raise ValueError("Coupon is expired or inactive.")

        if not coupon.can_user_use(user):
            raise ValueError("This coupon cannot be used again.")

        if totals["subtotal"] < coupon.minimum_order_amount:
            raise ValueError(
                f"Minimum order amount for {coupon.code} is "
                f"₹{coupon.minimum_order_amount}."
            )

        discount_amount = coupon.calculate_discount(
            totals["subtotal"]
        )

    coin_discount = max(
        Decimal("0.00"),
        Decimal(coin_discount or 0),
    )

    # Coins can discount product value only, never delivery/platform/tax.
    max_coin_discount = max(
        Decimal("0.00"),
        totals["subtotal"] - discount_amount,
    )
    coin_discount = min(
        coin_discount,
        max_coin_discount,
    )

    payable_total = max(
        Decimal("0.00"),
        totals["total"] - discount_amount - coin_discount,
    )

    with transaction.atomic():

        locked_products = {}

        for item in items:
            product = (
                Product.objects
                .select_for_update()
                .get(pk=item.product_id)
            )

            if not product.is_active:
                raise ValueError(
                    f"{product.name} is no longer available."
                )

            if product.stock_quantity < item.quantity:
                raise ValueError(
                    f"Only {product.stock_quantity} "
                    f"{product.name} available."
                )

            locked_products[product.pk] = product

        master_order = MasterOrder.objects.create(
            user=user,
            address=address,
            master_order_number=_build_master_order_number(),
            subtotal=totals["subtotal"],
            delivery_fee=totals["delivery_fee"],
            platform_fee=totals["platform_fee"],
            tax_amount=totals["tax_amount"],
            discount_amount=discount_amount + coin_discount,
            coins_redeemed=int(coin_discount),
            coin_discount_amount=coin_discount,
            total_amount=payable_total,
            status="Pending",
        )

        payment_status = (
            "Pending"
            if payment_method == "COD"
            else "Processing"
        )

        Payment.objects.create(
            master_order=master_order,
            user=user,
            payment_method=payment_method,
            payment_status=payment_status,
            amount=payable_total,
        )

        created_orders = []

        # Coupon + AMEXA Coins discount ko shop-wise proportionally allocate karna.
        total_order_discount = discount_amount + coin_discount
        allocated_discount = Decimal("0.00")
        group_discounts = []

        for index, group in enumerate(shop_groups):
            if total_order_discount <= 0:
                group_discount = Decimal("0.00")

            elif index == len(shop_groups) - 1:
                group_discount = (
                    total_order_discount - allocated_discount
                )

            elif totals["subtotal"] > 0:
                group_discount = (
                    total_order_discount
                    * group["subtotal"]
                    / totals["subtotal"]
                ).quantize(Decimal("0.01"))
                allocated_discount += group_discount

            else:
                group_discount = Decimal("0.00")

            group_discounts.append(group_discount)

        for group, group_discount in zip(
            shop_groups,
            group_discounts,
        ):
            shop = group["shop"]

            shop_total_after_discount = max(
                Decimal("0.00"),
                group["total"] - group_discount,
            )

            order = Order.objects.create(
                master_order=master_order,
                user=user,
                address=address,
                shop=shop,
                order_number=_build_order_number(),
                payment_method=(
                    "COD"
                    if payment_method == "COD"
                    else "ONLINE"
                ),
                payment_status=payment_status,
                status="Pending",
                total_amount=shop_total_after_discount,
                delivery_fee=group["delivery_fee"],
            )

            order.create_status_history(
                "Pending",
                "Order placed",
            )

            for cart_item in group["items"]:
                product = locked_products[cart_item.product_id]

                product.stock_quantity -= cart_item.quantity
                product.save(
                    update_fields=["stock_quantity"]
                )

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    quantity=cart_item.quantity,
                    price=cart_item.price,
                )

            product_amount = group["subtotal"]

            shop_commission = (
                product_amount * SHOP_COMMISSION_RATE
            ).quantize(Decimal("0.01"))

            shop_payable = product_amount - shop_commission

            delivery_partner_payout = min(
                group["delivery_fee"],
                DELIVERY_PARTNER_PAYOUT_PER_SHOP,
            )

            # Coupon ko platform-funded discount treat kar rahe hain.
            amexa_earning = (
                shop_commission
                + group["platform_fee"]
                + (
                    group["delivery_fee"]
                    - delivery_partner_payout
                )
                - group_discount
            )

            Settlement.objects.create(
                order=order,
                shop=shop,
                product_amount=product_amount,
                shop_commission=shop_commission,
                shop_payable=shop_payable,
                delivery_fee=group["delivery_fee"],
                delivery_partner_payout=delivery_partner_payout,
                platform_fee=group["platform_fee"],
                tax_amount=group["tax_amount"],
                amexa_earning=amexa_earning,
                status="Pending",
            )

            created_orders.append(order)

        if coupon and discount_amount > 0:
            CouponUsage.objects.create(
                coupon=coupon,
                user=user,
                master_order=master_order,
                discount_amount=discount_amount,
            )

        # Coins and order creation are ONE database transaction.
        # If redemption fails, MasterOrder/Orders/stock changes roll back too.
        if coin_discount > 0:
            redeem_coins(
                user,
                int(coin_discount),
                master_order=master_order,
                description=(
                    f"Used on order "
                    f"{master_order.master_order_number}"
                ),
                skip_expiry=True,
            )

        cart.items.all().delete()

        if cart.shop_id is not None:
            cart.shop = None
            cart.save(
                update_fields=[
                    "shop",
                    "updated_at",
                ]
            )

    return master_order, created_orders



# =========================================================
# SMART SEARCH HELPERS
# SEARCH ALIASES + MULTI-WORD EXPANSION
# =========================================================

def _smart_search_terms(query):
    """
    User query ko SearchAlias ke through expand karta hai.
    Example:
        chappal -> chappal, slipper, sandal, footwear
    """
    query = (query or "").strip()

    if not query:
        return []

    terms = [query]
    normalized_query = " ".join(query.lower().split())

    aliases = SearchAlias.objects.filter(
        is_active=True
    )

    for alias in aliases:
        keyword = " ".join(
            (alias.keyword or "").lower().split()
        )

        if not keyword:
            continue

        if (
            keyword == normalized_query
            or keyword in normalized_query
            or normalized_query in keyword
        ):
            mapped_text = (alias.mapped_text or "").strip()

            if mapped_text:
                terms.extend(mapped_text.split())

    unique_terms = []
    seen = set()

    for term in terms:
        cleaned = (term or "").strip()

        if not cleaned:
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            unique_terms.append(cleaned)

    return unique_terms


def _product_search_q(query):
    """
    Product, shop, category aur brand par expanded smart search Q banata hai.
    """
    search_q = Q()

    for term in _smart_search_terms(query):
        search_q |= (
            Q(name__icontains=term)
            | Q(description__icontains=term)
            | Q(shop__name__icontains=term)
            | Q(category__name__icontains=term)
            | Q(brand__name__icontains=term)
        )

    return search_q


# =========================================================
# HOME
# 5 KM SERVICE RADIUS + SHOP-FIRST EXPERIENCE
# =========================================================

def home(request):
    query = request.GET.get("q", "").strip()
    selected_shop_slug = request.GET.get("shop", "").strip()

    SERVICE_RADIUS_KM = 5.0

    # =====================================================
    # 1) CUSTOMER LOCATION
    # Priority:
    # browser GPS -> session -> saved default address
    # =====================================================

    user_lat = None
    user_lon = None
    location_source = None

    try:
        if request.GET.get("lat") and request.GET.get("lon"):
            user_lat = float(request.GET.get("lat"))
            user_lon = float(request.GET.get("lon"))

            request.session["customer_lat"] = user_lat
            request.session["customer_lon"] = user_lon
            request.session.modified = True

            location_source = "live"

        else:
            session_lat = request.session.get("customer_lat")
            session_lon = request.session.get("customer_lon")

            if session_lat is not None and session_lon is not None:
                user_lat = float(session_lat)
                user_lon = float(session_lon)
                location_source = "session"

    except (TypeError, ValueError):
        user_lat = None
        user_lon = None
        location_source = None

    # =====================================================
    # SAVED DEFAULT ADDRESS
    # =====================================================

    default_address = None

    if request.user.is_authenticated:
        default_address = (
            request.user.addresses
            .filter(is_default=True)
            .first()
        )

        if (
            user_lat is None
            and user_lon is None
            and default_address
        ):
            try:
                default_lat = float(default_address.latitude or 0)
                default_lon = float(default_address.longitude or 0)
            except (TypeError, ValueError):
                default_lat = 0
                default_lon = 0

            if default_lat != 0 and default_lon != 0:
                user_lat = default_lat
                user_lon = default_lon
                location_source = "default_address"

    location_ready = (
        user_lat is not None
        and user_lon is not None
    )

    # =====================================================
    # HOME LOCATION DISPLAY
    # =====================================================

    location_title = "Your Current Location"
    location_subtitle = "Tap to select live location"

    session_location_address = (
        request.session.get(
            "customer_location_address",
            ""
        )
        or ""
    ).strip()

    matches_default_address = False

    if (
        location_ready
        and default_address
    ):
        try:
            default_lat = float(default_address.latitude or 0)
            default_lon = float(default_address.longitude or 0)

            if default_lat != 0 and default_lon != 0:
                matches_default_address = (
                    abs(user_lat - default_lat) < 0.00001
                    and
                    abs(user_lon - default_lon) < 0.00001
                )

        except (TypeError, ValueError):
            matches_default_address = False

    if (
        location_ready
        and default_address
        and matches_default_address
    ):
        location_title = default_address.address_type
        location_subtitle = (
            f"{default_address.address_line}, "
            f"{default_address.city}"
        )

    elif (
        location_ready
        and session_location_address
    ):
        location_title = "Delivery Location"
        location_subtitle = session_location_address

    elif location_ready:
        location_title = "Current Location"
        location_subtitle = (
            "Live location selected · Tap to change"
        )

    elif default_address:
        location_title = default_address.address_type
        location_subtitle = (
            f"{default_address.address_line}, "
            f"{default_address.city}"
        )

    # =====================================================
    # 2) ONLY SHOPS INSIDE 5 KM
    # =====================================================

    nearby_shops = []

    if location_ready:
        active_shops = Shop.objects.filter(
            is_active=True
        )

        for shop in active_shops:
            distance = shop.distance_to(
                user_lat,
                user_lon,
            )

            if distance <= SERVICE_RADIUS_KM:
                shop.distance_km = distance
                nearby_shops.append(shop)

        nearby_shops.sort(
            key=lambda shop: (
                shop.distance_km,
                -float(shop.rating or 0),
            )
        )

    nearby_shops = nearby_shops[:8]

    # =====================================================
    # 3) SELECTED SHOP
    # =====================================================

    if not selected_shop_slug:
        selected_shop_slug = request.session.get(
            "selected_shop_slug",
            ""
        )

    selected_shop = None

    if selected_shop_slug:
        for shop in nearby_shops:
            if shop.slug == selected_shop_slug:
                selected_shop = shop
                break

    if selected_shop is None and nearby_shops:
        selected_shop = nearby_shops[0]

    if selected_shop:
        request.session["selected_shop_slug"] = (
            selected_shop.slug
        )
    else:
        request.session.pop(
            "selected_shop_slug",
            None,
        )

    # =====================================================
    # 4) CATEGORIES
    # =====================================================

    categories = (
        Category.objects
        .filter(is_active=True)
        .order_by("name")[:8]
    )

    # =====================================================
    # 5) PRODUCT BASE QUERY
    # =====================================================

    base_products = (
        Product.objects
        .filter(
            is_active=True,
            stock_quantity__gt=0,
            shop__is_active=True,
        )
        .select_related(
            "shop",
            "category",
            "brand",
        )
    )

    if selected_shop:
        base_products = base_products.filter(
            shop=selected_shop
        )

    elif location_ready and nearby_shops:
        nearby_shop_ids = [
            shop.id
            for shop in nearby_shops
        ]

        base_products = base_products.filter(
            shop_id__in=nearby_shop_ids
        )

    else:
        base_products = base_products.none()

    if query:
        base_products = base_products.filter(
            _product_search_q(query)
        ).distinct()

    # =====================================================
    # 6) SELECTED SHOP PRODUCTS
    # =====================================================

    selected_shop_products = (
        base_products
        .order_by("-created_at")[:12]
    )

    top_products = selected_shop_products

    # =====================================================
    # 7) DEALS
    # =====================================================

    deal_products = []

    for product in base_products.order_by("-created_at")[:40]:
        if product.mrp and product.price < product.mrp:
            deal_products.append(product)

        if len(deal_products) >= 10:
            break

    # =====================================================
    # 8) BRANDS
    # =====================================================

    if selected_shop:
        brands = (
            Brand.objects
            .filter(
                is_active=True,
                products__shop=selected_shop,
                products__is_active=True,
                products__stock_quantity__gt=0,
            )
            .distinct()
            .order_by("name")[:12]
        )

    elif location_ready and nearby_shops:
        nearby_shop_ids = [
            shop.id
            for shop in nearby_shops
        ]

        brands = (
            Brand.objects
            .filter(
                is_active=True,
                products__shop_id__in=nearby_shop_ids,
                products__is_active=True,
                products__stock_quantity__gt=0,
            )
            .distinct()
            .order_by("name")[:12]
        )

    else:
        brands = Brand.objects.none()

    # =====================================================
    # 9) MONTHLY ESSENTIAL SUGGESTIONS
    # =====================================================

    monthly_pack_products = (
        base_products
        .order_by("name")[:8]
    )

    # Backward compatibility
    shops = nearby_shops
    products = top_products

    # =====================================================
    # ADMIN-MANAGED HOME BANNERS
    # =====================================================
    banners = (
        Banner.objects
        .filter(is_active=True)
        .order_by("display_order", "-created_at")
    )

    # =====================================================
    # 10) AMEXA WALLET / COINS
    # =====================================================
    wallet = None
    coin_balance = 0

    if request.user.is_authenticated:
        wallet, wallet_created = Wallet.objects.get_or_create(
            user=request.user
        )
        coin_balance = wallet.coin_balance

    context = {
        "banners": banners,
        "categories": categories,
        "shops": shops,
        "products": products,
        "query": query,

        "nearby_shops": nearby_shops,
        "selected_shop": selected_shop,
        "selected_shop_products": selected_shop_products,
        "top_products": top_products,
        "deal_products": deal_products,
        "brands": brands,
        "monthly_pack_products": monthly_pack_products,

        "wallet": wallet,
        "coin_balance": coin_balance,

        "location_ready": location_ready,
        "customer_lat": user_lat,
        "customer_lon": user_lon,
        "default_address": default_address,
        "location_source": location_source,
        "location_title": location_title,
        "location_subtitle": location_subtitle,
        "service_radius_km": SERVICE_RADIUS_KM,
    }

    context.update(
        _cart_context(request)
    )

    return render(
        request,
        "customer/home.html",
        context,
    )



# =========================================================
# SEARCH RESULTS
# FLIPKART-STYLE: NEARBY STORES + FILTERS + STORE GROUPS
# =========================================================

def search_results_view(request):
    query = (request.GET.get("q", "") or "").strip()
    category_slug = (request.GET.get("category", "") or "").strip()
    brand_slug = (request.GET.get("brand", "") or "").strip()
    shop_slug = (request.GET.get("shop", "") or "").strip()
    sort = (request.GET.get("sort", "relevance") or "relevance").strip()

    try:
        min_price = Decimal(request.GET.get("min_price", "") or "0")
    except Exception:
        min_price = Decimal("0")

    try:
        max_price_raw = (request.GET.get("max_price", "") or "").strip()
        max_price = Decimal(max_price_raw) if max_price_raw else None
    except Exception:
        max_price = None

    SERVICE_RADIUS_KM = 5.0
    user_lat = None
    user_lon = None

    try:
        session_lat = request.session.get("customer_lat")
        session_lon = request.session.get("customer_lon")
        if session_lat is not None and session_lon is not None:
            user_lat = float(session_lat)
            user_lon = float(session_lon)
    except (TypeError, ValueError):
        user_lat = None
        user_lon = None

    if user_lat is None and request.user.is_authenticated:
        default_address = (
            request.user.addresses
            .filter(is_default=True)
            .first()
        )
        if default_address:
            try:
                lat = float(default_address.latitude or 0)
                lon = float(default_address.longitude or 0)
                if lat != 0 and lon != 0:
                    user_lat = lat
                    user_lon = lon
            except (TypeError, ValueError):
                pass

    location_ready = user_lat is not None and user_lon is not None
    nearby_shops = []

    if location_ready:
        for shop in Shop.objects.filter(is_active=True):
            distance = shop.distance_to(user_lat, user_lon)
            if distance <= SERVICE_RADIUS_KM:
                shop.distance_km = distance
                nearby_shops.append(shop)

        nearby_shops.sort(
            key=lambda item: (
                item.distance_km,
                -float(item.rating or 0),
            )
        )

    nearby_shop_ids = [shop.id for shop in nearby_shops]

    products = (
        Product.objects
        .filter(
            is_active=True,
            stock_quantity__gt=0,
            shop__is_active=True,
        )
        .select_related("shop", "category", "brand")
    )

    if location_ready:
        products = products.filter(shop_id__in=nearby_shop_ids)
    else:
        products = products.none()

    if query:
        products = products.filter(
            _product_search_q(query)
        ).distinct()

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if brand_slug:
        products = products.filter(brand__slug=brand_slug)

    if shop_slug:
        products = products.filter(shop__slug=shop_slug)

    if min_price > 0:
        products = products.filter(price__gte=min_price)

    if max_price is not None:
        products = products.filter(price__lte=max_price)

    if sort == "price_low":
        products = products.order_by("price", "name")
    elif sort == "price_high":
        products = products.order_by("-price", "name")
    elif sort == "newest":
        products = products.order_by("-created_at")
    else:
        products = products.order_by("shop__name", "name")

    products = list(products)

    store_groups_map = {}
    for product in products:
        shop = product.shop
        if shop.id not in store_groups_map:
            distance = None
            for nearby_shop in nearby_shops:
                if nearby_shop.id == shop.id:
                    distance = nearby_shop.distance_km
                    break
            store_groups_map[shop.id] = {
                "shop": shop,
                "distance_km": distance,
                "products": [],
            }
        store_groups_map[shop.id]["products"].append(product)

    store_groups = list(store_groups_map.values())
    store_groups.sort(
        key=lambda group: (
            group["distance_km"] if group["distance_km"] is not None else 999999,
            group["shop"].name.lower(),
        )
    )

    categories = (
        Category.objects
        .filter(
            is_active=True,
            products__shop_id__in=nearby_shop_ids,
            products__is_active=True,
            products__stock_quantity__gt=0,
        )
        .distinct()
        .order_by("name")
        if nearby_shop_ids
        else Category.objects.none()
    )

    brands = (
        Brand.objects
        .filter(
            is_active=True,
            products__shop_id__in=nearby_shop_ids,
            products__is_active=True,
            products__stock_quantity__gt=0,
        )
        .distinct()
        .order_by("name")
        if nearby_shop_ids
        else Brand.objects.none()
    )

    context = {
        "query": query,
        "products": products,
        "product_count": len(products),
        "store_groups": store_groups,
        "nearby_shops": nearby_shops,
        "categories": categories,
        "brands": brands,
        "selected_category": category_slug,
        "selected_brand": brand_slug,
        "selected_shop_slug": shop_slug,
        "min_price": min_price if min_price > 0 else "",
        "max_price": max_price if max_price is not None else "",
        "sort": sort,
        "location_ready": location_ready,
        "service_radius_km": SERVICE_RADIUS_KM,
    }
    context.update(_cart_context(request))

    return render(
        request,
        "customer/search_results.html",
        context,
    )


# =========================================================
# OTP HELPER
# =========================================================

def _create_otp_for_phone(phone, user):
    code = f"{random.randint(0, 999999):06d}"

    expires_at = (
        timezone.now()
        + timedelta(minutes=5)
    )

    OTPVerification.objects.filter(
        user=user,
        phone=phone,
        is_used=False,
    ).update(
        is_used=True
    )

    otp = OTPVerification.objects.create(
        user=user,
        phone=phone,
        code=code,
        expires_at=expires_at,
    )

    return otp


# =========================================================
# LOGIN - NAME + MOBILE + OTP
# NO REGISTER PAGE
# =========================================================

def _referrer_from_link_code(code):
    code = (code or "").strip().upper()
    if not code.startswith("AMX"):
        return None

    user_id_text = code[3:]
    if not user_id_text.isdigit():
        return None

    return (
        get_user_model()
        .objects
        .filter(pk=int(user_id_text))
        .first()
    )


def _login_destination(user):
    """Send every AMEXA account to its own app after login."""
    role = getattr(user, "role", "CUSTOMER")

    if user.is_superuser or (user.is_staff and role == "ADMIN"):
        return "admin_control_center"
    if role == "SHOPKEEPER":
        return "shopkeeper_dashboard"
    if role == "PICKER":
        return "picker_dashboard"
    if role == "DELIVERY":
        return "delivery_dashboard"
    return "home"


def login_view(request):

    # Referral is captured silently from URL.
    # Example: /login/?ref=AMX000123
    incoming_ref = (
        request.GET.get("ref")
        or ""
    ).strip().upper()

    if incoming_ref:
        request.session["pending_referral_code"] = incoming_ref

    if request.GET.get("change") == "1":
        request.session.pop("otp_phone", None)
        request.session.pop("otp_name", None)
        request.session.pop("otp_user_id", None)
        request.session.pop("otp_user_created", None)
        return redirect("login")

    if request.user.is_authenticated:
        return redirect(_login_destination(request.user))

    session_phone = request.session.get(
        "otp_phone",
        ""
    )

    session_name = request.session.get(
        "otp_name",
        ""
    )

    otp_sent = bool(session_phone)

    if request.method == "POST":

        post_data = request.POST.copy()

        if not post_data.get("phone") and session_phone:
            post_data["phone"] = session_phone

        if not post_data.get("name") and session_name:
            post_data["name"] = session_name

        form = LoginForm(post_data)

        if form.is_valid():

            phone = form.cleaned_data["phone"]

            name = (
                form.cleaned_data.get("name")
                or session_name
                or "Customer"
            )

            otp_code = (
                form.cleaned_data.get("otp_code")
                or ""
            ).strip()

            User = get_user_model()

            # IMPORTANT:
            # Old development data can contain duplicate CustomerUser rows
            # for the same phone number. get_or_create() internally calls
            # get(), which crashes with MultipleObjectsReturned.
            #
            # So AMEXA login safely reuses the oldest matching account.
            # A new account is created only when this phone does not exist.
            existing_users = (
                User.objects
                .filter(phone=phone)
                .order_by("pk")
            )

            user = existing_users.first()
            created = False

            if user is None:
                user = User.objects.create(
                    phone=phone,
                    name=name,
                    email=f"{phone}@amexa.local",
                )
                created = True

            # Preserve whether this account was first created
            # during the OTP request step.
            if not otp_code:
                request.session["otp_user_created"] = bool(created)

            if name and user.name != name:
                user.name = name
                user.save(
                    update_fields=["name"]
                )

            if otp_code:

                otp = (
                    OTPVerification
                    .objects
                    .filter(
                        user=user,
                        phone=phone,
                        is_used=False,
                    )
                    .order_by("-created_at")
                    .first()
                )

                if not otp:
                    form.add_error(
                        "otp_code",
                        "Please request a new OTP."
                    )

                elif not otp.is_valid():
                    form.add_error(
                        "otp_code",
                        "OTP expired. Please request a new OTP."
                    )

                elif otp.code != otp_code:
                    otp.attempts += 1
                    otp.save(
                        update_fields=["attempts"]
                    )

                    form.add_error(
                        "otp_code",
                        "Incorrect OTP."
                    )

                else:
                    otp.is_used = True
                    otp.save(
                        update_fields=["is_used"]
                    )

                    # Attach referral only after successful OTP,
                    # and only when this is a genuinely new user.
                    pending_ref = (
                        request.session.get(
                            "pending_referral_code",
                            ""
                        )
                        or ""
                    ).strip().upper()

                    was_created = bool(
                        request.session.get(
                            "otp_user_created",
                            False
                        )
                    )

                    if (
                        was_created
                        and pending_ref
                        and not Referral.objects.filter(
                            referred_user=user
                        ).exists()
                    ):
                        referrer = _referrer_from_link_code(
                            pending_ref
                        )

                        if (
                            referrer is not None
                            and referrer.pk != user.pk
                        ):
                            Referral.objects.create(
                                referrer=referrer,
                                referred_user=user,
                                referral_code=pending_ref,
                                reward_coins=50,
                            )

                    user.backend = (
                        "django.contrib.auth.backends."
                        "ModelBackend"
                    )

                    login(
                        request,
                        user
                    )

                    request.session.pop("otp_phone", None)
                    request.session.pop("otp_name", None)
                    request.session.pop("otp_user_id", None)
                    request.session.pop("otp_user_created", None)
                    request.session.pop("pending_referral_code", None)

                    messages.success(
                        request,
                        f"Welcome to AMEXA, {user.name}!"
                    )

                    return redirect(_login_destination(user))

            else:
                otp = _create_otp_for_phone(
                    phone,
                    user
                )

                request.session["otp_phone"] = phone
                request.session["otp_name"] = name
                request.session["otp_user_id"] = user.pk
                request.session.set_expiry(600)

                messages.success(
                    request,
                    f"OTP sent to {phone}. "
                    f"Demo OTP: {otp.code}"
                )

                return redirect("login")

    else:
        initial = {}

        if session_phone:
            initial["phone"] = session_phone

        if session_name:
            initial["name"] = session_name

        form = LoginForm(
            initial=initial
        )

    context = {
        "form": form,
        "otp_sent": otp_sent,
        "otp_phone": session_phone,
        "otp_name": session_name,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/login.html",
        context,
    )


# =========================================================
# LOGOUT
# =========================================================

@login_required
def logout_view(request):
    logout(request)

    messages.info(
        request,
        "You have been logged out."
    )

    return redirect("login")


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile_view(request):
    addresses = request.user.addresses.all()[:3]

    wallet, created = Wallet.objects.get_or_create(
        user=request.user
    )

    wallet_transactions = (
        WalletTransaction.objects
        .filter(wallet=wallet)
        .select_related("master_order")
        .order_by("-created_at")[:10]
    )

    context = {
        "addresses": addresses,
        "wallet": wallet,
        "coin_balance": wallet.coin_balance,
        "wallet_transactions": wallet_transactions,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/profile.html",
        context,
    )


# =========================================================
# ADDRESSES
# =========================================================

@login_required
def addresses_view(request):
    addresses = request.user.addresses.all()

    context = {
        "addresses": addresses,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/addresses.html",
        context,
    )


@login_required
def add_address_view(request):
    form = AddressForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user

        if not request.user.addresses.exists():
            address.is_default = True

        address.save()

        if address.is_default:
            request.user.addresses.exclude(
                pk=address.pk
            ).update(
                is_default=False
            )

        messages.success(
            request,
            "Address added successfully."
        )

        return redirect("addresses")

    context = {
        "form": form,
        "title": "Add Address",
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/address_form.html",
        context,
    )


@login_required
def edit_address_view(request, pk):
    address = get_object_or_404(
        Address,
        pk=pk,
        user=request.user,
    )

    form = AddressForm(
        request.POST or None,
        instance=address,
    )

    if request.method == "POST" and form.is_valid():
        address = form.save()

        if address.is_default:
            request.user.addresses.exclude(
                pk=address.pk
            ).update(
                is_default=False
            )

        messages.success(
            request,
            "Address updated successfully."
        )

        return redirect("addresses")

    context = {
        "form": form,
        "title": "Edit Address",
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/address_form.html",
        context,
    )


# =========================================================
# SHOPS
# =========================================================

def nearby_shops_view(request):
    query = request.GET.get("q", "").strip()

    shops = Shop.objects.filter(
        is_active=True
    )

    if query:
        shops = shops.filter(
            Q(name__icontains=query)
            |
            Q(address__icontains=query)
        )

    shops = shops[:20]

    context = {
        "shops": shops,
        "query": query,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/nearby_shops.html",
        context,
    )


def shop_detail_view(request, slug):
    shop = get_object_or_404(
        Shop,
        slug=slug,
        is_active=True,
    )

    query = request.GET.get("q", "").strip()

    products = (
        shop.products
        .filter(is_active=True)
        .select_related(
            "category",
            "brand",
        )
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            |
            Q(description__icontains=query)
            |
            Q(brand__name__icontains=query)
        )

    context = {
        "shop": shop,
        "products": products,
        "query": query,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/shop_detail.html",
        context,
    )


# =========================================================
# CATEGORIES
# SELECTED / NEARBY STORE BASED
# =========================================================

def categories_view(request):

    query = request.GET.get(
        "q",
        ""
    ).strip()

    selected_shop_slug = request.session.get(
        "selected_shop_slug",
        ""
    )

    selected_shop = None

    if selected_shop_slug:

        selected_shop = (
            Shop.objects
            .filter(
                slug=selected_shop_slug,
                is_active=True,
            )
            .first()
        )

    # -----------------------------------------------------
    # IF STORE SELECTED:
    # SHOW ONLY CATEGORIES AVAILABLE IN THAT STORE
    # -----------------------------------------------------

    if selected_shop:

        categories = (
            Category.objects
            .filter(
                is_active=True,
                products__shop=selected_shop,
                products__is_active=True,
                products__stock_quantity__gt=0,
            )
            .distinct()
            .order_by("name")
        )

    else:

        categories = (
            Category.objects
            .filter(
                is_active=True
            )
            .order_by("name")
        )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if query:

        categories = categories.filter(
            name__icontains=query
        )

    # -----------------------------------------------------
    # PRODUCT COUNT PER CATEGORY
    # -----------------------------------------------------

    category_list = []

    for category in categories:

        if selected_shop:

            product_count = (
                Product.objects
                .filter(
                    category=category,
                    shop=selected_shop,
                    is_active=True,
                    stock_quantity__gt=0,
                )
                .count()
            )

        else:

            product_count = (
                Product.objects
                .filter(
                    category=category,
                    is_active=True,
                    stock_quantity__gt=0,
                )
                .count()
            )

        category.product_count = product_count
        category_list.append(category)

    context = {
        "categories": category_list,
        "query": query,
        "selected_shop": selected_shop,
    }

    context.update(
        _cart_context(request)
    )

    return render(
        request,
        "customer/categories.html",
        context,
    )


def category_products_view(request, slug):
    category = get_object_or_404(
        Category,
        slug=slug,
        is_active=True,
    )

    query = request.GET.get(
        "q",
        ""
    ).strip()

    selected_shop_slug = request.session.get(
        "selected_shop_slug",
        ""
    )

    selected_shop = None

    if selected_shop_slug:
        selected_shop = (
            Shop.objects
            .filter(
                slug=selected_shop_slug,
                is_active=True,
            )
            .first()
        )

    products = (
        Product.objects
        .filter(
            category=category,
            is_active=True,
            stock_quantity__gt=0,
            shop__is_active=True,
        )
        .select_related(
            "shop",
            "category",
            "brand",
        )
    )

    # Selected store ko priority / strict filter
    if selected_shop:
        products = products.filter(
            shop=selected_shop
        )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            |
            Q(description__icontains=query)
            |
            Q(shop__name__icontains=query)
            |
            Q(brand__name__icontains=query)
        ).distinct()

    products = products.order_by(
        "price",
        "name",
    )

    context = {
        "category": category,
        "products": products,
        "query": query,
        "selected_shop": selected_shop,
    }

    context.update(
        _cart_context(request)
    )

    return render(
        request,
        "customer/category_products.html",
        context,
    )


# =========================================================
# PRODUCT DETAIL
# =========================================================

def product_detail_view(request, slug):
    product = get_object_or_404(
        Product.objects.select_related(
            "shop",
            "category",
            "brand",
        ),
        slug=slug,
        is_active=True,
    )

    related_products = (
        Product.objects
        .filter(
            category=product.category,
            is_active=True,
        )
        .exclude(pk=product.pk)
        .select_related(
            "shop",
            "category",
            "brand",
        )[:8]
    )

    context = {
        "product": product,
        "related_products": related_products,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/product_detail.html",
        context,
    )


# =========================================================
# CART
# =========================================================

@login_required
def cart_view(request):
    cart = _get_or_create_cart(
        request.user
    )

    items = list(
        cart.items
        .select_related(
            "product",
            "product__shop",
            "product__brand",
        )
        .all()
    )

    totals = _totals_with_coupon(
        request,
        items,
    )

    context = {
        "cart": cart,
        "items": items,
        **totals,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/cart.html",
        context,
    )


# =========================================================
# ADD PRODUCT TO CART
# MULTI-SHOP ENABLED
# =========================================================

@login_required
def cart_add_view(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("shop"),
        pk=product_id,
        is_active=True,
    )

    cart = _get_or_create_cart(
        request.user
    )

    if product.stock_quantity <= 0:
        messages.error(
            request,
            "This product is out of stock."
        )

        return redirect(
            "product_detail",
            slug=product.slug,
        )

    try:
        requested_quantity = int(
            request.POST.get(
                "quantity",
                1
            )
        )
    except (TypeError, ValueError):
        requested_quantity = 1

    if requested_quantity < 1:
        requested_quantity = 1

    item = (
        cart.items
        .filter(product=product)
        .first()
    )

    if item is None:
        quantity_to_add = min(
            requested_quantity,
            product.stock_quantity,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity_to_add,
            price=product.price,
        )

        messages.success(
            request,
            f"{product.name} from "
            f"{product.shop.name} added to cart."
        )

    else:
        new_quantity = (
            item.quantity
            + requested_quantity
        )

        if new_quantity > product.stock_quantity:
            new_quantity = product.stock_quantity

            messages.warning(
                request,
                "Maximum available stock added."
            )
        else:
            messages.success(
                request,
                f"{product.name} quantity updated."
            )

        item.quantity = new_quantity
        item.price = product.price

        item.save(
            update_fields=[
                "quantity",
                "price",
                "updated_at",
            ]
        )

    if cart.shop_id is not None:
        cart.shop = None
        cart.save(
            update_fields=[
                "shop",
                "updated_at",
            ]
        )

    if request.POST.get("buy_now") == "1":
        return redirect("checkout")

    next_url = request.POST.get("next", "").strip()

    if next_url.startswith("/"):
        return redirect(next_url)

    return redirect("cart")


# =========================================================
# UPDATE CART
# =========================================================

@login_required
def cart_update_view(request, item_id):
    item = get_object_or_404(
        CartItem,
        pk=item_id,
        cart__user=request.user,
    )

    try:
        quantity = int(
            request.POST.get(
                "quantity",
                1
            )
        )
    except (TypeError, ValueError):
        quantity = 1

    if quantity <= 0:
        item.delete()

        messages.info(
            request,
            "Item removed from cart."
        )

        return redirect("cart")

    if quantity > item.product.stock_quantity:
        quantity = item.product.stock_quantity

        messages.warning(
            request,
            "Maximum available stock selected."
        )

    if quantity <= 0:
        item.delete()

        messages.info(
            request,
            "Product is no longer in stock and was removed."
        )

        return redirect("cart")

    item.quantity = quantity
    item.price = item.product.price

    item.save(
        update_fields=[
            "quantity",
            "price",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Cart updated."
    )

    return redirect("cart")


# =========================================================
# REMOVE CART ITEM
# =========================================================

@login_required
def cart_remove_view(request, item_id):
    item = get_object_or_404(
        CartItem,
        pk=item_id,
        cart__user=request.user,
    )

    item.delete()

    messages.info(
        request,
        "Item removed from cart."
    )

    return redirect("cart")


# =========================================================
# CLEAR CART
# =========================================================

@login_required
def cart_clear_view(request):
    cart = _get_or_create_cart(
        request.user
    )

    cart.items.all().delete()

    if cart.shop_id is not None:
        cart.shop = None
        cart.save(
            update_fields=[
                "shop",
                "updated_at",
            ]
        )

    messages.info(
        request,
        "Cart cleared."
    )

    return redirect("cart")


# =========================================================
# APPLY / REMOVE COUPON
# =========================================================

@login_required
def apply_coupon_view(request):
    if request.method != "POST":
        return redirect("cart")

    code = (
        request.POST.get("coupon_code", "")
        or ""
    ).strip().upper()

    if not code:
        messages.error(
            request,
            "Please enter a coupon code."
        )
        return redirect("cart")

    cart = _get_or_create_cart(
        request.user
    )

    items = list(
        cart.items
        .select_related("product")
        .all()
    )

    if not items:
        messages.error(
            request,
            "Add products before applying a coupon."
        )
        return redirect("cart")

    subtotal = sum(
        (
            item.quantity * item.price
            for item in items
        ),
        Decimal("0.00"),
    )

    coupon = (
        Coupon.objects
        .filter(code=code)
        .first()
    )

    if coupon is None:
        messages.error(
            request,
            "Invalid coupon code."
        )
        return redirect("cart")

    if not coupon.is_currently_valid:
        messages.error(
            request,
            "This coupon is expired or inactive."
        )
        return redirect("cart")

    if not coupon.can_user_use(request.user):
        messages.error(
            request,
            "You have already used this coupon."
        )
        return redirect("cart")

    if subtotal < coupon.minimum_order_amount:
        messages.error(
            request,
            f"Minimum order amount is "
            f"₹{coupon.minimum_order_amount}."
        )
        return redirect("cart")

    discount = coupon.calculate_discount(
        subtotal
    )

    if discount <= 0:
        messages.error(
            request,
            "This coupon is not applicable to your cart."
        )
        return redirect("cart")

    request.session["applied_coupon_code"] = coupon.code

    messages.success(
        request,
        f"{coupon.code} applied. You save ₹{discount}."
    )

    return redirect("cart")


@login_required
def remove_coupon_view(request):
    request.session.pop(
        "applied_coupon_code",
        None,
    )

    messages.info(
        request,
        "Coupon removed."
    )

    return redirect("cart")


# =========================================================
# CHECKOUT
# MULTI-SHOP
# =========================================================

@login_required
def checkout_view(request):

    cart = _get_or_create_cart(
        request.user
    )

    items = list(
        cart.items
        .select_related(
            "product",
            "product__shop",
            "product__brand",
        )
        .all()
    )

    # =====================================================
    # EMPTY CART
    # =====================================================

    if not items:
        messages.info(
            request,
            "Your cart is empty."
        )
        return redirect("cart")

    # =====================================================
    # USER ADDRESSES
    # Default address first
    # =====================================================

    addresses = (
        request.user
        .addresses
        .all()
        .order_by(
            "-is_default",
            "-id",
        )
    )

    totals = _totals_with_coupon(
        request,
        items,
    )

    # =====================================================
    # AMEXA COINS
    # 1 Coin = ₹1, usable only against product value.
    # =====================================================
    expire_wallet_coins(request.user)

    wallet, wallet_created = Wallet.objects.get_or_create(
        user=request.user
    )
    wallet.refresh_from_db()

    available_coins = wallet.coin_balance

    max_coin_usable = max(
        0,
        int(
            max(
                Decimal("0.00"),
                totals["subtotal"] - totals["discount_amount"],
            )
        ),
    )
    max_coin_usable = min(
        available_coins,
        max_coin_usable,
    )

    # =====================================================
    # CHECKOUT PAGE
    # =====================================================

    if request.method != "POST":

        default_address = (
            request.user
            .addresses
            .filter(is_default=True)
            .first()
        )

        context = {
            "cart": cart,
            "items": items,
            "addresses": addresses,
            "default_address": default_address,
            "wallet": wallet,
            "available_coins": available_coins,
            "max_coin_usable": max_coin_usable,
            **totals,
        }

        context.update(
            _cart_context(request)
        )

        return render(
            request,
            "customer/checkout.html",
            context,
        )

    # =====================================================
    # SELECTED DELIVERY ADDRESS
    # =====================================================

    address_id = (
        request.POST.get(
            "address_id",
            ""
        )
        or ""
    ).strip()

    if not address_id:

        messages.error(
            request,
            "Please select a delivery address."
        )

        context = {
            "cart": cart,
            "items": items,
            "addresses": addresses,
            "wallet": wallet,
            "available_coins": available_coins,
            "max_coin_usable": max_coin_usable,
            **totals,
        }

        context.update(
            _cart_context(request)
        )

        return render(
            request,
            "customer/checkout.html",
            context,
        )

    # Address must belong to current logged-in user.
    address = get_object_or_404(
        Address,
        pk=address_id,
        user=request.user,
    )

    # =====================================================
    # ADDRESS VALIDATION
    # =====================================================

    if not address.full_name:
        messages.error(
            request,
            "Delivery address name is missing."
        )
        return redirect("addresses")

    if not address.mobile:
        messages.error(
            request,
            "Delivery mobile number is missing."
        )
        return redirect("addresses")

    if not address.address_line:
        messages.error(
            request,
            "Delivery address is incomplete."
        )
        return redirect(
            "edit_address",
            pk=address.pk,
        )

    if (
        not address.city
        or not address.state
        or not address.pincode
    ):
        messages.error(
            request,
            "Please complete city, state and pincode "
            "before placing the order."
        )
        return redirect(
            "edit_address",
            pk=address.pk,
        )

    # =====================================================
    # GPS LOCATION VALIDATION
    # =====================================================

    try:
        customer_latitude = float(
            address.latitude or 0
        )
        customer_longitude = float(
            address.longitude or 0
        )
    except (TypeError, ValueError):
        customer_latitude = 0
        customer_longitude = 0

    if (
        customer_latitude == 0
        or customer_longitude == 0
    ):
        messages.error(
            request,
            "Please add Current Location to this "
            "delivery address before placing the order."
        )
        return redirect(
            "edit_address",
            pk=address.pk,
        )

    # Selected delivery location ko session me bhi sync karo.
    request.session[
        "customer_lat"
    ] = customer_latitude

    request.session[
        "customer_lon"
    ] = customer_longitude

    request.session[
        "customer_location_address"
    ] = (
        f"{address.address_line}, "
        f"{address.city}, "
        f"{address.state} - "
        f"{address.pincode}"
    )

    request.session.modified = True

    # =====================================================
    # PAYMENT METHOD
    # =====================================================

    payment_method = (
        request.POST.get(
            "payment_method",
            "COD"
        )
        or "COD"
    ).strip().upper()

    allowed_payment_methods = {
        "COD",
        "UPI",
        "CARD",
        "NETBANKING",
        "WALLET",
    }

    if payment_method not in allowed_payment_methods:
        payment_method = "COD"

    # Real online gateway is not connected yet.
    if payment_method != "COD":
        messages.warning(
            request,
            "Online payment gateway is not live yet. "
            "Please use Cash on Delivery."
        )
        return redirect("checkout")

    # =====================================================
    # AMEXA COINS REDEMPTION
    # =====================================================

    try:
        requested_coins = int(
            request.POST.get("use_coins", "0") or 0
        )
    except (TypeError, ValueError):
        requested_coins = 0

    if requested_coins < 0:
        requested_coins = 0

    # Never allow more than current valid balance or product payable value.
    requested_coins = min(
        requested_coins,
        max_coin_usable,
    )
    coin_discount = Decimal(requested_coins)

    # =====================================================
    # COUPON
    # =====================================================

    coupon = totals.get(
        "applied_coupon"
    )

    # =====================================================
    # CREATE MULTI-SHOP ORDER
    # =====================================================

    try:
        master_order, shop_orders = (
            _create_multi_shop_order_from_cart(
                request.user,
                address,
                cart,
                payment_method=payment_method,
                coupon=coupon,
                coin_discount=coin_discount,
            )
        )

    except ValueError as error:
        messages.error(
            request,
            str(error)
        )
        return redirect("cart")

    request.session.pop(
        "applied_coupon_code",
        None,
    )

    messages.success(
        request,
        "Order placed successfully."
    )

    if shop_orders:
        return redirect(
            "order_success",
            order_id=shop_orders[0].id,
        )

    return redirect("orders")


# =========================================================
# MONTHLY GROCERY PACKS
# =========================================================

@login_required
def monthly_packs_view(request):
    packs = (
        MonthlyPack.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .select_related("shop")
        .prefetch_related(
            "items",
            "items__product",
        )
        .order_by("-updated_at")
    )

    context = {
        "packs": packs,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/monthly_packs.html",
        context,
    )


@login_required
def monthly_pack_create_view(request):
    selected_shop_slug = request.session.get(
        "selected_shop_slug",
        ""
    )

    selected_shop = None

    if selected_shop_slug:
        selected_shop = (
            Shop.objects
            .filter(
                slug=selected_shop_slug,
                is_active=True,
            )
            .first()
        )

    if request.method == "POST":
        shop_id = request.POST.get("shop_id")
        name = (
            request.POST.get(
                "name",
                "Monthly Grocery Pack",
            )
            or "Monthly Grocery Pack"
        ).strip()

        description = (
            request.POST.get(
                "description",
                ""
            )
            or ""
        ).strip()

        shop = get_object_or_404(
            Shop,
            pk=shop_id,
            is_active=True,
        )

        pack = MonthlyPack.objects.create(
            user=request.user,
            shop=shop,
            name=name,
            description=description,
            discount_type="FIXED",
            discount_value=Decimal("0.00"),
            is_active=True,
        )

        messages.success(
            request,
            "Monthly pack created. Now add products.",
        )

        return redirect(
            "monthly_pack_detail",
            pack_id=pack.id,
        )

    shops = Shop.objects.filter(
        is_active=True
    ).order_by("name")

    context = {
        "shops": shops,
        "selected_shop": selected_shop,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/monthly_pack_create.html",
        context,
    )


@login_required
def monthly_pack_detail_view(request, pack_id):
    pack = get_object_or_404(
        MonthlyPack.objects
        .select_related("shop")
        .prefetch_related(
            "items",
            "items__product",
            "items__product__brand",
            "items__product__category",
        ),
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    query = (
        request.GET.get(
            "q",
            ""
        )
        or ""
    ).strip()

    products = (
        Product.objects
        .filter(
            shop=pack.shop,
            is_active=True,
            stock_quantity__gt=0,
        )
        .select_related(
            "brand",
            "category",
            "shop",
        )
        .order_by("name")
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            |
            Q(description__icontains=query)
            |
            Q(brand__name__icontains=query)
            |
            Q(category__name__icontains=query)
        ).distinct()

    pack_product_ids = set(
        pack.items.values_list(
            "product_id",
            flat=True,
        )
    )

    context = {
        "pack": pack,
        "products": products,
        "pack_product_ids": pack_product_ids,
        "query": query,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/monthly_pack_detail.html",
        context,
    )


@login_required
def monthly_pack_add_product_view(
    request,
    pack_id,
    product_id,
):
    if request.method != "POST":
        return redirect(
            "monthly_pack_detail",
            pack_id=pack_id,
        )

    pack = get_object_or_404(
        MonthlyPack,
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    product = get_object_or_404(
        Product,
        pk=product_id,
        shop=pack.shop,
        is_active=True,
    )

    if product.stock_quantity <= 0:
        messages.error(
            request,
            "This product is out of stock.",
        )
        return redirect(
            "monthly_pack_detail",
            pack_id=pack.id,
        )

    try:
        quantity = int(
            request.POST.get(
                "quantity",
                1,
            )
        )
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(
        1,
        min(
            quantity,
            product.stock_quantity,
        ),
    )

    item, created = (
        MonthlyPackItem.objects
        .get_or_create(
            pack=pack,
            product=product,
            defaults={
                "quantity": quantity,
            },
        )
    )

    if not created:
        new_quantity = min(
            item.quantity + quantity,
            product.stock_quantity,
        )

        item.quantity = new_quantity
        item.save(
            update_fields=[
                "quantity",
                "updated_at",
            ]
        )

    messages.success(
        request,
        f"{product.name} added to {pack.name}.",
    )

    return redirect(
        "monthly_pack_detail",
        pack_id=pack.id,
    )


@login_required
def monthly_pack_update_item_view(
    request,
    pack_id,
    item_id,
):
    pack = get_object_or_404(
        MonthlyPack,
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    item = get_object_or_404(
        MonthlyPackItem.objects.select_related(
            "product"
        ),
        pk=item_id,
        pack=pack,
    )

    try:
        quantity = int(
            request.POST.get(
                "quantity",
                1,
            )
        )
    except (TypeError, ValueError):
        quantity = 1

    if quantity <= 0:
        item.delete()

        messages.info(
            request,
            "Product removed from monthly pack.",
        )

        return redirect(
            "monthly_pack_detail",
            pack_id=pack.id,
        )

    quantity = min(
        quantity,
        item.product.stock_quantity,
    )

    if quantity <= 0:
        item.delete()

        messages.warning(
            request,
            "Product is no longer available and was removed.",
        )

        return redirect(
            "monthly_pack_detail",
            pack_id=pack.id,
        )

    item.quantity = quantity
    item.save(
        update_fields=[
            "quantity",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Monthly pack quantity updated.",
    )

    return redirect(
        "monthly_pack_detail",
        pack_id=pack.id,
    )


@login_required
def monthly_pack_remove_item_view(
    request,
    pack_id,
    item_id,
):
    pack = get_object_or_404(
        MonthlyPack,
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    item = get_object_or_404(
        MonthlyPackItem,
        pk=item_id,
        pack=pack,
    )

    product_name = item.product.name
    item.delete()

    messages.info(
        request,
        f"{product_name} removed from monthly pack.",
    )

    return redirect(
        "monthly_pack_detail",
        pack_id=pack.id,
    )


@login_required
def monthly_pack_delete_view(
    request,
    pack_id,
):
    pack = get_object_or_404(
        MonthlyPack,
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    if request.method == "POST":
        pack.is_active = False
        pack.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "Monthly pack deleted.",
        )

        return redirect(
            "monthly_packs"
        )

    context = {
        "pack": pack,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/monthly_pack_delete.html",
        context,
    )


@login_required
def monthly_pack_add_to_cart_view(
    request,
    pack_id,
):
    if request.method != "POST":
        return redirect(
            "monthly_pack_detail",
            pack_id=pack_id,
        )

    pack = get_object_or_404(
        MonthlyPack.objects
        .select_related("shop")
        .prefetch_related(
            "items",
            "items__product",
        ),
        pk=pack_id,
        user=request.user,
        is_active=True,
    )

    pack_items = list(
        pack.items
        .select_related("product")
        .all()
    )

    if not pack_items:
        messages.error(
            request,
            "This monthly pack is empty.",
        )

        return redirect(
            "monthly_pack_detail",
            pack_id=pack.id,
        )

    cart = _get_or_create_cart(
        request.user
    )

    added_count = 0
    skipped_products = []

    with transaction.atomic():

        for pack_item in pack_items:
            product = (
                Product.objects
                .select_for_update()
                .get(pk=pack_item.product_id)
            )

            if (
                not product.is_active
                or product.stock_quantity <= 0
            ):
                skipped_products.append(
                    product.name
                )
                continue

            quantity_to_add = min(
                pack_item.quantity,
                product.stock_quantity,
            )

            cart_item = (
                cart.items
                .filter(product=product)
                .first()
            )

            if cart_item:
                final_quantity = min(
                    cart_item.quantity
                    + quantity_to_add,
                    product.stock_quantity,
                )

                cart_item.quantity = final_quantity
                cart_item.price = product.price

                cart_item.save(
                    update_fields=[
                        "quantity",
                        "price",
                        "updated_at",
                    ]
                )

            else:
                CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=quantity_to_add,
                    price=product.price,
                )

            added_count += 1

        if cart.shop_id is not None:
            cart.shop = None
            cart.save(
                update_fields=[
                    "shop",
                    "updated_at",
                ]
            )

    if added_count:
        messages.success(
            request,
            f"{pack.name} added to cart.",
        )

    if skipped_products:
        messages.warning(
            request,
            "Some unavailable products were skipped: "
            + ", ".join(skipped_products[:5]),
        )

    return redirect("cart")



# =========================================================
# CUSTOMER ORDER OWNERSHIP HELPER
# Phone is AMEXA customer identity. This also safely supports
# old development accounts where the same phone was duplicated.
# =========================================================

def _customer_order_user_ids(user):
    if not user or not user.is_authenticated:
        return []

    phone = (getattr(user, "phone", "") or "").strip()

    if not phone:
        return [user.pk]

    User = get_user_model()

    return list(
        User.objects
        .filter(phone=phone)
        .values_list("pk", flat=True)
    )

# =========================================================
# ORDER SUCCESS
# =========================================================

@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related(
            "shop",
            "address",
            "master_order",
        ),
        pk=order_id,
        user_id__in=_customer_order_user_ids(request.user),
    )

    master_order = order.master_order

    shop_orders = (
        master_order.shop_orders
        .select_related("shop")
        .prefetch_related("items")
        .all()
        if master_order
        else Order.objects.filter(pk=order.pk)
    )

    context = {
        "order": order,
        "master_order": master_order,
        "shop_orders": shop_orders,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/order_success.html",
        context,
    )


# =========================================================
# MY ORDERS
# =========================================================

@login_required
def orders_view(request):
    orders = (
        Order.objects
        .filter(
            user_id__in=_customer_order_user_ids(request.user)
        )
        .select_related(
            "shop",
            "address",
            "master_order",
        )
        .prefetch_related(
            "items"
        )
        .order_by("-id")
    )

    context = {
        "orders": orders,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/orders.html",
        context,
    )


# =========================================================
# ORDER DETAIL / TRACKING
# =========================================================

@login_required
def order_detail_view(request, order_number):
    order = get_object_or_404(
        Order.objects
        .select_related(
            "user",
            "address",
            "shop",
            "master_order",
        )
        .prefetch_related(
            "items",
            "status_history",
            "delivery_assignments__delivery_partner",
        ),
        order_number=order_number,
        user_id__in=_customer_order_user_ids(request.user),
    )

    tracking_steps = [
        ("Pending", "Order Placed"),
        ("Confirmed", "Order Confirmed"),
        ("Preparing", "Preparing"),
        ("Out for Delivery", "Out for Delivery"),
        ("Delivered", "Delivered"),
    ]

    delivery_assignment = (
        order.delivery_assignments
        .select_related("delivery_partner")
        .order_by("-assigned_at")
        .first()
    )

    context = {
        "order": order,
        "master_order": order.master_order,
        "tracking_steps": tracking_steps,
        "delivery_assignment": delivery_assignment,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/order_detail.html",
        context,
    )


# =========================================================
# CUSTOMER LIVE TRACKING DATA
# order_detail.html is endpoint ko poll karke rider marker move karega.
# =========================================================

@login_required
def order_tracking_data_view(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related(
            "address",
            "shop",
        ),
        order_number=order_number,
        user_id__in=_customer_order_user_ids(request.user),
    )

    assignment = (
        order.delivery_assignments
        .select_related("delivery_partner")
        .order_by("-assigned_at")
        .first()
    )

    def clean_coordinate(value):
        if value is None:
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        # Existing models use 0 as "not set".
        if number == 0:
            return None

        return number

    customer_lat = clean_coordinate(
        order.address.latitude
    )
    customer_lon = clean_coordinate(
        order.address.longitude
    )

    shop_lat = None
    shop_lon = None

    if order.shop:
        shop_lat = clean_coordinate(
            order.shop.latitude
        )
        shop_lon = clean_coordinate(
            order.shop.longitude
        )

    rider_lat = None
    rider_lon = None
    rider_name = None
    rider_phone = None
    rider_status = None
    location_updated_at = None

    if assignment:
        rider_lat = clean_coordinate(
            assignment.current_latitude
        )
        rider_lon = clean_coordinate(
            assignment.current_longitude
        )

        rider_name = (
            assignment.delivery_partner.name
            or "AMEXA Rider"
        )

        rider_phone = (
            assignment.delivery_partner.phone
            or ""
        )

        rider_status = assignment.status

        if assignment.location_updated_at:
            location_updated_at = (
                assignment.location_updated_at.isoformat()
            )

    response = JsonResponse(
        {
            "ok": True,
            "order_number": order.order_number,
            "order_status": order.status,
            "payment_status": order.payment_status,
            "delivery_otp": order.delivery_otp or "",

            "customer": {
                "latitude": customer_lat,
                "longitude": customer_lon,
                "address": (
                    f"{order.address.address_line}, "
                    f"{order.address.city}"
                ),
            },

            "shop": {
                "name": (
                    order.shop.name
                    if order.shop
                    else "AMEXA Store"
                ),
                "latitude": shop_lat,
                "longitude": shop_lon,
            },

            "rider": {
                "assigned": bool(assignment),
                "name": rider_name,
                "phone": rider_phone,
                "status": rider_status,
                "latitude": rider_lat,
                "longitude": rider_lon,
                "location_updated_at": location_updated_at,
            },
        }
    )

    response["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    return response


# =========================================================
# DELIVERY PARTNER LIVE GPS HEARTBEAT
# Rider online hone par dashboard / Android app yahan
# current GPS bhejega. This location exists even before
# an order is assigned, so nearby-order matching can work.
# =========================================================

@login_required
def delivery_partner_location_update_view(request):
    if request.method != "POST":
        return JsonResponse(
            {"ok": False, "error": "POST request required."},
            status=405,
        )

    if getattr(request.user, "role", "") != "DELIVERY":
        return JsonResponse(
            {"ok": False, "error": "Delivery partner access required."},
            status=403,
        )

    profile = _delivery_profile_for_user(request.user)

    if not profile.can_access_dashboard:
        return JsonResponse(
            {"ok": False, "error": "Approved delivery account required."},
            status=403,
        )

    if not request.user.is_active_delivery:
        return JsonResponse(
            {"ok": False, "error": "Go online to share live location."},
            status=409,
        )

    try:
        latitude = Decimal(str(request.POST.get("latitude", "")).strip())
        longitude = Decimal(str(request.POST.get("longitude", "")).strip())
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Valid latitude and longitude are required."},
            status=400,
        )

    if not (Decimal("-90") <= latitude <= Decimal("90")):
        return JsonResponse({"ok": False, "error": "Latitude is out of range."}, status=400)
    if not (Decimal("-180") <= longitude <= Decimal("180")):
        return JsonResponse({"ok": False, "error": "Longitude is out of range."}, status=400)

    accuracy = None
    raw_accuracy = (request.POST.get("accuracy") or "").strip()
    if raw_accuracy:
        try:
            accuracy = max(Decimal("0"), Decimal(raw_accuracy))
        except Exception:
            accuracy = None

    current_area = (request.POST.get("area") or "").strip()[:180]
    now = timezone.now()

    profile.current_latitude = latitude
    profile.current_longitude = longitude
    profile.location_accuracy = accuracy
    profile.current_area = current_area
    profile.location_updated_at = now
    profile.save(
        update_fields=[
            "current_latitude",
            "current_longitude",
            "location_accuracy",
            "current_area",
            "location_updated_at",
            "updated_at",
        ]
    )

    DeliveryAssignment.objects.filter(
        delivery_partner=request.user,
        status__in=["Assigned", "Accepted", "Picked"],
    ).update(
        current_latitude=latitude,
        current_longitude=longitude,
        location_updated_at=now,
    )

    waiting_orders = (
        Order.objects
        .filter(
            picking_task__status="PACKED",
            status__in=["Confirmed", "Preparing"],
        )
        .select_related("shop", "address")
        .order_by("created_at")[:10]
    )

    newly_assigned_order = ""
    for waiting_order in waiting_orders:
        if waiting_order.delivery_assignments.exclude(status="Rejected").exists():
            continue
        assignment = _assign_available_rider(waiting_order)
        if assignment and assignment.delivery_partner_id == request.user.id:
            newly_assigned_order = waiting_order.order_number
            break

    return JsonResponse(
        {
            "ok": True,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "accuracy": float(accuracy) if accuracy is not None else None,
            "location_updated_at": now.isoformat(),
            "newly_assigned_order": newly_assigned_order,
        }
    )


# =========================================================
# DELIVERY PARTNER LOCATION UPDATE
# Delivery app/browser rider ka GPS yahan POST karega.
# =========================================================

@login_required
def delivery_location_update_view(
    request,
    order_number,
):
    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "POST request required.",
            },
            status=405,
        )

    if (
        getattr(request.user, "role", "") != "DELIVERY"
        and not request.user.is_staff
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Delivery partner access required.",
            },
            status=403,
        )

    order = get_object_or_404(
        Order,
        order_number=order_number,
    )

    assignment_query = (
        DeliveryAssignment.objects
        .select_related(
            "order",
            "delivery_partner",
        )
        .filter(order=order)
    )

    if not request.user.is_staff:
        assignment_query = assignment_query.filter(
            delivery_partner=request.user
        )

    assignment = (
        assignment_query
        .order_by("-assigned_at")
        .first()
    )

    if assignment is None:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No delivery assignment found "
                    "for this rider and order."
                ),
            },
            status=404,
        )

    latitude = request.POST.get("latitude")
    longitude = request.POST.get("longitude")

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Valid latitude and longitude "
                    "are required."
                ),
            },
            status=400,
        )

    if not (-90 <= latitude <= 90):
        return JsonResponse(
            {
                "ok": False,
                "error": "Latitude is out of range.",
            },
            status=400,
        )

    if not (-180 <= longitude <= 180):
        return JsonResponse(
            {
                "ok": False,
                "error": "Longitude is out of range.",
            },
            status=400,
        )

    assignment.current_latitude = latitude
    assignment.current_longitude = longitude
    assignment.location_updated_at = timezone.now()

    assignment.save(
        update_fields=[
            "current_latitude",
            "current_longitude",
            "location_updated_at",
        ]
    )

    return JsonResponse(
        {
            "ok": True,
            "order_number": order.order_number,
            "latitude": latitude,
            "longitude": longitude,
            "location_updated_at": (
                assignment.location_updated_at.isoformat()
            ),
        }
    )


# =========================================================
# CANCEL ORDER
# SHOP-WISE CANCELLATION
# =========================================================

@login_required
def cancel_order_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related(
            "master_order",
            "shop",
        ),
        pk=order_id,
        user_id__in=_customer_order_user_ids(request.user),
    )

    if order.status == "Cancelled":
        messages.info(
            request,
            "This order is already cancelled."
        )

        return redirect(
            "order_detail",
            order_number=order.order_number,
        )

    if order.status not in {
        "Pending",
        "Confirmed",
    }:
        messages.info(
            request,
            "This order can no longer be cancelled."
        )

        return redirect(
            "order_detail",
            order_number=order.order_number,
        )

    if request.method == "POST":
        reason = (
            request.POST
            .get("reason", "")
            .strip()
            or "Other"
        )

        description = (
            request.POST
            .get("description", "")
            .strip()
        )

        with transaction.atomic():

            order = (
                Order.objects
                .select_for_update()
                .select_related(
                    "master_order",
                    "shop",
                )
                .get(pk=order.id)
            )

            if order.status == "Cancelled":
                messages.info(
                    request,
                    "Order already cancelled."
                )

                return redirect(
                    "order_detail",
                    order_number=order.order_number,
                )

            for item in (
                order.items
                .select_related("product")
                .all()
            ):
                if item.product_id:
                    product = (
                        Product.objects
                        .select_for_update()
                        .get(pk=item.product_id)
                    )

                    product.stock_quantity += item.quantity

                    product.save(
                        update_fields=[
                            "stock_quantity"
                        ]
                    )

            order.status = "Cancelled"
            order.cancellation_reason = reason
            order.cancellation_description = description
            order.cancelled_at = timezone.now()
            order.payment_status = "Refund Pending"

            order.save(
                update_fields=[
                    "status",
                    "cancellation_reason",
                    "cancellation_description",
                    "cancelled_at",
                    "payment_status",
                    "updated_at",
                ]
            )

            order.create_status_history(
                "Cancelled",
                reason,
            )

            if hasattr(order, "settlement"):
                settlement = order.settlement
                settlement.status = "On Hold"
                settlement.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            if order.master_order:
                _update_master_order_status(
                    order.master_order
                )
                order.master_order.refresh_from_db()

                # If the complete MasterOrder is now cancelled, return
                # redeemed Coins once and reverse any invalid reward lot.
                if order.master_order.status == "Cancelled":
                    refund_redeemed_coins(order.master_order)
                    reverse_order_reward(order.master_order)

                all_cancelled = not (
                    order.master_order
                    .shop_orders
                    .exclude(status="Cancelled")
                    .exists()
                )

                if all_cancelled:
                    try:
                        payment = order.master_order.payment
                    except Payment.DoesNotExist:
                        payment = None

                    if payment:
                        payment.payment_status = (
                            "Refund Pending"
                            if payment.payment_method != "COD"
                            else "Pending"
                        )

                        payment.save(
                            update_fields=[
                                "payment_status",
                                "updated_at",
                            ]
                        )

        messages.success(
            request,
            "Order cancelled successfully."
        )

        return redirect(
            "order_detail",
            order_number=order.order_number,
        )

    context = {
        "order": order,
        "master_order": order.master_order,
    }

    context.update(_cart_context(request))

    return render(
        request,
        "customer/cancel_order.html",
        context,
    )


# =========================================================
# AMEXA LIVE LOCATION PICKER
# =========================================================

def location_picker_view(request):
    """
    Rapido-style map/location selection page.
    Current selected latitude/longitude session se leta hai.
    """

    latitude = request.session.get("customer_lat")
    longitude = request.session.get("customer_lon")

    context = {
        "saved_latitude": latitude or "",
        "saved_longitude": longitude or "",
    }

    return render(
        request,
        "customer/location_picker.html",
        context,
    )


# =========================================================
# SAVE LIVE LOCATION
# =========================================================

def location_save_view(request):
    """
    Map se selected latitude/longitude ko session me save karta hai.
    """

    if request.method != "POST":
        return redirect("location_picker")

    latitude = (
        request.POST.get("latitude", "")
        or ""
    ).strip()

    longitude = (
        request.POST.get("longitude", "")
        or ""
    ).strip()

    if not latitude or not longitude:
        messages.error(
            request,
            "Please select your location first."
        )
        return redirect("location_picker")

    try:
        latitude = float(latitude)
        longitude = float(longitude)

    except (TypeError, ValueError):
        messages.error(
            request,
            "Invalid location. Please try again."
        )
        return redirect("location_picker")

    # Valid GPS coordinate check
    if not (-90 <= latitude <= 90):
        messages.error(
            request,
            "Invalid latitude."
        )
        return redirect("location_picker")

    if not (-180 <= longitude <= 180):
        messages.error(
            request,
            "Invalid longitude."
        )
        return redirect("location_picker")

    # -----------------------------------------------------
    # SAVE LOCATION IN SESSION
    # These names match our existing AMEXA location system.
    # -----------------------------------------------------

    request.session["customer_lat"] = latitude
    request.session["customer_lon"] = longitude

    # Old selected shop remove karo,
    # new location ke according nearest shop choose hoga.
    request.session.pop(
        "selected_shop_slug",
        None,
    )

    request.session.modified = True

    messages.success(
        request,
        "📍 Current location updated successfully."
    )

    return redirect("home")
@login_required
def delete_address_view(request, pk):

    address = get_object_or_404(
        Address,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":

        was_default = address.is_default

        address.delete()

        # Agar default address delete hua,
        # kisi aur address ko default bana do.
        if was_default:

            next_address = (
                request.user.addresses
                .order_by("-id")
                .first()
            )

            if next_address:
                next_address.is_default = True
                next_address.save(
                    update_fields=["is_default"]
                )

        messages.success(
            request,
            "Address deleted successfully."
        )

    return redirect("addresses")
# =========================================================
# DELIVERY PARTNER LIVE TRACKING PAGE
# Rider apne phone se is page ko open karega.
# =========================================================

@login_required
def delivery_live_tracking_view(request, order_number):

    # Sirf DELIVERY user ya admin/staff access kar sake
    if (
        getattr(request.user, "role", "") != "DELIVERY"
        and not request.user.is_staff
    ):
        messages.error(
            request,
            "Delivery partner access required."
        )
        return redirect("home")

    # Order find karo
    order = get_object_or_404(
        Order.objects.select_related(
            "shop",
            "address",
        ),
        order_number=order_number,
    )

    # Is order ki delivery assignment
    assignment_query = (
        DeliveryAssignment.objects
        .select_related(
            "delivery_partner",
            "order",
            "order__shop",
            "order__address",
        )
        .filter(order=order)
    )

    # Normal rider sirf apna assigned order dekh sake
    if not request.user.is_staff:
        assignment_query = assignment_query.filter(
            delivery_partner=request.user
        )

    assignment = (
        assignment_query
        .order_by("-assigned_at")
        .first()
    )

    if assignment is None:
        messages.error(
            request,
            "This order is not assigned to you."
        )
        return redirect("home")

    context = {
        "order": order,
        "assignment": assignment,
    }

    return render(
        request,
        "customer/delivery_live_tracking.html",
        context,
    )
# =========================================================
# ABOUT AMEXA
# =========================================================

def about_view(request):

    about = (
        AboutPage.objects
        .filter(is_active=True)
        .order_by("-updated_at")
        .first()
    )

    return render(
        request,
        "customer/about.html",
        {
            "about": about,
        },
    )


# =========================================================
# DELIVERY PARTNER DASHBOARD + CONTROLLED ORDER WORKFLOW
# =========================================================

def _delivery_profile_for_user(user):
    profile, created = DeliveryPartnerProfile.objects.get_or_create(
        user=user
    )
    return profile


def _save_delivery_document(
    profile,
    document_type,
    uploaded_file,
    document_number="",
):
    document = (
        DeliveryPartnerDocument.objects
        .filter(
            profile=profile,
            document_type=document_type,
        )
        .first()
    )

    if document is None:
        document = DeliveryPartnerDocument(
            profile=profile,
            document_type=document_type,
        )

    document.document_file = uploaded_file
    document.set_document_number(document_number)
    document.status = "PENDING"
    document.rejection_reason = ""
    document.verified_at = None
    document.verified_by = None
    document.save()

    return document


def _required_delivery_document_types(profile):
    return {
        "AADHAAR_FRONT",
        "AADHAAR_BACK",
        "PAN",
        "SELFIE",
    }


@login_required
def delivery_onboarding_view(request, step=1):
    if request.user.is_staff:
        return redirect("delivery_dashboard")

    profile = _delivery_profile_for_user(request.user)

    if profile.verification_status == "APPROVED":
        return redirect("delivery_dashboard")

    if profile.verification_status in {
        "PENDING",
        "UNDER_REVIEW",
        "BLOCKED",
    }:
        return redirect("delivery_verification_status")

    step = max(1, min(int(step), 4))

    if step > profile.onboarding_step:
        return redirect(
            "delivery_onboarding",
            step=profile.onboarding_step,
        )

    form = None

    if step == 1:
        form = DeliveryPersonalDetailsForm(
            request.POST or None,
            request.FILES or None,
            instance=profile,
            user=request.user,
        )

        if request.method == "POST" and form.is_valid():
            profile = form.save()
            profile.onboarding_step = max(profile.onboarding_step, 2)
            profile.verification_status = "DRAFT"
            profile.save(
                update_fields=[
                    "onboarding_step",
                    "verification_status",
                    "updated_at",
                ]
            )
            return redirect("delivery_onboarding", step=2)

    elif step == 2:
        form = DeliveryDocumentsForm(
            request.POST or None,
            request.FILES or None,
            profile=profile,
        )

        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                _save_delivery_document(
                    profile,
                    "AADHAAR_FRONT",
                    form.cleaned_data["aadhaar_front"],
                    form.cleaned_data["aadhaar_number"],
                )
                _save_delivery_document(
                    profile,
                    "AADHAAR_BACK",
                    form.cleaned_data["aadhaar_back"],
                    form.cleaned_data["aadhaar_number"],
                )
                _save_delivery_document(
                    profile,
                    "PAN",
                    form.cleaned_data["pan_card"],
                    form.cleaned_data["pan_number"],
                )
                _save_delivery_document(
                    profile,
                    "SELFIE",
                    form.cleaned_data["selfie"],
                )

                if form.cleaned_data.get("driving_licence"):
                    _save_delivery_document(
                        profile,
                        "DRIVING_LICENCE",
                        form.cleaned_data["driving_licence"],
                        form.cleaned_data.get(
                            "driving_licence_number",
                            "",
                        ),
                    )

                if form.cleaned_data.get("vehicle_rc"):
                    _save_delivery_document(
                        profile,
                        "VEHICLE_RC",
                        form.cleaned_data["vehicle_rc"],
                        profile.vehicle_number,
                    )

                profile.onboarding_step = max(
                    profile.onboarding_step,
                    3,
                )
                profile.save(
                    update_fields=["onboarding_step", "updated_at"]
                )

            return redirect("delivery_onboarding", step=3)

    elif step == 3:
        bank_account = (
            DeliveryPartnerBankAccount.objects
            .filter(profile=profile)
            .first()
        )

        initial = {}
        if bank_account:
            initial = {
                "account_holder_name": bank_account.account_holder_name,
                "bank_name": bank_account.bank_name,
                "ifsc_code": bank_account.ifsc_code,
            }

        form = DeliveryBankDetailsForm(
            request.POST or None,
            request.FILES or None,
            initial=initial,
        )

        if request.method == "POST" and form.is_valid():
            if bank_account is None:
                bank_account = DeliveryPartnerBankAccount(
                    profile=profile
                )

            bank_account.account_holder_name = (
                form.cleaned_data["account_holder_name"]
            )
            bank_account.bank_name = form.cleaned_data["bank_name"]
            bank_account.ifsc_code = form.cleaned_data["ifsc_code"]
            bank_account.set_account_number(
                form.cleaned_data["account_number"]
            )

            if form.cleaned_data.get("cancelled_cheque"):
                bank_account.cancelled_cheque = (
                    form.cleaned_data["cancelled_cheque"]
                )

            bank_account.status = "PENDING"
            bank_account.rejection_reason = ""
            bank_account.verified_at = None
            bank_account.verified_by = None
            bank_account.save()

            profile.onboarding_step = max(profile.onboarding_step, 4)
            profile.save(
                update_fields=["onboarding_step", "updated_at"]
            )
            return redirect("delivery_onboarding", step=4)

    else:
        form = DeliveryFinalVerificationForm(request.POST or None)

        existing_document_types = set(
            profile.documents.values_list(
                "document_type",
                flat=True,
            )
        )
        missing_document_types = (
            _required_delivery_document_types(profile)
            - existing_document_types
        )
        bank_account = (
            DeliveryPartnerBankAccount.objects
            .filter(profile=profile)
            .first()
        )

        if request.method == "POST" and form.is_valid():
            if missing_document_types:
                messages.error(
                    request,
                    "Please upload all required documents.",
                )
                return redirect("delivery_onboarding", step=2)

            if bank_account is None:
                messages.error(
                    request,
                    "Please add your bank details.",
                )
                return redirect("delivery_onboarding", step=3)

            profile.terms_accepted = True
            profile.onboarding_step = 4
            profile.save(
                update_fields=[
                    "terms_accepted",
                    "onboarding_step",
                    "updated_at",
                ]
            )
            profile.submit_for_verification()

            request.user.is_active_delivery = False
            request.user.save(update_fields=["is_active_delivery"])

            messages.success(
                request,
                "Your profile was submitted for AMEXA verification.",
            )
            return redirect("delivery_verification_status")

    return render(
        request,
        "customer/delivery_onboarding.html",
        {
            "form": form,
            "profile": profile,
            "step": step,
            "step_range": range(1, 5),
        },
    )


@login_required
def delivery_verification_status_view(request):
    if request.user.is_staff:
        return redirect("delivery_dashboard")

    profile = _delivery_profile_for_user(request.user)

    if profile.verification_status == "APPROVED":
        return redirect("delivery_dashboard")

    if profile.verification_status == "DRAFT":
        return redirect(
            "delivery_onboarding",
            step=profile.onboarding_step,
        )

    return render(
        request,
        "customer/delivery_verification_status.html",
        {
            "profile": profile,
            "documents": profile.documents.all(),
            "bank_account": (
                DeliveryPartnerBankAccount.objects
                .filter(profile=profile)
                .first()
            ),
        },
    )


# =========================================================
# SHOPKEEPER ONBOARDING / VERIFICATION / BASIC DASHBOARD
# =========================================================

SHOPKEEPER_FOOD_TYPES = {
    "GROCERY",
    "FRUITS_VEGETABLES",
    "DAIRY",
    "BAKERY",
    "RESTAURANT",
}


def _shopkeeper_profile_for_user(user):
    profile, _ = ShopkeeperProfile.objects.get_or_create(user=user)
    return profile


def _save_shopkeeper_document(
    profile,
    document_type,
    uploaded_file,
    document_number="",
):
    document = (
        ShopkeeperDocument.objects
        .filter(profile=profile, document_type=document_type)
        .first()
    )
    if document is None:
        document = ShopkeeperDocument(
            profile=profile,
            document_type=document_type,
        )
    document.document_file = uploaded_file
    document.set_document_number(document_number)
    document.status = "PENDING"
    document.rejection_reason = ""
    document.verified_at = None
    document.verified_by = None
    document.save()
    return document


def _required_shopkeeper_document_types(profile):
    required = {
        "AADHAAR_FRONT",
        "AADHAAR_BACK",
        "PAN",
        "GST_CERTIFICATE",
        "OWNER_SELFIE",
        "SHOP_FRONT",
    }
    if (
        profile.shop_id
        and profile.shop.shop_type in SHOPKEEPER_FOOD_TYPES
    ):
        required.add("FSSAI_CERTIFICATE")
    return required


@login_required
def shopkeeper_onboarding_view(request, step=1):
    if request.user.is_staff:
        return redirect("admin_control_center")

    profile = _shopkeeper_profile_for_user(request.user)

    if profile.verification_status == "APPROVED":
        return redirect("shopkeeper_dashboard")

    if profile.verification_status in {
        "PENDING",
        "UNDER_REVIEW",
        "BLOCKED",
    }:
        return redirect("shopkeeper_verification_status")

    step = max(1, min(int(step), 5))
    if step > profile.onboarding_step:
        return redirect(
            "shopkeeper_onboarding",
            step=profile.onboarding_step,
        )

    form = None

    if step == 1:
        form = ShopkeeperPersonalDetailsForm(
            request.POST or None,
            request.FILES or None,
            instance=profile,
            user=request.user,
        )
        if request.method == "POST" and form.is_valid():
            profile = form.save()
            profile.onboarding_step = max(profile.onboarding_step, 2)
            profile.verification_status = "DRAFT"
            profile.save(
                update_fields=[
                    "onboarding_step",
                    "verification_status",
                    "updated_at",
                ]
            )
            return redirect("shopkeeper_onboarding", step=2)

    elif step == 2:
        form = ShopkeeperBusinessDetailsForm(
            request.POST or None,
            instance=profile.shop if profile.shop_id else None,
        )
        if request.method == "POST" and form.is_valid():
            shop = form.save(commit=False)
            shop.owner = request.user
            shop.is_active = False
            shop.is_online = False
            shop.save()
            profile.shop = shop
            profile.onboarding_step = max(profile.onboarding_step, 3)
            profile.save(
                update_fields=["shop", "onboarding_step", "updated_at"]
            )
            return redirect("shopkeeper_onboarding", step=3)

    elif step == 3:
        form = ShopkeeperDocumentsForm(
            request.POST or None,
            request.FILES or None,
            profile=profile,
        )
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                aadhaar_number = form.cleaned_data["aadhaar_number"]
                pan_number = form.cleaned_data["pan_number"]
                _save_shopkeeper_document(
                    profile,
                    "AADHAAR_FRONT",
                    form.cleaned_data["aadhaar_front"],
                    aadhaar_number,
                )
                _save_shopkeeper_document(
                    profile,
                    "AADHAAR_BACK",
                    form.cleaned_data["aadhaar_back"],
                    aadhaar_number,
                )
                _save_shopkeeper_document(
                    profile,
                    "PAN",
                    form.cleaned_data["pan_card"],
                    pan_number,
                )
                _save_shopkeeper_document(
                    profile,
                    "GST_CERTIFICATE",
                    form.cleaned_data["gst_certificate"],
                    profile.shop.gstin,
                )
                _save_shopkeeper_document(
                    profile,
                    "OWNER_SELFIE",
                    form.cleaned_data["owner_selfie"],
                )
                _save_shopkeeper_document(
                    profile,
                    "SHOP_FRONT",
                    form.cleaned_data["shop_front"],
                )
                if form.cleaned_data.get("fssai_certificate"):
                    _save_shopkeeper_document(
                        profile,
                        "FSSAI_CERTIFICATE",
                        form.cleaned_data["fssai_certificate"],
                        profile.shop.fssai_number,
                    )
                profile.onboarding_step = max(profile.onboarding_step, 4)
                profile.save(
                    update_fields=["onboarding_step", "updated_at"]
                )
            return redirect("shopkeeper_onboarding", step=4)

    elif step == 4:
        bank_account = ShopkeeperBankAccount.objects.filter(
            profile=profile
        ).first()
        initial = {}
        if bank_account:
            initial = {
                "account_holder_name": bank_account.account_holder_name,
                "bank_name": bank_account.bank_name,
                "ifsc_code": bank_account.ifsc_code,
                "upi_id": bank_account.upi_id,
            }
        form = ShopkeeperBankDetailsForm(
            request.POST or None,
            request.FILES or None,
            initial=initial,
        )
        if request.method == "POST" and form.is_valid():
            if bank_account is None:
                bank_account = ShopkeeperBankAccount(profile=profile)
            bank_account.account_holder_name = form.cleaned_data[
                "account_holder_name"
            ]
            bank_account.bank_name = form.cleaned_data["bank_name"]
            bank_account.ifsc_code = form.cleaned_data["ifsc_code"]
            bank_account.upi_id = form.cleaned_data.get("upi_id", "")
            bank_account.set_account_number(
                form.cleaned_data["account_number"]
            )
            if form.cleaned_data.get("cancelled_cheque"):
                bank_account.cancelled_cheque = form.cleaned_data[
                    "cancelled_cheque"
                ]
            bank_account.status = "PENDING"
            bank_account.rejection_reason = ""
            bank_account.verified_at = None
            bank_account.verified_by = None
            bank_account.save()
            profile.onboarding_step = max(profile.onboarding_step, 5)
            profile.save(
                update_fields=["onboarding_step", "updated_at"]
            )
            return redirect("shopkeeper_onboarding", step=5)

    else:
        form = ShopkeeperFinalVerificationForm(request.POST or None)
        existing_types = set(
            profile.documents.values_list("document_type", flat=True)
        )
        missing_types = (
            _required_shopkeeper_document_types(profile) - existing_types
        )
        bank_account = ShopkeeperBankAccount.objects.filter(
            profile=profile
        ).first()

        if request.method == "POST" and form.is_valid():
            if missing_types:
                messages.error(
                    request,
                    "Please upload all mandatory shop documents.",
                )
                return redirect("shopkeeper_onboarding", step=3)
            if bank_account is None:
                messages.error(request, "Please add shop payout details.")
                return redirect("shopkeeper_onboarding", step=4)

            profile.terms_accepted = True
            profile.onboarding_step = 5
            profile.save(
                update_fields=[
                    "terms_accepted",
                    "onboarding_step",
                    "updated_at",
                ]
            )
            profile.submit_for_verification()
            messages.success(
                request,
                "Your shop application was submitted for verification.",
            )
            return redirect("shopkeeper_verification_status")

    return render(
        request,
        "customer/shopkeeper_onboarding.html",
        {
            "form": form,
            "profile": profile,
            "step": step,
            "step_range": range(1, 6),
        },
    )


@login_required
def shopkeeper_verification_status_view(request):
    if request.user.is_staff:
        return redirect("admin_control_center")
    profile = _shopkeeper_profile_for_user(request.user)
    if profile.verification_status == "APPROVED":
        return redirect("shopkeeper_dashboard")
    if profile.verification_status == "DRAFT":
        return redirect(
            "shopkeeper_onboarding",
            step=profile.onboarding_step,
        )
    return render(
        request,
        "customer/shopkeeper_verification_status.html",
        {
            "profile": profile,
            "documents": profile.documents.all(),
            "bank_account": ShopkeeperBankAccount.objects.filter(
                profile=profile
            ).first(),
        },
    )


@login_required
def shopkeeper_dashboard_view(request):
    if request.user.is_staff:
        return redirect("admin_control_center")
    profile = _shopkeeper_profile_for_user(request.user)
    if not profile.can_access_dashboard:
        if profile.verification_status == "DRAFT":
            return redirect(
                "shopkeeper_onboarding",
                step=profile.onboarding_step,
            )
        return redirect("shopkeeper_verification_status")

    shop = profile.shop
    if request.method == "POST":
        shop.is_online = request.POST.get("is_online") == "1"
        shop.save(update_fields=["is_online"])
        messages.success(
            request,
            "Shop is online." if shop.is_online else "Shop is offline.",
        )
        return redirect("shopkeeper_dashboard")

    shop_orders = Order.objects.filter(shop=shop)
    delivered_orders = shop_orders.filter(status="Delivered")
    total_sales = delivered_orders.aggregate(
        value=Sum("total_amount")
    )["value"] or Decimal("0.00")
    total_profit = Settlement.objects.filter(
        shop=shop,
        order__status="Delivered",
    ).aggregate(value=Sum("shop_payable"))["value"] or Decimal("0.00")

    return render(
        request,
        "customer/shopkeeper_dashboard.html",
        {
            "profile": profile,
            "shop": shop,
            "today_orders": shop_orders.filter(
                created_at__date=timezone.localdate()
            ).count(),
            "pending_orders": shop_orders.filter(
                status__in=["Pending", "Confirmed", "Preparing"]
            ).count(),
            "total_sales": total_sales,
            "total_profit": total_profit,
            "inventory_count": Product.objects.filter(shop=shop).count(),
            "low_stock_count": Product.objects.filter(
                shop=shop,
                stock_quantity__lte=5,
                is_active=True,
            ).count(),
            "recent_orders": shop_orders.select_related("user")[:6],
        },
    )


def _shopkeeper_app_profile(request):
    if request.user.is_staff:
        return None
    profile = (
        ShopkeeperProfile.objects
        .filter(user=request.user)
        .select_related("shop", "user")
        .first()
    )
    if profile and profile.can_access_dashboard:
        return profile
    return None


def _sync_shop_product_listing(product):
    ShopProduct.objects.update_or_create(
        product=product,
        shop=product.shop,
        defaults={
            "selling_price": product.price,
            "mrp": product.mrp,
            "stock_quantity": product.stock_quantity,
            "is_active": product.is_active,
        },
    )


def _ensure_order_picking_task(order):
    task, _ = OrderPickingTask.objects.get_or_create(
        order=order,
        defaults={"shop": order.shop},
    )
    if task.shop_id != order.shop_id:
        task.shop = order.shop
        task.save(update_fields=["shop", "updated_at"])

    for order_item in order.items.all():
        picking_item, created = OrderPickingItem.objects.get_or_create(
            task=task,
            order_item=order_item,
            defaults={"required_quantity": order_item.quantity},
        )
        if not created and picking_item.required_quantity != order_item.quantity:
            picking_item.required_quantity = order_item.quantity
            picking_item.picked_quantity = min(
                picking_item.picked_quantity,
                order_item.quantity,
            )
            picking_item.save(
                update_fields=[
                    "required_quantity",
                    "picked_quantity",
                    "updated_at",
                ]
            )
    return task


def _assign_available_rider(order):
    current_assignment = (
        order.delivery_assignments
        .exclude(status="Rejected")
        .select_related("delivery_partner", "delivery_partner__delivery_profile")
        .first()
    )
    if current_assignment:
        return current_assignment

    if not order.shop_id:
        return None

    try:
        shop_lat = float(order.shop.latitude or 0)
        shop_lon = float(order.shop.longitude or 0)
    except (TypeError, ValueError):
        return None

    if shop_lat == 0 or shop_lon == 0:
        return None

    fresh_after = timezone.now() - timedelta(minutes=RIDER_LOCATION_FRESH_MINUTES)

    profiles = (
        DeliveryPartnerProfile.objects
        .filter(
            verification_status="APPROVED",
            user__role="DELIVERY",
            user__is_active=True,
            user__is_active_delivery=True,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
            location_updated_at__gte=fresh_after,
        )
        .select_related("user")
    )

    candidates = []
    for profile in profiles:
        try:
            rider_lat = float(profile.current_latitude)
            rider_lon = float(profile.current_longitude)
        except (TypeError, ValueError):
            continue

        distance_km = order.shop.distance_to(rider_lat, rider_lon)
        if distance_km > DELIVERY_ASSIGNMENT_RADIUS_KM:
            continue

        active_jobs = DeliveryAssignment.objects.filter(
            delivery_partner=profile.user,
            status__in=["Assigned", "Accepted", "Picked"],
        ).count()

        if active_jobs >= 2:
            continue

        candidates.append((distance_km, active_jobs, profile.user_id, profile.user))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, _, rider = candidates[0]

    return DeliveryAssignment.objects.create(
        order=order,
        delivery_partner=rider,
        status="Assigned",
        current_latitude=rider.delivery_profile.current_latitude,
        current_longitude=rider.delivery_profile.current_longitude,
        location_updated_at=rider.delivery_profile.location_updated_at,
    )


def _move_expired_batches_to_bad_inventory(shop, user=None):
    today = timezone.localdate()
    expired_ids = list(
        InventoryBatch.objects.filter(
            shop=shop,
            status="ACTIVE",
            expiry_date__lt=today,
            quantity_available__gt=0,
        ).values_list("pk", flat=True)
    )

    moved_quantity = 0
    for batch_id in expired_ids:
        with transaction.atomic():
            batch = (
                InventoryBatch.objects
                .select_for_update()
                .select_related("product")
                .get(pk=batch_id, shop=shop)
            )
            if batch.status != "ACTIVE" or batch.quantity_available <= 0:
                continue

            quantity = batch.quantity_available
            product = Product.objects.select_for_update().get(
                pk=batch.product_id,
                shop=shop,
            )
            product.stock_quantity = max(
                0,
                product.stock_quantity - quantity,
            )
            product.save(update_fields=["stock_quantity"])

            BadInventoryRecord.objects.create(
                shop=shop,
                product=product,
                batch=batch,
                quantity=quantity,
                reason="EXPIRED",
                unit_cost=batch.purchase_price or product.cost_price,
                note=f"Auto moved after expiry on {batch.expiry_date}.",
                created_by=user,
            )
            batch.quantity_available = 0
            batch.status = "EXPIRED"
            batch.save(
                update_fields=[
                    "quantity_available",
                    "status",
                    "updated_at",
                ]
            )
            _sync_shop_product_listing(product)
            moved_quantity += quantity

    return moved_quantity


@login_required
def shopkeeper_orders_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")

    shop = profile.shop
    if shop.auto_accept_orders:
        pending_orders = list(
            Order.objects.filter(shop=shop, status="Pending")
        )
        for order in pending_orders:
            order.status = "Confirmed"
            order.save(update_fields=["status", "updated_at"])
            _ensure_order_picking_task(order)
            order.create_status_history(
                "Confirmed",
                "Automatically accepted by shop settings.",
            )
            if order.master_order_id:
                _update_master_order_status(order.master_order)

    picker_sync_failed = False
    for accepted_order in Order.objects.filter(
        shop=shop,
        status__in=["Confirmed", "Preparing"],
        picking_task__isnull=True,
    ).prefetch_related("items"):
        try:
            _ensure_order_picking_task(accepted_order)
        except Exception:
            # Order screen must remain usable even if a legacy order has
            # incomplete picker data. The action endpoint retries safely.
            picker_sync_failed = True

    if picker_sync_failed:
        messages.warning(
            request,
            "Some accepted orders are waiting for picker sync.",
        )

    status_filter = (request.GET.get("status") or "ALL").strip()
    allowed_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    orders = (
        Order.objects
        .filter(shop=shop)
        .select_related(
            "user",
            "address",
            "master_order",
            "picking_task",
            "picking_task__picker",
        )
        .prefetch_related("items", "items__product")
    )
    if status_filter in allowed_statuses:
        orders = orders.filter(status=status_filter)
    else:
        status_filter = "ALL"

    status_counts = {
        status: Order.objects.filter(shop=shop, status=status).count()
        for status in allowed_statuses
    }
    return render(
        request,
        "customer/shopkeeper_orders.html",
        {
            "profile": profile,
            "shop": shop,
            "orders": orders[:100],
            "status_filter": status_filter,
            "status_counts": status_counts,
            "status_choices": Order.STATUS_CHOICES,
            "active_tab": "orders",
        },
    )


@login_required
def shopkeeper_order_action_view(request, order_number):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")
    if request.method != "POST":
        return redirect("shopkeeper_orders")

    action = (request.POST.get("action") or "").strip().casefold()
    accepted_now = False

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().select_related(
                "master_order",
            ),
            order_number=order_number,
            shop=profile.shop,
        )
        current_status = (order.status or "").strip().casefold()

        if action == "accept" and current_status == "pending":
            order.status = "Confirmed"
            order.save(update_fields=["status", "updated_at"])
            order.create_status_history("Confirmed", "Accepted by shop.")
            accepted_now = True
            messages.success(
                request,
                f"Order #{order.order_number} accepted successfully.",
            )

        elif action == "accept" and current_status in {
            "confirmed",
            "preparing",
        }:
            messages.info(
                request,
                f"Order #{order.order_number} is already accepted.",
            )

        elif action == "prepare" and current_status == "confirmed":
            order.status = "Preparing"
            order.save(update_fields=["status", "updated_at"])
            order.create_status_history("Preparing", "Shop started packing.")
            messages.success(request, "Order is being prepared for pickup.")

        elif action == "reject" and current_status in {
            "pending",
            "confirmed",
        }:
            existing_task = OrderPickingTask.objects.filter(order=order).first()
            if existing_task and existing_task.status not in {"WAITING", "CANCELLED"}:
                messages.error(
                    request,
                    "Picker has already started this order, so it cannot be rejected.",
                )
                return redirect("shopkeeper_orders")
            reason = (
                request.POST.get("reason") or "Rejected by shop"
            ).strip()[:100]
            for item in order.items.select_related("product"):
                if item.product_id:
                    product = Product.objects.select_for_update().get(
                        pk=item.product_id,
                    )
                    product.stock_quantity += item.quantity
                    product.save(update_fields=["stock_quantity"])
                    _sync_shop_product_listing(product)

            order.status = "Cancelled"
            order.cancellation_reason = reason
            order.cancellation_description = "Cancelled from shopkeeper app."
            order.cancelled_at = timezone.now()
            order.payment_status = "Refund Pending"
            order.save(
                update_fields=[
                    "status",
                    "cancellation_reason",
                    "cancellation_description",
                    "cancelled_at",
                    "payment_status",
                    "updated_at",
                ]
            )
            order.create_status_history("Cancelled", reason)
            OrderPickingTask.objects.filter(order=order).update(
                status="CANCELLED"
            )
            Settlement.objects.filter(order=order).update(status="On Hold")
            messages.info(request, "Order rejected and stock restored.")

        else:
            messages.error(request, "This order action is not allowed now.")
            return redirect("shopkeeper_orders")

        if order.master_order_id:
            _update_master_order_status(order.master_order)

    if accepted_now:
        try:
            with transaction.atomic():
                accepted_order = (
                    Order.objects
                    .select_related("shop")
                    .prefetch_related("items")
                    .get(pk=order.pk)
                )
                _ensure_order_picking_task(accepted_order)
        except Exception:
            messages.warning(
                request,
                "Order accepted. Picker queue sync will retry automatically.",
            )

    return redirect("shopkeeper_orders")


@login_required
def shopkeeper_inventory_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")
    shop = profile.shop

    moved_quantity = _move_expired_batches_to_bad_inventory(
        shop,
        request.user,
    )
    if moved_quantity:
        messages.warning(
            request,
            f"{moved_quantity} expired item(s) moved to Bad Inventory.",
        )

    query = (request.GET.get("q") or "").strip()
    products = (
        Product.objects
        .filter(shop=shop)
        .select_related("category", "brand")
        .prefetch_related("barcodes")
        .order_by("stock_quantity", "name")
    )
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(barcodes__barcode__icontains=query)
            | Q(brand__name__icontains=query)
        ).distinct()

    bad_records = (
        BadInventoryRecord.objects
        .filter(shop=shop)
        .select_related("product", "batch")[:30]
    )
    bad_loss = sum(
        (record.loss_amount for record in bad_records),
        Decimal("0.00"),
    )
    return render(
        request,
        "customer/shopkeeper_inventory.html",
        {
            "profile": profile,
            "shop": shop,
            "products": products[:200],
            "query": query,
            "bad_records": bad_records,
            "bad_loss": bad_loss,
            "low_stock_count": Product.objects.filter(
                shop=shop,
                is_active=True,
                stock_quantity__lte=5,
            ).count(),
            "out_of_stock_count": Product.objects.filter(
                shop=shop,
                stock_quantity=0,
            ).count(),
            "active_tab": "inventory",
        },
    )


@login_required
def shopkeeper_product_add_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")

    form = ShopkeeperProductForm(
        request.POST or None,
        request.FILES or None,
    )
    if request.method == "POST" and form.is_valid():
        barcode = form.cleaned_data["barcode"]
        if ProductBarcode.objects.filter(
            barcode=barcode,
            product__shop=profile.shop,
        ).exists():
            form.add_error("barcode", "This product is already in your shop.")
        else:
            catalog_product = (
                ProductBarcode.objects
                .filter(barcode=barcode)
                .select_related("product", "product__brand")
                .first()
            )
            with transaction.atomic():
                product = form.save(commit=False)
                product.shop = profile.shop
                product.stock_quantity = form.cleaned_data["opening_stock"]
                brand_name = (form.cleaned_data.get("brand_name") or "").strip()
                if brand_name:
                    product.brand, _ = Brand.objects.get_or_create(
                        name__iexact=brand_name,
                        defaults={"name": brand_name},
                    )
                elif catalog_product and catalog_product.product.brand_id:
                    product.brand = catalog_product.product.brand

                if (
                    not form.cleaned_data.get("image")
                    and catalog_product
                    and catalog_product.product.image
                ):
                    product.image = catalog_product.product.image
                product.save()

                barcode_type = "OTHER"
                if barcode.isdigit() and len(barcode) == 12:
                    barcode_type = "UPC"
                elif barcode.isdigit() and len(barcode) == 13:
                    barcode_type = "EAN"
                elif barcode.isdigit() and len(barcode) == 14:
                    barcode_type = "GTIN"
                ProductBarcode.objects.create(
                    product=product,
                    barcode=barcode,
                    barcode_type=barcode_type,
                    is_primary=True,
                )

                if product.stock_quantity:
                    InventoryBatch.objects.create(
                        shop=profile.shop,
                        product=product,
                        batch_number=form.cleaned_data.get("batch_number", ""),
                        quantity_received=product.stock_quantity,
                        quantity_available=product.stock_quantity,
                        purchase_price=product.cost_price,
                        expiry_date=form.cleaned_data.get("expiry_date"),
                    )
                _sync_shop_product_listing(product)

            messages.success(request, f"{product.name} added to inventory.")
            return redirect("shopkeeper_inventory")

    return render(
        request,
        "customer/shopkeeper_product_form.html",
        {
            "profile": profile,
            "shop": profile.shop,
            "form": form,
            "active_tab": "inventory",
        },
    )


@login_required
def shopkeeper_upc_lookup_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return JsonResponse({"found": False, "error": "Access denied"}, status=403)

    barcode = (request.GET.get("barcode") or "").strip().upper()
    if not barcode:
        return JsonResponse({"found": False, "error": "Enter a barcode."})

    barcode_row = (
        ProductBarcode.objects
        .filter(barcode=barcode)
        .select_related("product", "product__category", "product__brand")
        .order_by("-product__shop_id")
        .first()
    )
    if barcode_row is None:
        return JsonResponse({"found": False, "barcode": barcode})

    product = barcode_row.product
    try:
        image_url = product.image.url if product.image else ""
    except Exception:
        image_url = ""
    return JsonResponse(
        {
            "found": True,
            "barcode": barcode,
            "already_in_shop": ProductBarcode.objects.filter(
                barcode=barcode,
                product__shop=profile.shop,
            ).exists(),
            "product": {
                "name": product.name,
                "description": product.description,
                "category_id": product.category_id,
                "brand_name": product.brand.name if product.brand_id else "",
                "cost_price": str(product.cost_price),
                "price": str(product.price),
                "mrp": str(product.mrp),
                "gst_rate": str(product.gst_rate),
                "image_url": image_url,
            },
        }
    )


@login_required
def shopkeeper_inventory_update_view(request, product_id):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")
    if request.method != "POST":
        return redirect("shopkeeper_inventory")

    product = get_object_or_404(
        Product,
        pk=product_id,
        shop=profile.shop,
    )
    form = ShopkeeperInventoryUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter valid stock and prices.")
        return redirect("shopkeeper_inventory")

    old_stock = product.stock_quantity
    product.stock_quantity = form.cleaned_data["stock_quantity"]
    product.cost_price = form.cleaned_data["cost_price"]
    product.price = form.cleaned_data["price"]
    product.mrp = form.cleaned_data["mrp"]
    product.is_active = form.cleaned_data["is_active"]
    product.save(
        update_fields=[
            "stock_quantity",
            "cost_price",
            "price",
            "mrp",
            "is_active",
        ]
    )
    added_stock = product.stock_quantity - old_stock
    if added_stock > 0:
        InventoryBatch.objects.create(
            shop=profile.shop,
            product=product,
            batch_number="MANUAL-ADJUSTMENT",
            quantity_received=added_stock,
            quantity_available=added_stock,
            purchase_price=product.cost_price,
        )
    _sync_shop_product_listing(product)
    messages.success(request, f"{product.name} inventory updated.")
    return redirect("shopkeeper_inventory")


@login_required
def shopkeeper_bad_stock_view(request, product_id):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")
    if request.method != "POST":
        return redirect("shopkeeper_inventory")

    form = ShopkeeperBadStockForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid bad-stock quantity.")
        return redirect("shopkeeper_inventory")

    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=product_id,
            shop=profile.shop,
        )
        quantity = form.cleaned_data["quantity"]
        if quantity > product.stock_quantity:
            messages.error(request, "Bad stock cannot exceed available stock.")
            return redirect("shopkeeper_inventory")

        product.stock_quantity -= quantity
        product.save(update_fields=["stock_quantity"])
        BadInventoryRecord.objects.create(
            shop=profile.shop,
            product=product,
            quantity=quantity,
            reason=form.cleaned_data["reason"],
            unit_cost=product.cost_price,
            note=form.cleaned_data.get("note", ""),
            created_by=request.user,
        )
        _sync_shop_product_listing(product)

    messages.success(request, "Item moved to Bad Inventory.")
    return redirect("shopkeeper_inventory")


@login_required
def shopkeeper_payments_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")
    shop = profile.shop
    settlements = (
        Settlement.objects
        .filter(shop=shop)
        .select_related("order")
        .order_by("-created_at")
    )
    delivered_items = (
        OrderItem.objects
        .filter(order__shop=shop, order__status="Delivered")
        .select_related("product")
    )
    goods_cost = sum(
        (
            (item.product.cost_price if item.product_id else Decimal("0.00"))
            * item.quantity
            for item in delivered_items
        ),
        Decimal("0.00"),
    )
    bad_records = BadInventoryRecord.objects.filter(shop=shop)
    bad_loss = sum(
        (record.loss_amount for record in bad_records),
        Decimal("0.00"),
    )
    totals = settlements.aggregate(
        product_sales=Sum("product_amount"),
        commission=Sum("shop_commission"),
        payout=Sum("shop_payable"),
        gst=Sum("tax_amount"),
    )
    payout = totals["payout"] or Decimal("0.00")
    return render(
        request,
        "customer/shopkeeper_payments.html",
        {
            "profile": profile,
            "shop": shop,
            "settlements": settlements[:100],
            "total_sales": totals["product_sales"] or Decimal("0.00"),
            "total_commission": totals["commission"] or Decimal("0.00"),
            "total_payout": payout,
            "total_gst": totals["gst"] or Decimal("0.00"),
            "goods_cost": goods_cost,
            "bad_loss": bad_loss,
            "estimated_profit": payout - goods_cost - bad_loss,
            "pending_payout": settlements.exclude(status="Settled").aggregate(
                value=Sum("shop_payable")
            )["value"] or Decimal("0.00"),
            "active_tab": "profile",
        },
    )


@login_required
def shopkeeper_profile_view(request):
    profile = _shopkeeper_app_profile(request)
    if profile is None:
        return redirect("shopkeeper_dashboard")

    form = ShopkeeperProfileSettingsForm(
        request.POST or None,
        instance=profile.shop,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shop profile settings updated.")
        return redirect("shopkeeper_profile")

    return render(
        request,
        "customer/shopkeeper_profile.html",
        {
            "profile": profile,
            "shop": profile.shop,
            "form": form,
            "documents": profile.documents.all(),
            "bank_account": ShopkeeperBankAccount.objects.filter(
                profile=profile
            ).first(),
            "active_tab": "profile",
        },
    )


# =========================================================
# PICKER APP / UPC ORDER PICKING
# =========================================================

def _picker_app_profile(request):
    if request.user.is_staff or getattr(request.user, "role", "") != "PICKER":
        return None
    return (
        PickerProfile.objects
        .filter(user=request.user, is_active=True, shop__is_active=True)
        .select_related("shop", "user")
        .first()
    )


@login_required
def picker_dashboard_view(request):
    profile = _picker_app_profile(request)
    if profile is None:
        messages.error(request, "Active picker profile and shop assignment required.")
        return redirect("home")

    tasks = (
        OrderPickingTask.objects
        .filter(shop=profile.shop)
        .filter(
            Q(status="WAITING")
            | Q(
                picker=request.user,
                status__in=["ACCEPTED", "PICKING", "PACKED"],
            )
        )
        .select_related("order", "order__user", "picker")
        .prefetch_related("picking_items")
        .order_by("created_at")
    )
    return render(
        request,
        "customer/picker_dashboard.html",
        {
            "profile": profile,
            "shop": profile.shop,
            "tasks": tasks,
            "active_tab": "tasks",
            "waiting_count": tasks.filter(status="WAITING").count(),
            "active_count": tasks.filter(
                picker=request.user,
                status__in=["ACCEPTED", "PICKING"],
            ).count(),
        },
    )


@login_required
def picker_accept_task_view(request, order_number):
    profile = _picker_app_profile(request)
    if profile is None:
        return redirect("home")
    if request.method != "POST":
        return redirect("picker_dashboard")

    with transaction.atomic():
        task = get_object_or_404(
            OrderPickingTask.objects.select_for_update().select_related("order"),
            order__order_number=order_number,
            shop=profile.shop,
        )
        if task.status != "WAITING":
            if task.picker_id == request.user.id:
                return redirect(
                    "picker_order_detail",
                    order_number=order_number,
                )
            messages.error(request, "Another picker already accepted this order.")
            return redirect("picker_dashboard")

        task.picker = request.user
        task.status = "ACCEPTED"
        task.accepted_at = timezone.now()
        task.save(
            update_fields=[
                "picker",
                "status",
                "accepted_at",
                "updated_at",
            ]
        )
        if task.order.status == "Confirmed":
            task.order.status = "Preparing"
            task.order.save(update_fields=["status", "updated_at"])
            task.order.create_status_history(
                "Preparing",
                f"Picker {request.user.name} accepted the picking task.",
            )

    messages.success(request, "Picking task accepted. Scan every ordered item.")
    return redirect("picker_order_detail", order_number=order_number)


@login_required
def picker_order_detail_view(request, order_number):
    profile = _picker_app_profile(request)
    if profile is None:
        return redirect("home")

    task = get_object_or_404(
        OrderPickingTask.objects
        .filter(shop=profile.shop, order__order_number=order_number)
        .select_related("order", "order__user", "order__address", "picker")
        .prefetch_related(
            "picking_items",
            "picking_items__order_item",
            "picking_items__order_item__product",
            "picking_items__order_item__product__barcodes",
        ),
    )
    if task.picker_id not in {None, request.user.id}:
        messages.error(request, "This order belongs to another picker.")
        return redirect("picker_dashboard")

    assignment = (
        task.order.delivery_assignments
        .exclude(status="Rejected")
        .select_related("delivery_partner", "delivery_partner__delivery_profile")
        .first()
    )
    if task.status == "PACKED" and assignment is None:
        assignment = _assign_available_rider(task.order)
    return render(
        request,
        "customer/picker_order_detail.html",
        {
            "profile": profile,
            "shop": profile.shop,
            "task": task,
            "picking_items": task.picking_items.all(),
            "assignment": assignment,
            "active_tab": "tasks",
        },
    )


@login_required
def picker_scan_item_view(request, order_number):
    profile = _picker_app_profile(request)
    if profile is None:
        return redirect("home")
    if request.method != "POST":
        return redirect("picker_order_detail", order_number=order_number)

    with transaction.atomic():
        task = get_object_or_404(
            OrderPickingTask.objects.select_for_update().select_related("order"),
            order__order_number=order_number,
            shop=profile.shop,
            picker=request.user,
            status__in=["ACCEPTED", "PICKING"],
        )
        barcode = (request.POST.get("barcode") or "").strip().upper()
        manual_item_id = request.POST.get("picking_item_id")
        try:
            quantity = max(1, int(request.POST.get("quantity") or 1))
        except (TypeError, ValueError):
            quantity = 1

        candidates = list(
            task.picking_items
            .select_for_update()
            .select_related("order_item", "order_item__product")
            .prefetch_related("order_item__product__barcodes")
        )
        picking_item = None
        if manual_item_id:
            picking_item = next(
                (
                    item
                    for item in candidates
                    if str(item.pk) == str(manual_item_id)
                ),
                None,
            )
        elif barcode:
            for item in candidates:
                product = item.order_item.product
                product_barcodes = {
                    row.barcode.upper()
                    for row in product.barcodes.all()
                } if product else set()
                if barcode in product_barcodes and not item.is_complete:
                    picking_item = item
                    break

        if picking_item is None:
            messages.error(request, "Barcode does not match this order.")
            return redirect("picker_order_detail", order_number=order_number)
        if picking_item.is_complete:
            messages.info(request, "This item is already fully picked.")
            return redirect("picker_order_detail", order_number=order_number)

        quantity = min(quantity, picking_item.remaining_quantity)
        picking_item.picked_quantity += quantity
        if barcode:
            picking_item.last_scanned_barcode = barcode
        picking_item.save(
            update_fields=[
                "picked_quantity",
                "last_scanned_barcode",
                "updated_at",
            ]
        )
        task.status = "PICKING"
        task.save(update_fields=["status", "updated_at"])

        all_complete = all(
            item.pk == picking_item.pk and picking_item.is_complete
            or item.pk != picking_item.pk and item.is_complete
            for item in candidates
        )
        if all_complete:
            task.status = "PACKED"
            task.packed_at = timezone.now()
            task.save(
                update_fields=["status", "packed_at", "updated_at"]
            )
            assignment = _assign_available_rider(task.order)
            if assignment:
                messages.success(
                    request,
                    "Order packed. Rider details are now available below.",
                )
            else:
                messages.warning(
                    request,
                    "Order packed. Waiting for an online verified rider.",
                )
        else:
            product_name = (
                picking_item.order_item.product_name
                or picking_item.order_item.product.name
            )
            messages.success(request, f"Picked {quantity} × {product_name}.")

    return redirect("picker_order_detail", order_number=order_number)


def _delivery_incentive_period(incentive, now):
    local_now = timezone.localtime(now)
    current_timezone = timezone.get_current_timezone()

    if incentive.incentive_type == "DAILY":
        period_start = timezone.make_aware(
            datetime.combine(local_now.date(), time.min),
            current_timezone,
        )
        period_end = period_start + timedelta(days=1)
    elif incentive.incentive_type == "WEEKLY":
        week_date = local_now.date() - timedelta(
            days=local_now.weekday()
        )
        period_start = timezone.make_aware(
            datetime.combine(week_date, time.min),
            current_timezone,
        )
        period_end = period_start + timedelta(days=7)
    else:
        period_start = incentive.start_at
        period_end = incentive.end_at or (
            incentive.start_at + timedelta(days=1)
        )

    return period_start, period_end


def _delivery_incentive_cards(delivery_partner):
    now = timezone.now()
    incentives = (
        DeliveryIncentive.objects
        .filter(is_active=True, start_at__lte=now)
        .filter(Q(end_at__isnull=True) | Q(end_at__gte=now))
        .order_by("-start_at")[:6]
    )
    cards = []

    for incentive in incentives:
        period_start, period_end = _delivery_incentive_period(
            incentive,
            now,
        )
        completed_query = DeliveryAssignment.objects.filter(
            delivery_partner=delivery_partner,
            status="Completed",
            completed_at__gte=period_start,
            completed_at__lt=period_end,
        )

        if (
            incentive.incentive_type == "PEAK_HOURS"
            and incentive.peak_start_time
            and incentive.peak_end_time
        ):
            completed_query = completed_query.filter(
                completed_at__time__gte=incentive.peak_start_time,
                completed_at__time__lte=incentive.peak_end_time,
            )

        completed_deliveries = completed_query.count()
        progress, created = (
            DeliveryIncentiveProgress.objects.get_or_create(
                incentive=incentive,
                delivery_partner=delivery_partner,
                period_start=period_start,
                defaults={
                    "period_end": period_end,
                    "completed_deliveries": completed_deliveries,
                },
            )
        )

        update_fields = []

        if progress.period_end != period_end:
            progress.period_end = period_end
            update_fields.append("period_end")

        if progress.completed_deliveries != completed_deliveries:
            progress.completed_deliveries = completed_deliveries
            update_fields.append("completed_deliveries")

        if (
            completed_deliveries >= incentive.required_deliveries
            and progress.status == "IN_PROGRESS"
        ):
            progress.status = "COMPLETED"
            progress.bonus_earned = incentive.bonus_amount
            progress.completed_at = now
            update_fields.extend(
                ["status", "bonus_earned", "completed_at"]
            )

        if update_fields:
            update_fields.append("updated_at")
            progress.save(update_fields=list(dict.fromkeys(update_fields)))

        cards.append(progress)

    return cards

def _delivery_access_allowed(user):
    return (
        getattr(user, "role", "") == "DELIVERY"
        or user.is_staff
    )


def _delivery_assignment_for_user(request, assignment_id, lock=False):
    # PostgreSQL-safe locking: lock only the DeliveryAssignment row.
    # Do not combine SELECT FOR UPDATE with nullable select_related joins
    # such as order__master_order / order__shop.
    queryset = DeliveryAssignment.objects.all()

    if lock:
        queryset = queryset.select_for_update()

    if not request.user.is_staff:
        queryset = queryset.filter(
            delivery_partner=request.user
        )

    return get_object_or_404(
        queryset,
        pk=assignment_id,
    )


@login_required
def delivery_dashboard_view(request):
    if not _delivery_access_allowed(request.user):
        messages.error(request, "Delivery partner access required.")
        return redirect("home")

    if not request.user.is_staff:
        profile = _delivery_profile_for_user(request.user)

        if not profile.can_access_dashboard:
            if profile.verification_status == "DRAFT":
                return redirect(
                    "delivery_onboarding",
                    step=profile.onboarding_step,
                )

            return redirect("delivery_verification_status")

    # ---------------------------------------------------------
    # Dashboard POST actions:
    # - online/offline availability
    # - 24/7 help request
    # - claim/issue submission
    # ---------------------------------------------------------
    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "availability").strip()

        if form_type == "availability":
            if request.user.is_staff:
                messages.info(
                    request,
                    "Staff preview cannot change delivery availability.",
                )
            else:
                request.user.is_active_delivery = (
                    request.POST.get("is_active_delivery") == "1"
                )
                request.user.save(update_fields=["is_active_delivery"])

                messages.success(
                    request,
                    "You are online for deliveries."
                    if request.user.is_active_delivery
                    else "You are offline for deliveries.",
                )

            return redirect("delivery_dashboard")

        if form_type in {"help_request", "claim"}:
            if getattr(request.user, "role", "") != "DELIVERY":
                messages.error(
                    request,
                    "Only delivery partners can submit support requests.",
                )
                return redirect("delivery_dashboard")

            subject = (request.POST.get("subject") or "").strip()
            description = (request.POST.get("description") or "").strip()
            order_number = (
                request.POST.get("order_number") or ""
            ).strip()
            amount_raw = (
                request.POST.get("amount_claimed") or ""
            ).strip()

            if not subject or not description:
                messages.error(
                    request,
                    "Subject and description are required.",
                )
                return redirect("delivery_dashboard")

            related_order = None
            if order_number:
                related_order = (
                    Order.objects
                    .filter(
                        order_number=order_number,
                        delivery_assignments__delivery_partner=request.user,
                    )
                    .distinct()
                    .first()
                )
                if related_order is None:
                    messages.error(
                        request,
                        "Order number was not found in your deliveries.",
                    )
                    return redirect("delivery_dashboard")

            amount_claimed = None
            if form_type == "claim" and amount_raw:
                try:
                    amount_claimed = Decimal(amount_raw)
                    if amount_claimed < 0:
                        raise ValueError
                except Exception:
                    messages.error(
                        request,
                        "Enter a valid claim amount.",
                    )
                    return redirect("delivery_dashboard")

            DeliverySupportRequest.objects.create(
                delivery_partner=request.user,
                request_type=(
                    "CLAIM" if form_type == "claim" else "HELP"
                ),
                order=related_order,
                subject=subject,
                description=description,
                amount_claimed=amount_claimed,
                status="Open",
            )

            messages.success(
                request,
                "Claim submitted successfully."
                if form_type == "claim"
                else "Help request submitted. AMEXA Support will review it.",
            )
            return redirect("delivery_dashboard")

    assignments = (
        DeliveryAssignment.objects
        .select_related(
            "order",
            "order__shop",
            "order__address",
            "delivery_partner",
        )
        .prefetch_related("order__items")
    )

    if not request.user.is_staff:
        assignments = assignments.filter(
            delivery_partner=request.user
        )

    assignments = assignments.order_by("-assigned_at")

    active_assignments = assignments.exclude(
        status__in=["Completed", "Rejected"]
    )

    completed_assignments_qs = assignments.filter(
        status="Completed"
    )

    completed_assignments = completed_assignments_qs[:20]

    # Persistent delivery timers.
    active_assignments = list(active_assignments)
    for assignment in active_assignments:
        if assignment.status == "Assigned":
            timer_started_at = assignment.assigned_at
        elif assignment.status == "Accepted":
            timer_started_at = (
                assignment.accepted_at
                or assignment.assigned_at
            )
        elif (
            assignment.status == "Picked"
            and assignment.order.status != "Out for Delivery"
        ):
            timer_started_at = (
                assignment.picked_at
                or assignment.accepted_at
                or assignment.assigned_at
            )
        elif (
            assignment.status == "Picked"
            and assignment.order.status == "Out for Delivery"
        ):
            timer_started_at = (
                assignment.out_for_delivery_at
                or assignment.picked_at
                or assignment.assigned_at
            )
        else:
            timer_started_at = assignment.assigned_at

        assignment.timer_started_at_ms = int(
            timer_started_at.timestamp() * 1000
        )

    # ---------------------------------------------------------
    # Earnings overview.
    # Existing AMEXA rule: ₹15 delivery payout per completed shop order.
    # ---------------------------------------------------------
    now = timezone.now()
    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    payout_per_delivery = DELIVERY_PARTNER_PAYOUT_PER_SHOP

    today_deliveries = completed_assignments_qs.filter(
        completed_at__gte=today_start
    ).count()
    week_deliveries = completed_assignments_qs.filter(
        completed_at__gte=week_start
    ).count()
    month_deliveries = completed_assignments_qs.filter(
        completed_at__gte=month_start
    ).count()
    all_deliveries = completed_assignments_qs.count()

    today_earnings = payout_per_delivery * today_deliveries
    week_earnings = payout_per_delivery * week_deliveries
    month_earnings = payout_per_delivery * month_deliveries
    total_earnings = payout_per_delivery * all_deliveries

    support_requests = DeliverySupportRequest.objects.none()
    incentive_cards = []
    if getattr(request.user, "role", "") == "DELIVERY":
        support_requests = (
            DeliverySupportRequest.objects
            .filter(delivery_partner=request.user)
            .select_related("order")[:10]
        )
        incentive_cards = _delivery_incentive_cards(request.user)

    context = {
        "active_assignments": active_assignments,
        "completed_assignments": completed_assignments,
        "is_delivery_partner": (
            getattr(request.user, "role", "") == "DELIVERY"
        ),
        "payout_per_delivery": payout_per_delivery,
        "today_deliveries": today_deliveries,
        "week_deliveries": week_deliveries,
        "month_deliveries": month_deliveries,
        "all_deliveries": all_deliveries,
        "today_earnings": today_earnings,
        "week_earnings": week_earnings,
        "month_earnings": month_earnings,
        "total_earnings": total_earnings,
        "incentive_cards": incentive_cards,
        "support_requests": support_requests,
    }

    return render(
        request,
        "customer/delivery_dashboard.html",
        context,
    )


@login_required
def delivery_profile_view(request):
    if not _delivery_access_allowed(request.user):
        messages.error(request, "Delivery partner access required.")
        return redirect("home")

    profile = _delivery_profile_for_user(request.user)

    if not request.user.is_staff and not profile.can_access_dashboard:
        if profile.verification_status == "DRAFT":
            return redirect(
                "delivery_onboarding",
                step=profile.onboarding_step,
            )
        return redirect("delivery_verification_status")

    bank_account = (
        DeliveryPartnerBankAccount.objects
        .filter(profile=profile)
        .first()
    )

    documents = profile.documents.all().order_by("document_type")

    assignments = DeliveryAssignment.objects.filter(
        delivery_partner=request.user
    )

    completed_assignments = assignments.filter(status="Completed")

    now = timezone.now()
    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    payout_per_delivery = DELIVERY_PARTNER_PAYOUT_PER_SHOP

    today_deliveries = completed_assignments.filter(
        completed_at__gte=today_start
    ).count()
    week_deliveries = completed_assignments.filter(
        completed_at__gte=week_start
    ).count()
    month_deliveries = completed_assignments.filter(
        completed_at__gte=month_start
    ).count()
    all_deliveries = completed_assignments.count()

    context = {
        "profile": profile,
        "bank_account": bank_account,
        "documents": documents,
        "payout_per_delivery": payout_per_delivery,
        "today_deliveries": today_deliveries,
        "week_deliveries": week_deliveries,
        "month_deliveries": month_deliveries,
        "all_deliveries": all_deliveries,
        "today_earnings": payout_per_delivery * today_deliveries,
        "week_earnings": payout_per_delivery * week_deliveries,
        "month_earnings": payout_per_delivery * month_deliveries,
        "total_earnings": payout_per_delivery * all_deliveries,
        "support_count": DeliverySupportRequest.objects.filter(
            delivery_partner=request.user
        ).count(),
        "open_support_count": DeliverySupportRequest.objects.filter(
            delivery_partner=request.user,
            status__in=["Open", "In Review"],
        ).count(),
    }

    return render(
        request,
        "customer/delivery_profile.html",
        context,
    )


@login_required
def delivery_assignment_action_view(request, assignment_id):
    if not _delivery_access_allowed(request.user):
        messages.error(request, "Delivery partner access required.")
        return redirect("home")

    if request.method != "POST":
        return redirect("delivery_dashboard")

    action = (request.POST.get("action") or "").strip().lower()
    entered_otp = (request.POST.get("delivery_otp") or "").strip()

    with transaction.atomic():
        assignment = _delivery_assignment_for_user(
            request,
            assignment_id,
            lock=True,
        )

        order = (
            Order.objects
            .select_for_update()
            .get(pk=assignment.order_id)
        )

        if order.status == "Cancelled":
            messages.error(request, "This order is cancelled.")
            return redirect("delivery_dashboard")

        if assignment.status == "Completed":
            messages.info(request, "Delivery is already completed.")
            return redirect("delivery_dashboard")

        if assignment.status == "Rejected":
            messages.info(request, "This assignment was rejected.")
            return redirect("delivery_dashboard")

        if action == "accept":
            if assignment.status != "Assigned":
                messages.info(request, "Assignment is already processed.")
                return redirect("delivery_dashboard")

            assignment.status = "Accepted"
            assignment.accepted_at = timezone.now()
            assignment.save(update_fields=["status", "accepted_at"])

            if order.status == "Pending":
                order.status = "Confirmed"
                order.save(update_fields=["status", "updated_at"])
                order.create_status_history(
                    "Confirmed",
                    "Delivery partner accepted the assignment.",
                )

            if order.master_order:
                _update_master_order_status(order.master_order)

            messages.success(request, "Order accepted.")

        elif action == "reject":
            if assignment.status not in {"Assigned", "Accepted"}:
                messages.error(
                    request,
                    "This assignment can no longer be rejected.",
                )
                return redirect("delivery_dashboard")

            assignment.status = "Rejected"
            assignment.save(update_fields=["status"])

            messages.info(request, "Assignment rejected.")

        elif action == "picked":
            if assignment.status != "Accepted":
                messages.error(
                    request,
                    "Accept the order before pickup.",
                )
                return redirect("delivery_dashboard")

            assignment.status = "Picked"
            assignment.picked_at = timezone.now()
            assignment.save(update_fields=["status", "picked_at"])

            if order.status in {"Pending", "Confirmed"}:
                order.status = "Preparing"
                order.save(update_fields=["status", "updated_at"])
                order.create_status_history(
                    "Preparing",
                    "Order picked up by delivery partner.",
                )

            if not order.delivery_otp:
                order.delivery_otp = f"{random.randint(0, 999999):06d}"
                order.save(
                    update_fields=["delivery_otp", "updated_at"]
                )

            if order.master_order:
                _update_master_order_status(order.master_order)

            messages.success(
                request,
                "Order picked up. Delivery OTP is now active.",
            )

        elif action == "out_for_delivery":
            if assignment.status != "Picked":
                messages.error(
                    request,
                    "Mark the order as picked up first.",
                )
                return redirect("delivery_dashboard")

            if order.status == "Delivered":
                messages.info(request, "Order is already delivered.")
                return redirect("delivery_dashboard")

            if not order.delivery_otp:
                order.delivery_otp = f"{random.randint(0, 999999):06d}"

            if assignment.out_for_delivery_at is None:
                assignment.out_for_delivery_at = timezone.now()
                assignment.save(update_fields=["out_for_delivery_at"])

            order.status = "Out for Delivery"
            order.save(
                update_fields=[
                    "status",
                    "delivery_otp",
                    "updated_at",
                ]
            )
            order.create_status_history(
                "Out for Delivery",
                "Delivery partner is on the way.",
            )

            if order.master_order:
                _update_master_order_status(order.master_order)

            messages.success(
                request,
                "Order is now Out for Delivery. Start live GPS tracking.",
            )

        elif action == "complete":
            if assignment.status != "Picked":
                messages.error(
                    request,
                    "Order must be picked up before delivery.",
                )
                return redirect("delivery_dashboard")

            if order.status != "Out for Delivery":
                messages.error(
                    request,
                    "Mark the order Out for Delivery first.",
                )
                return redirect("delivery_dashboard")

            if not order.delivery_otp:
                messages.error(
                    request,
                    "Delivery OTP is not available for this order.",
                )
                return redirect("delivery_dashboard")

            if entered_otp != order.delivery_otp:
                messages.error(request, "Incorrect delivery OTP.")
                return redirect("delivery_dashboard")

            assignment.status = "Completed"
            assignment.completed_at = timezone.now()
            assignment.save(
                update_fields=[
                    "status",
                    "completed_at",
                ]
            )

            # Saving Delivered triggers the existing wallet signal.
            # Coins are credited only when every child order is Delivered.
            order.status = "Delivered"

            if order.payment_method == "COD":
                order.payment_status = "Paid"
                order.save(
                    update_fields=[
                        "status",
                        "payment_status",
                        "updated_at",
                    ]
                )
            else:
                order.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            order.create_status_history(
                "Delivered",
                "Delivery completed after OTP verification.",
            )

            if order.master_order:
                _update_master_order_status(order.master_order)

                try:
                    payment = order.master_order.payment
                except Payment.DoesNotExist:
                    payment = None

                if (
                    payment
                    and payment.payment_method == "COD"
                    and order.master_order.status == "Completed"
                ):
                    payment.payment_status = "Paid"
                    payment.paid_at = timezone.now()
                    payment.save(
                        update_fields=[
                            "payment_status",
                            "paid_at",
                            "updated_at",
                        ]
                    )

            messages.success(
                request,
                "Delivery OTP verified. Order delivered successfully.",
            )

        else:
            messages.error(request, "Invalid delivery action.")

    return redirect("delivery_dashboard")

