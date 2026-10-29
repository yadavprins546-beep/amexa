
from django import forms
from django.contrib import admin, messages
from decimal import Decimal
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from .models import (
    IndiaOrder,
    IndiaOrderItem,
    IndiaOrderNotification,
    IndiaProductReview,
    IndiaShoppingSettings,
    IndiaWishlistItem,
    IndiaOrderReward,
    IndiaCoinTransaction,
    IndiaReturnRequest,
    IndiaCart,
    IndiaCartItem,
    IndiaCategory,
    IndiaProduct,
    ResellingProduct,
    FinancePayable,
    FinanceTransaction,
)

from .notifications import notify_order_status
from .rewards import grant_delivery_rewards
from .stock_services import release_order_stock


@admin.register(IndiaCategory)
class IndiaCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "sort_order",
        "is_active",
        "show_on_home",
        "coming_soon",
    )
    list_filter = ("is_active", "show_on_home", "coming_soon")
    search_fields = ("name", "slug", "banner_title")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("sort_order", "is_active", "show_on_home", "coming_soon")
    ordering = ("sort_order", "name")
    list_per_page = 25

    fieldsets = (
        ("Category Details", {
            "fields": ("name", "slug", "icon", "image")
        }),
        ("Category Banner", {
            "fields": ("banner_image", "banner_title", "banner_subtitle")
        }),
        ("Display Settings", {
            "fields": ("sort_order", "is_active", "show_on_home", "coming_soon")
        }),
        ("System Information", {
            "fields": ("created_at",),
        }),
    )
    readonly_fields = ("created_at",)



