from django import forms
from django.contrib import admin
from django.utils import timezone

from .models import (
    AboutPage,
    HelpSupport,
    BadInventoryRecord,
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
    DeliveryIncentive,
    DeliveryIncentiveProgress,
    DeliveryPartnerBankAccount,
    DeliveryPartnerDocument,
    DeliveryPartnerProfile,
    DeliverySupportRequest,
    InventoryBatch,
    OTPVerification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductBarcode,
    SearchAlias,
    Shop,
    ShopkeeperBankAccount,
    ShopkeeperDocument,
    ShopkeeperProfile,
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

    def save_model(self, request, obj, form, change):
        # Shopkeepers use their own app and never receive Django Admin access.
        if obj.role == "SHOPKEEPER":
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


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
        "owner",
        "shop_type",
        "phone",
        "gstin",
        "is_online",
        "rating",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "phone",
        "address",
        "gstin",
        "fssai_number",
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
        "cost_price",
        "price",
        "mrp",
        "gst_rate",
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


@admin.register(InventoryBatch)
class InventoryBatchAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "shop",
        "batch_number",
        "quantity_received",
        "quantity_available",
        "expiry_date",
        "status",
    )
    search_fields = ("product__name", "shop__name", "batch_number")
    list_filter = ("status", "expiry_date", "shop")
    list_select_related = ("product", "shop")


@admin.register(BadInventoryRecord)
class BadInventoryRecordAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "shop",
        "quantity",
        "reason",
        "unit_cost",
        "loss_amount",
        "created_at",
    )
    search_fields = ("product__name", "shop__name", "note")
    list_filter = ("reason", "shop", "created_at")
    list_select_related = ("product", "shop", "batch", "created_by")
    readonly_fields = ("created_at",)


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


# =========================================================
# SHOPKEEPER VERIFICATION ADMIN
# =========================================================

SHOPKEEPER_BASE_DOCUMENT_TYPES = {
    "AADHAAR_FRONT",
    "AADHAAR_BACK",
    "PAN",
    "GST_CERTIFICATE",
    "OWNER_SELFIE",
    "SHOP_FRONT",
}
SHOPKEEPER_FOOD_TYPES = {
    "GROCERY",
    "FRUITS_VEGETABLES",
    "DAIRY",
    "BAKERY",
    "RESTAURANT",
}


def _shopkeeper_required_document_types(profile):
    required = set(SHOPKEEPER_BASE_DOCUMENT_TYPES)
    if (
        profile.shop_id
        and profile.shop.shop_type in SHOPKEEPER_FOOD_TYPES
    ):
        required.add("FSSAI_CERTIFICATE")
    return required


