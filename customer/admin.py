from django import forms
from django.contrib import admin

from .models import (
    AboutPage,
    HelpSupport,
    PrivacyPolicy,
    TermsConditions,
    Wallet,
    WalletTransaction,
    Settlement,
    Referral,
    Payment,
    MasterOrder,
    CouponUsage,
    Coupon,
    Address,
    Brand,
    Cart,
    CartItem,
    Category,
    CustomerUser,
    DeliveryAssignment,
    DeliverySupportRequest,
    OTPVerification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductBarcode,
    SearchAlias,
    Shop,
    ShopProduct,
)


# =========================================================
# CUSTOMER USER CREATE FORM
# =========================================================

class CustomerUserCreationForm(forms.ModelForm):

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
    )

    class Meta:
        model = CustomerUser

        fields = (
            "email",
            "name",
            "phone",
            "role",
            "is_active_delivery",
            "is_active",
            "is_staff",
        )

    def clean_password2(self):

        password1 = self.cleaned_data.get(
            "password1"
        )

        password2 = self.cleaned_data.get(
            "password2"
        )

        if (
            password1
            and password2
            and password1 != password2
        ):
            raise forms.ValidationError(
                "Passwords do not match."
            )

        return password2

    def save(
        self,
        commit=True,
    ):

        user = super().save(
            commit=False
        )

        user.set_password(
            self.cleaned_data["password1"]
        )

        if commit:
            user.save()

        return user


# =========================================================
# CUSTOMER USER CHANGE FORM
# =========================================================

class CustomerUserChangeForm(forms.ModelForm):

    class Meta:
        model = CustomerUser

        fields = "__all__"


# =========================================================
# CUSTOMER USER ADMIN
# =========================================================

@admin.register(CustomerUser)
class CustomerUserAdmin(admin.ModelAdmin):

    form = CustomerUserChangeForm

    add_form = CustomerUserCreationForm


    list_display = (
        "email",
        "name",
        "phone",
        "role",
        "is_active_delivery",
        "is_staff",
        "is_active",
        "created_at",
    )


    search_fields = (
        "email",
        "name",
        "phone",
    )


    list_filter = (
        "role",
        "is_active_delivery",
        "is_staff",
        "is_active",
    )


    ordering = (
        "-created_at",
    )


    readonly_fields = (
        "last_login",
        "created_at",
    )


    fieldsets = (

        (
            "Account",
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),

        (
            "Personal Information",
            {
                "fields": (
                    "name",
                    "phone",
                    "role",
                )
            },
        ),

        (
            "Delivery Partner",
            {
                "fields": (
                    "is_active_delivery",
                )
            },
        ),

        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),

        (
            "Important Dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                )
            },
        ),
    )


    add_fieldsets = (

        (
            "Create AMEXA User",
            {
                "classes": (
                    "wide",
                ),

                "fields": (
                    "email",
                    "name",
                    "phone",
                    "role",
                    "password1",
                    "password2",
                    "is_active_delivery",
                    "is_active",
                    "is_staff",
                ),
            },
        ),

    )


    def get_fieldsets(
        self,
        request,
        obj=None,
    ):

        if obj is None:
            return self.add_fieldsets

        return super().get_fieldsets(
            request,
            obj,
        )


    def get_form(
        self,
        request,
        obj=None,
        **kwargs,
    ):

        if obj is None:
            kwargs["form"] = (
                self.add_form
            )

        return super().get_form(
            request,
            obj,
            **kwargs,
        )


# =========================================================
# BRAND ADMIN
# =========================================================

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
    )

    list_filter = (
        "is_active",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        )
    }


# =========================================================
# CATEGORY ADMIN
# =========================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
    )

    list_filter = (
        "is_active",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        )
    }


# =========================================================
# SHOP ADMIN
# =========================================================

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "phone",
        "rating",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "phone",
        "address",
    )

    list_filter = (
        "is_active",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        )
    }


# =========================================================
# PRODUCT ADMIN
# =========================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "shop",
        "category",
        "price",
        "mrp",
        "stock_quantity",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "description",
    )

    list_filter = (
        "shop",
        "category",
        "is_active",
    )

    prepopulated_fields = {
        "slug": (
            "name",
        )
    }


# =========================================================
# PRODUCT BARCODE ADMIN
# =========================================================

@admin.register(ProductBarcode)
class ProductBarcodeAdmin(admin.ModelAdmin):

    list_display = (
        "barcode",
        "barcode_type",
        "product",
        "is_primary",
        "created_at",
    )

    search_fields = (
        "barcode",
        "product__name",
    )

    list_filter = (
        "barcode_type",
        "is_primary",
    )


# =========================================================
# SHOP PRODUCT ADMIN
# =========================================================

@admin.register(ShopProduct)
class ShopProductAdmin(admin.ModelAdmin):

    list_display = (
        "product",
        "shop",
        "selling_price",
        "mrp",
        "stock_quantity",
        "is_active",
        "updated_at",
    )

    search_fields = (
        "product__name",
        "shop__name",
    )

    list_filter = (
        "shop",
        "is_active",
    )