@admin.register(IndiaProduct)
class IndiaProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "selling_price",
        "mrp",
        "discount_percent",
        "stock",
        "show_sale_badge",
        "is_featured",
        "is_active",
    )

    list_filter = (
        "category",
        "show_sale_badge",
        "is_featured",
        "is_active",
    )

    search_fields = ("name", "description", "sale_badge_text")
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25

    list_editable = (
        "show_sale_badge",
        "is_featured",
        "is_active",
    )

    fieldsets = (
        ("Product Details", {
            "fields": (
                "category",
                "name",
                "slug",
                "description",
                "image",
            )
        }),
        ("Pricing and Inventory", {
            "fields": ("mrp", "selling_price", "stock")
        }),
        ("Sale Badge Controls", {
            "fields": (
                "show_sale_badge",
                "sale_badge_text",
                "sale_start_at",
                "sale_end_at",
            )
        }),
        ("Product Discovery", {
            "fields": (
                "is_featured",
                "show_new_arrival_badge",
                "show_bestseller_badge",
                "show_trending_badge",
            )
        }),
        ("Visibility", {
            "fields": ("is_active",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    readonly_fields = ("created_at", "updated_at")


class ResellingStockSignalFilter(admin.SimpleListFilter):
    title = "Stock signal"
    parameter_name = "stock_signal"

    def lookups(self, request, model_admin):
        return (
            ("unknown", "Quantity not recorded"),
            ("low", "At or below reorder level"),
            ("ok", "Above reorder level"),
        )

    def queryset(self, request, queryset):
        if self.value() == "unknown":
            return queryset.filter(
                Q(fulfillment_method="byxom", inventory_quantity__isnull=True)
                | Q(fulfillment_method="supplier", source_quantity__isnull=True)
            )
        if self.value() == "low":
            return queryset.filter(
                Q(
                    fulfillment_method="byxom",
                    inventory_quantity__isnull=False,
                    inventory_quantity__lte=F("reorder_level"),
                )
                | Q(
                    fulfillment_method="supplier",
                    source_quantity__isnull=False,
                    source_quantity__lte=F("source_reorder_level"),
                )
            )
        if self.value() == "ok":
            return queryset.filter(
                Q(
                    fulfillment_method="byxom",
                    inventory_quantity__gt=F("reorder_level"),
                )
                | Q(
                    fulfillment_method="supplier",
                    source_quantity__gt=F("source_reorder_level"),
                )
            )
        return queryset


@admin.register(ResellingProduct)
class ResellingProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "inventory_quantity",
        "reorder_level",
        "source_quantity",
        "source_reorder_level",
        "stock_signal_display",
        "sourcing_cost",
        "selling_price",
        "estimated_gross_margin",
        "source_name",
        "stock_checked_at",
        "source_status",
        "listing_status",
        "show_sale_badge",
        "is_featured",
    )

    list_filter = (
        "category",
        "source_status",
        "fulfillment_method",
        ResellingStockSignalFilter,
        "listing_status",
        "show_sale_badge",
        "is_featured",
        "show_new_arrival_badge",
        "show_bestseller_badge",
        "show_trending_badge",
    )

    search_fields = (
        "name",
        "description",
        "source_name",
        "sale_badge_text",
    )

    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25
    date_hierarchy = "created_at"

    list_editable = (
        "inventory_quantity",
        "source_quantity",
        "source_status",
        "listing_status",
        "show_sale_badge",
        "is_featured",
    )

    fieldsets = (
        ("Product Details", {
            "fields": (
                "name",
                "slug",
                "category",
                "description",
                "image",
                "image_2",
                "image_3",
            )
        }),
        ("Supplier and Source", {
            "fields": (
                "source_name",
                "source_url",
                "source_status",
                "stock_checked_at",
                "source_quantity",
                "source_reorder_level",
                "stock_check_notes",
                "fulfillment_method",
            )
        }),
        ("Pricing and Margin", {
            "fields": (
                "sourcing_cost",
                "mrp",
                "selling_price",
                "estimated_gross_margin",
            )
        }),
        ("Sale Badge Controls", {
            "fields": (
                "show_sale_badge",
                "sale_badge_text",
                "sale_start_at",
                "sale_end_at",
            )
        }),
        ("Product Discovery", {
            "fields": (
                "is_featured",
                "show_new_arrival_badge",
                "show_bestseller_badge",
                "show_trending_badge",
            )
        }),
        ("BYXOM Inventory", {
            "fields": ("inventory_quantity", "reorder_level")
        }),
        ("Listing Status", {
            "fields": ("listing_status",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Stock Signal")
    def stock_signal_display(self, obj):
        if obj.fulfillment_method == "supplier":
            quantity = obj.source_quantity
            threshold = obj.source_reorder_level
            label = "Supplier"
        else:
            quantity = obj.inventory_quantity
            threshold = obj.reorder_level
            label = "BYXOM"

        if quantity is None:
            return f"{label}: NOT RECORDED"
        if quantity <= threshold:
            return f"{label}: LOW"
        return f"{label}: OK"

    def save_model(self, request, obj, form, change):
        # Record when supplier stock details/status were manually checked.
        supplier_fields = {"source_quantity", "source_status", "stock_check_notes"}
        if obj.fulfillment_method == "supplier" and supplier_fields.intersection(form.changed_data):
            obj.stock_checked_at = timezone.now()
        super().save_model(request, obj, form, change)

    readonly_fields = (
        "created_at",
        "updated_at",
        "estimated_gross_margin",
    )


@admin.register(FinancePayable)
class FinancePayableAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient_name",
        "recipient_type",
        "amount_due",
        "amount_paid",
        "balance_due",
        "payment_status",
        "due_date",
    )

    list_filter = ("recipient_type", "due_date")

    search_fields = (
        "recipient_name",
        "invoice_reference",
        "order_reference",
    )

    readonly_fields = (
        "amount_paid",
        "balance_due",
        "payment_status",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Recipient Details", {
            "fields": (
                "recipient_type",
                "recipient_name",
                "invoice_reference",
                "order_reference",
                "reselling_product",
            )
        }),
        ("Amount and Due Date", {
            "fields": ("amount_due", "due_date", "notes")
        }),
        ("Payment Summary", {
            "fields": (
                "amount_paid",
                "balance_due",
                "payment_status",
            )
        }),
        ("Record Information", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    list_per_page = 25


@admin.register(FinanceTransaction)
class FinanceTransactionAdmin(admin.ModelAdmin):
    change_list_template = (
        "admin/india_store/financetransaction/change_list.html"
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        transactions = FinanceTransaction.objects.all()

        def total(queryset):
            return (
                queryset.aggregate(value=Sum("amount"))["value"]
                or Decimal("0.00")
            )

        extra_context["finance_summary"] = {
            "verified_incoming": total(
                transactions.filter(
                    direction="incoming",
                    status="successful",
                    is_verified=True,
                )
            ),
            "verified_outgoing": total(
                transactions.filter(
                    direction="outgoing",
                    status="successful",
                    is_verified=True,
                )
            ),
            "pending_incoming": total(
                transactions.filter(
                    direction="incoming",
                    status__in=["pending", "processing"],
                )
            ),
            "pending_outgoing": total(
                transactions.filter(
                    direction="outgoing",
                    status__in=["pending", "processing"],
                )
            ),
            "unverified_incoming": total(
                transactions.filter(
                    direction="incoming",
                    status="successful",
                    is_verified=False,
                )
            ),
            "unverified_outgoing": total(
                transactions.filter(
                    direction="outgoing",
                    status="successful",
                    is_verified=False,
                )
            ),
            "unverified_successful_count": transactions.filter(
                status="successful",
                is_verified=False,
            ).count(),
            "pending_payables": sum(
                (
                    payable.balance_due
                    for payable in FinancePayable.objects.all()
                ),
                Decimal("0.00"),
            ),
        }

        return super().changelist_view(
            request,
            extra_context=extra_context,
        )


    list_display = (
        "id",
        "transaction_date",
        "direction",
        "transaction_type",
        "party_name",
        "amount",
        "payment_method",
        "status",
        "transaction_reference",
        "is_verified",
    )

    list_filter = (
        "direction",
        "transaction_type",
        "status",
        "payment_method",
        "payment_source",
        "party_type",
        "is_verified",
    )

    search_fields = (
        "party_name",
        "transaction_reference",
        "order_reference",
        "payment_provider",
    )

    readonly_fields = (
        "is_verified",
        "verified_at",
        "verified_by",
        "created_by",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Transaction Details", {
            "fields": (
                "direction",
                "transaction_type",
                "status",
                "amount",
                "transaction_date",
            )
        }),
        ("Payment Party and Source", {
            "fields": (
                "party_type",
                "party_name",
                "payment_method",
                "payment_source",
                "payment_provider",
            )
        }),
        ("References", {
            "fields": (
                "transaction_reference",
                "order_reference",
                "payable",
                "reselling_product",
            )
        }),
        ("Verification", {
            "fields": (
                "is_verified",
                "verified_at",
                "verified_by",
            )
        }),
        ("Notes and Audit", {
            "fields": (
                "notes",
                "created_by",
                "created_at",
                "updated_at",
            )
        }),
    )

    list_per_page = 25
    date_hierarchy = "created_at"

    actions = ["verify_confirmed_transactions"]

    @admin.action(
        description="Verify selected transactions matched against bank/gateway records"
    )
    def verify_confirmed_transactions(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only a superuser can verify financial transactions.",
                level=messages.ERROR,
            )
            return

        eligible = queryset.filter(
            status="successful",
            payment_source__in=[
                "bank_statement",
                "gateway_webhook",
            ],
            is_verified=False,
        ).exclude(
            transaction_reference__isnull=True
        ).exclude(
            transaction_reference__exact=""
        )

        verified_count = eligible.update(
            is_verified=True,
            verified_at=timezone.now(),
            verified_by=request.user,
        )

        skipped_count = queryset.count() - verified_count

        if verified_count:
            self.message_user(
                request,
                f"{verified_count} transaction(s) verified. "
                f"{skipped_count} skipped because they did not meet "
                "the verification requirements.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No transactions were verified. Confirm that selected "
                "records are successful, have a transaction reference, "
                "and match a bank statement or verified gateway record.",
                level=messages.WARNING,
            )

class IndiaCartItemInline(admin.TabularInline):
    model = IndiaCartItem
    extra = 0
    fields = ("product", "own_product", "quantity", "price", "line_total", "created_at", "updated_at")
    readonly_fields = ("price", "line_total", "created_at", "updated_at")


@admin.register(IndiaCart)
class IndiaCartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "item_count", "subtotal", "updated_at")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at", "item_count", "subtotal")
    inlines = [IndiaCartItemInline]



class IndiaOrderItemInline(admin.TabularInline):
    model = IndiaOrderItem
    extra = 0
    fields = (
        "product", "own_product", "product_name", "quantity", "price", "line_total",
        "stock_pool", "stock_deducted", "stock_restored",
        "stock_deducted_at", "stock_restored_at",
    )
    readonly_fields = fields


class IndiaStockBlockedFilter(admin.SimpleListFilter):
    title = "stock reservation"
    parameter_name = "stock_blocked"

    def lookups(self, request, model_admin):
        return (("blocked", "Blocked - needs stock review"),)

    def queryset(self, request, queryset):
        if self.value() != "blocked":
            return queryset

        active_statuses = ("Pending", "Confirmed", "Processing", "Shipped")
        return queryset.filter(
            status__in=active_statuses
        ).filter(
            Q(items__isnull=True)
            | Q(items__stock_deducted=False)
            | Q(items__stock_pool__in=("none", ""))
            | Q(items__stock_restored=True)
        ).distinct()


@admin.register(IndiaOrder)
class IndiaOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "payment_method",
        "payment_status",
        "total_amount",
        "courier_name",
        "tracking_number",
        "supplier_order_id",
        "supplier_cost",
        "discount_amount",
        "verified_payment_method",
        "delivered_at",
        "created_at",
    )
    list_filter = (
        "status",
        "payment_method",
        "payment_status",
        "supplier_platform",
        "created_at",
        IndiaStockBlockedFilter,
    )
    search_fields = ("order_number", "user__email", "address__pincode", "supplier_order_id")
    readonly_fields = (
        "order_number",
        "user",
        "address",
        "shipping_full_name",
        "shipping_mobile",
        "shipping_address_line",
        "shipping_city",
        "shipping_state",
        "shipping_pincode",
        "status",
        "payment_method",
        "payment_status",
        "subtotal",
        "delivery_fee",
        "total_amount",
        "razorpay_order_id",
        "razorpay_payment_id",
        "razorpay_amount_paise",
        "discount_amount",
        "verified_payment_method",
        "delivered_at",
        "created_at",
        "updated_at",
        "customer_confirmed_at",
        "supplier_ordered_at",
    )

    def save_model(self, request, obj, form, change):
        if obj.supplier_order_id and not obj.supplier_ordered_at:
            obj.supplier_ordered_at = timezone.now()
        super().save_model(request, obj, form, change)

    actions = [
        "confirm_pending_orders",
        "cancel_pending_orders",
        "start_processing_orders",
        "mark_orders_shipped",
        "mark_orders_delivered",
        "process_delivery_rewards",
    ]

    def _apply_india_order_status_transition(
        self, request, queryset, source_status, target_status, label
    ):
        selected_count = queryset.count()

        # BYXOM-ORDER-PAYMENT-GATE-V1
        eligible_queryset = queryset.filter(status=source_status)
        if target_status in ("Confirmed", "Processing", "Shipped", "Delivered"):
            eligible_queryset = eligible_queryset.filter(
                Q(
                    payment_method="COD",
                    payment_status__in=("Pending", "Paid"),
                )
                | Q(
                    payment_method="ONLINE",
                    payment_status="Paid",
                )
            )

        eligible = list(eligible_queryset)
        changed_count = 0
        stock_blocked_count = 0

        with transaction.atomic():
            for order in eligible:
                # BYXOM-ORDER-STOCK-GATE-V1
                if target_status in ("Confirmed", "Processing", "Shipped", "Delivered"):
                    order_items = list(order.items.select_for_update().all())
                    if not order_items or any(
                        not item.stock_deducted
                        or item.stock_pool not in ("byxom", "supplier", "own")
                        or item.stock_restored
                        for item in order_items
                    ):
                        stock_blocked_count += 1
                        continue
                order.status = target_status
                if target_status == "Delivered":
                    order.delivered_at = order.delivered_at or timezone.now()
                    order.save(
                        update_fields=["status", "delivered_at", "updated_at"]
                    )
                    grant_delivery_rewards(order)
                else:
                    order.save(update_fields=["status", "updated_at"])
                notify_order_status(order)
                changed_count += 1

        if changed_count:
            self.message_user(
                request,
                f"{changed_count} order(s) updated to {label}. Payment status was not changed.",
                level=messages.SUCCESS,
            )

        if stock_blocked_count:
            self.message_user(
                request,
                f"{stock_blocked_count} order(s) blocked: product items missing or stock reservation incomplete/restored.",
                level=messages.ERROR,
            )

        skipped_count = selected_count - changed_count
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} order(s) skipped because status, payment, or stock checks did not allow this transition.",
                level=messages.WARNING,
            )

    @admin.action(description="Confirm selected Pending orders after customer call")
    def confirm_pending_orders(self, request, queryset):
        pending_ids = list(
            queryset.filter(status="Pending").values_list("pk", flat=True)
        )
        self._apply_india_order_status_transition(
            request, queryset, "Pending", "Confirmed", "Confirmed"
        )
        if pending_ids:
            timestamp = timezone.now()
            IndiaOrder.objects.filter(
                pk__in=pending_ids,
                status="Confirmed",
                customer_confirmed_at__isnull=True,
            ).update(
                customer_confirmed_at=timestamp,
                updated_at=timestamp,
            )

    @admin.action(description="Cancel selected Pending COD orders when customer declines")
    def cancel_pending_orders(self, request, queryset):
        selected_count = queryset.count()
        changed_count = 0

        with transaction.atomic():
            eligible = list(
                queryset.select_for_update().filter(
                    status="Pending",
                    payment_method="COD",
                    payment_status="Pending",
                    supplier_order_id="",
                )
            )
            for order in eligible:
                release_order_stock(order)
                order.status = "Cancelled"
                order.save(update_fields=["status", "updated_at"])
                notify_order_status(order)
                changed_count += 1

        if changed_count:
            self.message_user(
                request,
                f"{changed_count} pending COD order(s) cancelled. Payment status was not changed.",
                level=messages.SUCCESS,
            )
        skipped_count = selected_count - changed_count
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} order(s) skipped. Only unpaid Pending COD orders with no supplier order ID can be cancelled by this action.",
                level=messages.WARNING,
            )

    @admin.action(description="Start processing after supplier order ID or for own-stock-only orders")
    def start_processing_orders(self, request, queryset):
        confirmed = list(queryset.filter(status="Confirmed"))
        ready_ids = []
        missing_id_count = 0

        for order in confirmed:
            if (order.supplier_order_id or "").strip():
                ready_ids.append(order.pk)
                continue

            has_reseller_line = order.items.filter(product__isnull=False).exists()
            has_own_line = order.items.filter(own_product__isnull=False).exists()
            if has_own_line and not has_reseller_line:
                ready_ids.append(order.pk)
            else:
                missing_id_count += 1

        if missing_id_count:
            self.message_user(
                request,
                f"{missing_id_count} confirmed reseller/mixed order(s) skipped: enter the supplier order ID first.",
                level=messages.WARNING,
            )

        ready = queryset.filter(pk__in=ready_ids)
        self._apply_india_order_status_transition(
            request, ready, "Confirmed", "Processing", "Processing"
        )

    @admin.action(description="Mark selected Processing orders as Shipped")
    def mark_orders_shipped(self, request, queryset):
        self._apply_india_order_status_transition(
            request, queryset, "Processing", "Shipped", "Shipped"
        )

    @admin.action(description="Mark selected Shipped orders as Delivered")
    def mark_orders_delivered(self, request, queryset):
        self._apply_india_order_status_transition(
            request, queryset, "Shipped", "Delivered", "Delivered"
        )

    @admin.action(description="Process rewards/gift entitlements for Delivered orders")
    def process_delivery_rewards(self, request, queryset):
        selected_count = queryset.count()
        eligible = list(
            queryset.filter(status="Delivered", delivered_at__isnull=False)
        )
        processed_count = 0

        with transaction.atomic():
            for order in eligible:
                grant_delivery_rewards(order)
                processed_count += 1

        if processed_count:
            self.message_user(
                request,
                f"Processed reward/gift rules for {processed_count} Delivered order(s). "
                "Order status and payment status were not changed.",
                level=messages.SUCCESS,
            )

        skipped_count = selected_count - processed_count
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} order(s) skipped. Only Delivered orders with a "
                "recorded delivery date are eligible.",
                level=messages.WARNING,
            )

    inlines = [IndiaOrderItemInline]