def _auto_approve_verified_shopkeepers(profile_ids, reviewer):
    approved = 0
    profiles = ShopkeeperProfile.objects.filter(
        pk__in=set(profile_ids),
        terms_accepted=True,
        shop__isnull=False,
    ).select_related("user", "shop")

    for profile in profiles:
        required = _shopkeeper_required_document_types(profile)
        verified = set(
            ShopkeeperDocument.objects.filter(
                profile=profile,
                status="VERIFIED",
                document_type__in=required,
            ).values_list("document_type", flat=True)
        )
        bank_verified = ShopkeeperBankAccount.objects.filter(
            profile=profile,
            status="VERIFIED",
        ).exists()
        if required.issubset(verified) and bank_verified:
            ShopkeeperProfile.objects.filter(pk=profile.pk).update(
                verification_status="APPROVED",
                rejection_reason="",
                reviewed_by=reviewer,
                reviewed_at=timezone.now(),
            )
            CustomerUser.objects.filter(pk=profile.user_id).update(
                role="SHOPKEEPER",
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
            Shop.objects.filter(pk=profile.shop_id).update(
                is_active=True,
                is_online=False,
            )
            approved += 1
    return approved


@admin.register(ShopkeeperProfile)
class ShopkeeperProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "shop",
        "verification_status",
        "onboarding_step",
        "submitted_at",
        "reviewed_at",
    )
    search_fields = (
        "user__name",
        "user__email",
        "user__phone",
        "shop__name",
        "shop__gstin",
    )
    list_filter = (
        "verification_status",
        "terms_accepted",
        "submitted_at",
    )
    readonly_fields = (
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "created_at",
        "updated_at",
    )
    actions = (
        "mark_under_review",
        "approve_shopkeepers",
        "block_shopkeepers",
    )

    def save_model(self, request, obj, form, change):
        if "verification_status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            if obj.verification_status != "REJECTED":
                obj.rejection_reason = ""
        super().save_model(request, obj, form, change)
        if obj.shop_id:
            if obj.verification_status == "APPROVED":
                CustomerUser.objects.filter(pk=obj.user_id).update(
                    role="SHOPKEEPER",
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                Shop.objects.filter(pk=obj.shop_id).update(is_active=True)
            elif obj.verification_status == "BLOCKED":
                Shop.objects.filter(pk=obj.shop_id).update(
                    is_active=False,
                    is_online=False,
                )

    @admin.action(description="Move selected shopkeepers to Under Review")
    def mark_under_review(self, request, queryset):
        changed = queryset.update(
            verification_status="UNDER_REVIEW",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{changed} shop application(s) in review.")

    @admin.action(description="Approve selected shopkeepers")
    def approve_shopkeepers(self, request, queryset):
        profile_rows = list(queryset.values_list("user_id", "shop_id"))
        changed = queryset.update(
            verification_status="APPROVED",
            rejection_reason="",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        CustomerUser.objects.filter(
            pk__in=[row[0] for row in profile_rows]
        ).update(
            role="SHOPKEEPER",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        Shop.objects.filter(
            pk__in=[row[1] for row in profile_rows if row[1]]
        ).update(is_active=True, is_online=False)
        self.message_user(request, f"{changed} shopkeeper(s) approved.")

    @admin.action(description="Block selected shopkeepers")
    def block_shopkeepers(self, request, queryset):
        shop_ids = list(
            queryset.exclude(shop__isnull=True).values_list(
                "shop_id",
                flat=True,
            )
        )
        changed = queryset.update(
            verification_status="BLOCKED",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        Shop.objects.filter(pk__in=shop_ids).update(
            is_active=False,
            is_online=False,
        )
        self.message_user(request, f"{changed} shopkeeper(s) blocked.")


@admin.register(ShopkeeperDocument)
class ShopkeeperDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "document_type",
        "masked_document_number",
        "status",
        "verified_at",
    )
    search_fields = (
        "profile__user__name",
        "profile__shop__name",
        "document_number_last4",
    )
    list_filter = ("document_type", "status", "created_at")
    readonly_fields = (
        "document_number_hash",
        "document_number_last4",
        "masked_document_number",
        "verified_at",
        "verified_by",
        "created_at",
        "updated_at",
    )
    actions = ("verify_documents", "reject_documents")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            if obj.status == "VERIFIED":
                obj.rejection_reason = ""
        super().save_model(request, obj, form, change)
        if obj.status == "VERIFIED":
            _auto_approve_verified_shopkeepers(
                [obj.profile_id],
                request.user,
            )

    @admin.action(description="Verify selected shop documents")
    def verify_documents(self, request, queryset):
        profile_ids = list(
            queryset.values_list("profile_id", flat=True).distinct()
        )
        changed = queryset.update(
            status="VERIFIED",
            rejection_reason="",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        approved = _auto_approve_verified_shopkeepers(
            profile_ids,
            request.user,
        )
        self.message_user(
            request,
            f"{changed} document(s) verified; {approved} shop(s) approved.",
        )

    @admin.action(description="Reject selected shop documents")
    def reject_documents(self, request, queryset):
        changed = queryset.update(
            status="REJECTED",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(request, f"{changed} document(s) rejected.")


@admin.register(ShopkeeperBankAccount)
class ShopkeeperBankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "account_holder_name",
        "bank_name",
        "masked_account_number",
        "ifsc_code",
        "status",
        "verified_at",
    )
    search_fields = (
        "profile__user__name",
        "profile__shop__name",
        "account_holder_name",
        "ifsc_code",
    )
    list_filter = ("status", "bank_name", "created_at")
    readonly_fields = (
        "account_number_hash",
        "account_number_last4",
        "masked_account_number",
        "verified_at",
        "verified_by",
        "created_at",
        "updated_at",
    )
    actions = ("verify_bank_accounts", "reject_bank_accounts")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            if obj.status == "VERIFIED":
                obj.rejection_reason = ""
        super().save_model(request, obj, form, change)
        if obj.status == "VERIFIED":
            _auto_approve_verified_shopkeepers(
                [obj.profile_id],
                request.user,
            )

    @admin.action(description="Verify selected shop bank accounts")
    def verify_bank_accounts(self, request, queryset):
        profile_ids = list(
            queryset.values_list("profile_id", flat=True).distinct()
        )
        changed = queryset.update(
            status="VERIFIED",
            rejection_reason="",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        approved = _auto_approve_verified_shopkeepers(
            profile_ids,
            request.user,
        )
        self.message_user(
            request,
            f"{changed} bank account(s) verified; {approved} shop(s) approved.",
        )

    @admin.action(description="Reject selected shop bank accounts")
    def reject_bank_accounts(self, request, queryset):
        changed = queryset.update(
            status="REJECTED",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(request, f"{changed} bank account(s) rejected.")


# =========================================================
# DELIVERY PARTNER VERIFICATION ADMIN
# =========================================================

DELIVERY_REQUIRED_DOCUMENT_TYPES = {
    "AADHAAR_FRONT",
    "AADHAAR_BACK",
    "PAN",
    "SELFIE",
}


def _auto_approve_verified_delivery_profiles(profile_ids, reviewer):
    """Approve a profile when all mandatory KYC and bank checks pass."""
    approved_count = 0

    profiles = DeliveryPartnerProfile.objects.filter(
        pk__in=set(profile_ids),
        terms_accepted=True,
    ).select_related("user")

    for profile in profiles:
        verified_types = set(
            DeliveryPartnerDocument.objects.filter(
                profile=profile,
                status="VERIFIED",
                document_type__in=DELIVERY_REQUIRED_DOCUMENT_TYPES,
            ).values_list("document_type", flat=True)
        )
        bank_verified = DeliveryPartnerBankAccount.objects.filter(
            profile=profile,
            status="VERIFIED",
        ).exists()

        if (
            DELIVERY_REQUIRED_DOCUMENT_TYPES.issubset(verified_types)
            and bank_verified
        ):
            DeliveryPartnerProfile.objects.filter(pk=profile.pk).update(
                verification_status="APPROVED",
                rejection_reason="",
                reviewed_by=reviewer,
                reviewed_at=timezone.now(),
            )
            CustomerUser.objects.filter(pk=profile.user_id).update(
                role="DELIVERY",
                is_active=True,
                is_active_delivery=False,
            )
            approved_count += 1

    return approved_count

@admin.register(DeliveryPartnerProfile)
class DeliveryPartnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "verification_status",
        "onboarding_step",
        "vehicle_type",
        "city",
        "submitted_at",
        "reviewed_at",
    )
    search_fields = (
        "user__name",
        "user__email",
        "user__phone",
        "vehicle_number",
        "city",
        "pincode",
    )
    list_filter = (
        "verification_status",
        "vehicle_type",
        "terms_accepted",
        "submitted_at",
    )
    list_select_related = (
        "user",
        "reviewed_by",
    )
    readonly_fields = (
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "created_at",
        "updated_at",
    )
    actions = (
        "mark_under_review",
        "approve_partners",
        "block_partners",
    )

    fieldsets = (
        (
            "Delivery Partner",
            {
                "fields": (
                    "user",
                    "profile_photo",
                    "date_of_birth",
                    "full_address",
                    "city",
                    "state",
                    "pincode",
                    "emergency_contact_name",
                    "emergency_contact_phone",
                )
            },
        ),
        (
            "Vehicle",
            {
                "fields": (
                    "vehicle_type",
                    "vehicle_number",
                )
            },
        ),
        (
            "Onboarding & Verification",
            {
                "fields": (
                    "onboarding_step",
                    "terms_accepted",
                    "verification_status",
                    "rejection_reason",
                    "admin_note",
                    "submitted_at",
                    "reviewed_at",
                    "reviewed_by",
                )
            },
        ),
        (
            "Record",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if "verification_status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()

            if obj.verification_status != "REJECTED":
                obj.rejection_reason = ""

        super().save_model(request, obj, form, change)

        if obj.verification_status == "APPROVED":
            type(obj.user).objects.filter(pk=obj.user_id).update(
                role="DELIVERY",
                is_active=True,
            )
        elif obj.verification_status == "BLOCKED":
            type(obj.user).objects.filter(pk=obj.user_id).update(
                is_active_delivery=False,
            )

    @admin.action(description="Move selected partners to Under Review")
    def mark_under_review(self, request, queryset):
        changed = queryset.update(
            verification_status="UNDER_REVIEW",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{changed} partner(s) moved to review.")

    @admin.action(description="Approve selected delivery partners")
    def approve_partners(self, request, queryset):
        partner_ids = list(queryset.values_list("user_id", flat=True))
        changed = queryset.update(
            verification_status="APPROVED",
            rejection_reason="",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        CustomerUser.objects.filter(pk__in=partner_ids).update(
            role="DELIVERY",
            is_active=True,
        )
        self.message_user(request, f"{changed} partner(s) approved.")

    @admin.action(description="Block selected delivery partners")
    def block_partners(self, request, queryset):
        partner_ids = list(queryset.values_list("user_id", flat=True))
        changed = queryset.update(
            verification_status="BLOCKED",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        CustomerUser.objects.filter(pk__in=partner_ids).update(
            is_active_delivery=False,
        )
        self.message_user(request, f"{changed} partner(s) blocked.")


@admin.register(DeliveryPartnerDocument)
class DeliveryPartnerDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "document_type",
        "masked_document_number",
        "status",
        "verified_at",
    )
    search_fields = (
        "profile__user__name",
        "profile__user__email",
        "profile__user__phone",
        "document_number_last4",
    )
    list_filter = (
        "document_type",
        "status",
        "created_at",
    )
    list_select_related = (
        "profile",
        "profile__user",
        "verified_by",
    )
    readonly_fields = (
        "document_number_hash",
        "document_number_last4",
        "masked_document_number",
        "verified_at",
        "verified_by",
        "created_at",
        "updated_at",
    )
    actions = (
        "verify_documents",
        "reject_documents",
    )

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            if obj.status == "VERIFIED":
                obj.rejection_reason = ""

        super().save_model(request, obj, form, change)

        if obj.status == "VERIFIED":
            _auto_approve_verified_delivery_profiles(
                [obj.profile_id],
                request.user,
            )

    @admin.action(description="Verify selected documents")
    def verify_documents(self, request, queryset):
        profile_ids = list(
            queryset.values_list("profile_id", flat=True).distinct()
        )
        changed = queryset.update(
            status="VERIFIED",
            rejection_reason="",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        approved = _auto_approve_verified_delivery_profiles(
            profile_ids,
            request.user,
        )
        self.message_user(
            request,
            f"{changed} document(s) verified; "
            f"{approved} partner profile(s) automatically approved.",
        )

    @admin.action(description="Reject selected documents")
    def reject_documents(self, request, queryset):
        changed = queryset.update(
            status="REJECTED",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{changed} document(s) rejected. Add a reason from each record.",
        )


@admin.register(DeliveryPartnerBankAccount)
class DeliveryPartnerBankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "account_holder_name",
        "bank_name",
        "masked_account_number",
        "ifsc_code",
        "status",
        "verified_at",
    )
    search_fields = (
        "profile__user__name",
        "profile__user__email",
        "profile__user__phone",
        "account_holder_name",
        "account_number_last4",
        "ifsc_code",
    )
    list_filter = (
        "status",
        "bank_name",
        "created_at",
    )
    list_select_related = (
        "profile",
        "profile__user",
        "verified_by",
    )
    readonly_fields = (
        "account_number_hash",
        "account_number_last4",
        "masked_account_number",
        "verified_at",
        "verified_by",
        "created_at",
        "updated_at",
    )
    actions = (
        "verify_bank_accounts",
        "reject_bank_accounts",
    )

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            if obj.status == "VERIFIED":
                obj.rejection_reason = ""

        super().save_model(request, obj, form, change)

        if obj.status == "VERIFIED":
            _auto_approve_verified_delivery_profiles(
                [obj.profile_id],
                request.user,
            )

    @admin.action(description="Verify selected bank accounts")
    def verify_bank_accounts(self, request, queryset):
        profile_ids = list(
            queryset.values_list("profile_id", flat=True).distinct()
        )
        changed = queryset.update(
            status="VERIFIED",
            rejection_reason="",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        approved = _auto_approve_verified_delivery_profiles(
            profile_ids,
            request.user,
        )
        self.message_user(
            request,
            f"{changed} bank account(s) verified; "
            f"{approved} partner profile(s) automatically approved.",
        )

    @admin.action(description="Reject selected bank accounts")
    def reject_bank_accounts(self, request, queryset):
        changed = queryset.update(
            status="REJECTED",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{changed} bank account(s) rejected. Add a reason from each record.",
        )


# =========================================================
# DELIVERY INCENTIVE ADMIN
# =========================================================

@admin.register(DeliveryIncentive)
class DeliveryIncentiveAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "incentive_type",
        "required_deliveries",
        "bonus_amount",
        "start_at",
        "end_at",
        "is_active",
    )
    search_fields = (
        "title",
        "description",
    )
    list_filter = (
        "incentive_type",
        "is_active",
        "start_at",
    )
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
    )

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DeliveryIncentiveProgress)
class DeliveryIncentiveProgressAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_partner",
        "incentive",
        "completed_deliveries",
        "progress_percentage",
        "bonus_earned",
        "status",
        "period_start",
        "period_end",
    )
    search_fields = (
        "delivery_partner__name",
        "delivery_partner__email",
        "delivery_partner__phone",
        "incentive__title",
    )
    list_filter = (
        "status",
        "incentive__incentive_type",
        "period_start",
    )
    list_select_related = (
        "delivery_partner",
        "incentive",
    )
    readonly_fields = (
        "progress_percentage",
        "remaining_deliveries",
        "completed_at",
        "credited_at",
        "created_at",
        "updated_at",
    )