# =========================================================
# ADDRESS ADMIN
# =========================================================

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):

    list_display = (
        "full_name",
        "mobile",
        "city",
        "pincode",
        "address_type",
        "is_default",
    )

    search_fields = (
        "full_name",
        "mobile",
        "city",
        "pincode",
    )

    list_filter = (
        "address_type",
        "is_default",
    )


# =========================================================
# ORDER ADMIN
# =========================================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "master_order",
        "user",
        "shop",
        "total_amount",
        "payment_method",
        "payment_status",
        "status",
        "created_at",
    )

    search_fields = (
        "order_number",
        "master_order__master_order_number",
        "user__email",
        "user__name",
        "user__phone",
        "shop__name",
    )

    list_filter = (
        "status",
        "payment_status",
        "payment_method",
        "shop",
        "created_at",
    )

    list_select_related = (
        "master_order",
        "user",
        "shop",
        "address",
    )

    readonly_fields = (
        "order_number",
        "created_at",
        "updated_at",
        "cancelled_at",
    )

    actions = (
        "mark_confirmed",
        "mark_preparing",
        "mark_out_for_delivery",
        "mark_delivered",
    )

    def _change_status(self, request, queryset, status, note):
        changed = 0

        for order in queryset.select_related("master_order"):
            if order.status == "Cancelled":
                continue

            if order.status == status:
                continue

            order.status = status

            update_fields = ["status", "updated_at"]

            if status == "Delivered":
                order.payment_status = (
                    "Paid"
                    if order.payment_method == "COD"
                    else order.payment_status
                )
                update_fields.append("payment_status")

            order.save(update_fields=update_fields)
            order.create_status_history(status, note)
            changed += 1

        self.message_user(
            request,
            f"{changed} order(s) updated to {status}.",
        )

    @admin.action(description="Mark selected orders as Confirmed")
    def mark_confirmed(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "Confirmed",
            "Status updated by AMEXA admin",
        )

    @admin.action(description="Mark selected orders as Preparing")
    def mark_preparing(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "Preparing",
            "Status updated by AMEXA admin",
        )

    @admin.action(description="Mark selected orders as Out for Delivery")
    def mark_out_for_delivery(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "Out for Delivery",
            "Status updated by AMEXA admin",
        )

    @admin.action(description="Mark selected orders as Delivered")
    def mark_delivered(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "Delivered",
            "Delivered by AMEXA admin",
        )


# =========================================================
# ORDER ITEM ADMIN
# =========================================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "product_name",
        "quantity",
        "price",
        "created_at",
    )

    search_fields = (
        "product_name",
        "order__order_number",
    )


# =========================================================
# ORDER STATUS HISTORY ADMIN
# =========================================================

@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "status",
        "note",
        "created_at",
    )

    search_fields = (
        "order__order_number",
        "status",
    )

    list_filter = (
        "status",
    )


# =========================================================
# DELIVERY ASSIGNMENT ADMIN
# =========================================================

@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "delivery_partner",
        "status",
        "current_latitude",
        "current_longitude",
        "location_updated_at",
        "assigned_at",
        "completed_at",
    )

    search_fields = (
        "order__order_number",
        "delivery_partner__email",
        "delivery_partner__name",
        "delivery_partner__phone",
    )

    list_filter = (
        "status",
        "assigned_at",
    )

    readonly_fields = (
        "assigned_at",
        "accepted_at",
        "picked_at",
        "out_for_delivery_at",
        "completed_at",
        "location_updated_at",
    )

    fieldsets = (

        (
            "Delivery Assignment",
            {
                "fields": (
                    "order",
                    "delivery_partner",
                    "status",
                )
            },
        ),

        (
            "Rider Live Location",
            {
                "fields": (
                    "current_latitude",
                    "current_longitude",
                    "location_updated_at",
                )
            },
        ),

        (
            "Timing",
            {
                "fields": (
                    "assigned_at",
                    "accepted_at",
                    "picked_at",
                    "out_for_delivery_at",
                    "completed_at",
                )
            },
        ),
    )


# =========================================================
# DELIVERY SUPPORT REQUEST ADMIN
# =========================================================

@admin.register(DeliverySupportRequest)
class DeliverySupportRequestAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "delivery_partner",
        "request_type",
        "order",
        "subject",
        "amount_claimed",
        "status",
        "created_at",
    )

    search_fields = (
        "delivery_partner__email",
        "delivery_partner__name",
        "delivery_partner__phone",
        "order__order_number",
        "subject",
        "description",
    )

    list_filter = (
        "request_type",
        "status",
        "created_at",
    )

    list_select_related = (
        "delivery_partner",
        "order",
    )

    readonly_fields = (
        "delivery_partner",
        "request_type",
        "order",
        "subject",
        "description",
        "amount_claimed",
        "created_at",
        "updated_at",
    )

    fields = (
        "delivery_partner",
        "request_type",
        "order",
        "subject",
        "description",
        "amount_claimed",
        "status",
        "created_at",
        "updated_at",
    )


# =========================================================
# CART ADMIN
# =========================================================

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "shop",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__email",
        "user__phone",
    )