@admin.register(IndiaProductReview)
class IndiaProductReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "rating",
        "title",
        "is_approved",
        "created_at",
    )
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("product__name", "user__email", "title", "body")
    list_editable = ("is_approved",)
    list_per_page = 25
    readonly_fields = ("user", "product", "order_item", "created_at", "updated_at")
    fields = (
        "user", "product", "order_item", "rating", "title", "body",
        "is_approved", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        # Reviews are created by customers after eligible deliveries.
        return False

    @admin.action(description="Approve selected reviews")
    def approve_selected_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Hide selected reviews")
    def hide_selected_reviews(self, request, queryset):
        queryset.update(is_approved=False)

    actions = ("approve_selected_reviews", "hide_selected_reviews")


@admin.register(IndiaOrderNotification)
class IndiaOrderNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "order",
        "event",
        "is_read",
        "created_at",
    )
    list_filter = ("event", "is_read", "created_at")
    search_fields = (
        "title",
        "message",
        "order__order_number",
    )
    list_select_related = ("user", "order")
    readonly_fields = (
        "user",
        "order",
        "event",
        "title",
        "message",
        "is_read",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# BYXOM FEATURE ADMIN CONTROLS
@admin.register(IndiaShoppingSettings)
class IndiaShoppingSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "coins_enabled", "diwali_gift_enabled",
        "return_window_days", "card_discount_enabled",
        "card_discount_percent", "updated_at",
    )
    readonly_fields = ("updated_at",)
    fieldsets = (
        ("Coin Rewards", {
            "fields": ("coins_enabled",),
        }),
        ("Diwali Gift", {
            "fields": (
                "diwali_gift_enabled",
                "diwali_gift_name",
                "diwali_gift_description",
            ),
        }),
        ("Returns", {
            "fields": ("return_window_days",),
        }),
        ("Card Discount", {
            "fields": ("card_discount_enabled", "card_discount_percent"),
        }),
        ("System", {
            "fields": ("updated_at",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk=1)

    def has_add_permission(self, request):
        if self.model.objects.filter(pk=1).exists():
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.pk != 1:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IndiaOrderReward)
class IndiaOrderRewardAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "customer_email", "coins_awarded",
        "coins_awarded_at", "gift_status", "gift_shipped_at",
    )
    list_filter = ("gift_status", "coins_awarded_at", "created_at")
    search_fields = ("order__order_number", "order__user__email", "gift_name")
    readonly_fields = (
        "order", "coins_awarded", "coins_awarded_at", "gift_shipped_at",
        "created_at", "updated_at",
    )
    fields = (
        "order", "coins_awarded", "coins_awarded_at",
        "gift_name", "gift_description", "gift_status",
        "gift_shipped_at", "created_at", "updated_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 25

    @admin.display(description="Order Number", ordering="order__order_number")
    def order_number(self, obj):
        return obj.order.order_number

    @admin.display(description="Customer", ordering="order__user__email")
    def customer_email(self, obj):
        return getattr(obj.order.user, "email", str(obj.order.user))

    # BYXOM-GIFT-SHIP-TIMESTAMP-V1
    def save_model(self, request, obj, form, change):
        if obj.gift_status in ("SHIPPED", "DELIVERED") and not obj.gift_shipped_at:
            obj.gift_shipped_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(IndiaCoinTransaction)
class IndiaCoinTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer_email", "order_number", "transaction_type",
        "reason", "coins", "balance_after", "created_at",
    )
    list_filter = ("transaction_type", "reason", "created_at")
    search_fields = (
        "wallet__user__email", "order__order_number",
        "idempotency_key", "description",
    )
    readonly_fields = (
        "wallet", "order", "transaction_type", "reason", "coins",
        "balance_after", "idempotency_key", "description", "created_at",
    )
    fields = readonly_fields
    date_hierarchy = "created_at"
    list_per_page = 50

    @admin.display(description="Customer", ordering="wallet__user__email")
    def customer_email(self, obj):
        return getattr(obj.wallet.user, "email", str(obj.wallet.user))

    @admin.display(description="Order Number", ordering="order__order_number")
    def order_number(self, obj):
        return obj.order.order_number

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class IndiaReturnRequestAdminForm(forms.ModelForm):
    class Meta:
        model = IndiaReturnRequest
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get("status")

        old_status = None
        if self.instance.pk:
            old_status = (
                IndiaReturnRequest.objects
                .filter(pk=self.instance.pk)
                .values_list("status", flat=True)
                .first()
            )

        if (
            old_status in ("REFUNDED", "CLOSED")
            and new_status != old_status
        ):
            self.add_error(
                "status",
                "This return is finalized. Its final status cannot be changed here.",
            )
            return cleaned

        if new_status == "REFUNDED" and old_status != "REFUNDED":
            if old_status != "RECEIVED":
                self.add_error(
                    "status",
                    "A return must reach Item Received before it can be marked Refunded.",
                )
                return cleaned

            finance_tx = cleaned.get("refund_finance_transaction")
            if finance_tx is None:
                self.add_error(
                    "refund_finance_transaction",
                    "Select a verified refund transaction before finalizing this return.",
                )
                return cleaned

            order = self.instance.order
            problems = []

            if finance_tx.direction != "outgoing":
                problems.append("transaction direction must be Money Out")
            if finance_tx.transaction_type != "customer_refund":
                problems.append("transaction type must be Customer Refund")
            if finance_tx.status != "successful":
                problems.append("transaction must be Successful")
            if not finance_tx.is_verified:
                problems.append("transaction must be verified")
            if finance_tx.payment_source not in ("bank_statement", "gateway_webhook"):
                problems.append("source must be a bank statement or verified gateway event")
            if not (finance_tx.transaction_reference or "").strip():
                problems.append("transaction reference is missing")
            if (finance_tx.order_reference or "").strip() != order.order_number:
                problems.append("transaction order reference does not match this order")
            if finance_tx.amount is None or finance_tx.amount <= 0:
                problems.append("refund transaction amount must be positive")

            if problems:
                self.add_error(
                    "refund_finance_transaction",
                    "Refund transaction rejected: " + "; ".join(problems) + ".",
                )

        return cleaned


@admin.register(IndiaReturnRequest)
class IndiaReturnRequestAdmin(admin.ModelAdmin):
    form = IndiaReturnRequestAdminForm

    list_display = (
        "id",
        "order_number",
        "product_name",
        "customer_email",
        "quantity",
        "status",
        "refund_amount_display",
        "refund_reference_display",
        "created_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = (
        "order__order_number",
        "order_item__product_name",
        "user__email",
        "reason",
        "refund_finance_transaction__transaction_reference",
    )
    readonly_fields = (
        "order",
        "order_item",
        "user",
        "quantity",
        "reason",
        "refund_amount_display",
        "refund_reference_display",
        "refund_processed_at",
        "refund_verified_by",
        "created_at",
        "updated_at",
    )
    fields = (
        "order",
        "order_item",
        "user",
        "quantity",
        "reason",
        "status",
        "admin_note",
        "refund_finance_transaction",
        "refund_amount_display",
        "refund_reference_display",
        "refund_processed_at",
        "refund_verified_by",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 25

    @admin.display(description="Order Number", ordering="order__order_number")
    def order_number(self, obj):
        return obj.order.order_number

    @admin.display(description="Product", ordering="order_item__product_name")
    def product_name(self, obj):
        return obj.order_item.product_name

    @admin.display(description="Customer", ordering="user__email")
    def customer_email(self, obj):
        return getattr(obj.user, "email", str(obj.user))

    @admin.display(description="Refund Amount")
    def refund_amount_display(self, obj):
        tx = obj.refund_finance_transaction
        return tx.amount if tx else "—"

    @admin.display(description="Refund Reference")
    def refund_reference_display(self, obj):
        tx = obj.refund_finance_transaction
        return tx.transaction_reference if tx else "—"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in ("REFUNDED", "CLOSED"):
            for name in ("status", "refund_finance_transaction"):
                if name not in readonly:
                    readonly.append(name)
        return tuple(readonly)

    def save_model(self, request, obj, form, change):
        if obj.status == "REFUNDED":
            obj.refund_processed_at = obj.refund_processed_at or timezone.now()
            obj.refund_verified_by = obj.refund_verified_by or request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Customer returns must originate from the customer return workflow.
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep return/refund records available for audit.
        return False


@admin.register(IndiaCartItem)
class IndiaCartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'own_product', 'quantity', 'price', 'line_total', 'created_at', 'updated_at')
    search_fields = ('cart__user__email', 'product__name', 'own_product__name')
    readonly_fields = ('price', 'line_total', 'created_at', 'updated_at')
    fields = ('cart', 'product', 'own_product', 'quantity', 'price', 'line_total', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 25


@admin.register(IndiaOrderItem)
class IndiaOrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_name', 'quantity', 'price', 'line_total', 'stock_pool', 'stock_deducted', 'stock_restored')
    search_fields = ('order__order_number', 'order__user__email', 'product_name', 'own_product__name')
    readonly_fields = ('order', 'product', 'own_product', 'product_name', 'quantity', 'price', 'line_total', 'stock_pool', 'stock_deducted', 'stock_restored', 'stock_deducted_at', 'stock_restored_at')
    fields = readonly_fields
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IndiaWishlistItem)
class IndiaWishlistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'product__name')
    readonly_fields = ('user', 'product', 'created_at')
    fields = ('user', 'product', 'created_at')
    date_hierarchy = 'created_at'
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