# =========================================================
# CART ITEM ADMIN
# =========================================================

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):

    list_display = (
        "cart",
        "product",
        "quantity",
        "price",
        "created_at",
    )

    search_fields = (
        "product__name",
        "cart__user__email",
    )


# =========================================================
# OTP ADMIN
# =========================================================

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):

    list_display = (
        "phone",
        "user",
        "code",
        "expires_at",
        "attempts",
        "is_used",
        "created_at",
    )

    search_fields = (
        "phone",
        "user__email",
    )

    list_filter = (
        "is_used",
    )
    # =========================================================
# ABOUT AMEXA ADMIN
# =========================================================

@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "email",
        "phone",
        "is_active",
        "updated_at",
    )

    search_fields = (
        "title",
        "short_description",
        "description",
        "mission",
        "vision",
        "email",
        "phone",
    )

    list_filter = (
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

# =========================================================
# HELP & SUPPORT ADMIN
# =========================================================

@admin.register(HelpSupport)
class HelpSupportAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "support_phone",
        "support_email",
        "support_hours",
        "is_active",
        "updated_at",
    )

    search_fields = (
        "title",
        "short_description",
        "order_help",
        "delivery_help",
        "payment_help",
        "cancellation_help",
        "faq",
        "support_phone",
        "whatsapp_number",
        "support_email",
    )

    list_filter = (
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )
# =========================================================
# PRIVACY POLICY ADMIN
# =========================================================

@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "is_active",
        "updated_at",
    )

    search_fields = (
        "title",
        "content",
    )

    list_filter = (
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

# =========================================================
# TERMS & CONDITIONS ADMIN
# =========================================================

@admin.register(TermsConditions)
class TermsConditionsAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "is_active",
        "updated_at",
    )

    search_fields = (
        "title",
        "content",
    )

    list_filter = (
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

@admin.register(SearchAlias)

class SearchAliasAdmin(admin.ModelAdmin):
    list_display = ("keyword", "mapped_text", "is_active", "updated_at")
    search_fields = ("keyword", "mapped_text")
    list_filter = ("is_active",)

# =========================================================
# AMEXA WALLET / COINS ADMIN
# =========================================================

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "coin_balance",
        "lifetime_earned",
        "lifetime_spent",
        "updated_at",
    )

    search_fields = (
        "user__email",
        "user__name",
        "user__phone",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "wallet",
        "transaction_type",
        "reason",
        "coins",
        "balance_after",
        "remaining_coins",
        "expires_at",
        "master_order",
        "created_at",
    )

    search_fields = (
        "wallet__user__email",
        "wallet__user__name",
        "wallet__user__phone",
        "description",
        "master_order__master_order_number",
    )

    list_filter = (
        "transaction_type",
        "reason",
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )



# =========================================================
# MASTER ORDER / PAYMENT / SETTLEMENT ADMIN
# =========================================================

@admin.register(MasterOrder)
class MasterOrderAdmin(admin.ModelAdmin):
    list_display = (
        "master_order_number",
        "user",
        "subtotal",
        "discount_amount",
        "coins_redeemed",
        "coin_discount_amount",
        "total_amount",
        "status",
        "created_at",
    )

    search_fields = (
        "master_order_number",
        "user__email",
        "user__name",
        "user__phone",
    )

    list_filter = (
        "status",
        "created_at",
    )

    readonly_fields = (
        "master_order_number",
        "created_at",
        "updated_at",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "master_order",
        "user",
        "payment_method",
        "payment_status",
        "amount",
        "transaction_id",
        "created_at",
    )

    search_fields = (
        "master_order__master_order_number",
        "user__email",
        "user__name",
        "user__phone",
        "transaction_id",
    )

    list_filter = (
        "payment_method",
        "payment_status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "shop",
        "product_amount",
        "shop_commission",
        "shop_payable",
        "delivery_partner_payout",
        "platform_fee",
        "amexa_earning",
        "status",
        "created_at",
    )

    search_fields = (
        "order__order_number",
        "shop__name",
    )

    list_filter = (
        "status",
        "shop",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referred_user",
        "referral_code",
        "reward_coins",
        "is_rewarded",
        "qualifying_master_order",
        "rewarded_at",
        "created_at",
    )

    search_fields = (
        "referrer__email",
        "referrer__name",
        "referrer__phone",
        "referred_user__email",
        "referred_user__name",
        "referred_user__phone",
        "referral_code",
    )

    list_filter = (
        "is_rewarded",
        "created_at",
    )

    readonly_fields = (
        "rewarded_at",
        "created_at",
    )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "minimum_order_amount",
        "is_active",
        "start_at",
        "end_at",
    )

    search_fields = (
        "code",
        "description",
    )

    list_filter = (
        "discount_type",
        "is_active",
    )


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = (
        "coupon",
        "user",
        "master_order",
        "discount_amount",
        "used_at",
    )

    search_fields = (
        "coupon__code",
        "user__email",
        "user__name",
        "user__phone",
        "master_order__master_order_number",
    )

    readonly_fields = (
        "used_at",
    )
