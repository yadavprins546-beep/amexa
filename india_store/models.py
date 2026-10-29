
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class IndiaCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)

    icon = models.CharField(
        max_length=80,
        blank=True,
        help_text="Optional emoji or icon name, e.g. ??",
    )
    image = models.ImageField(
        upload_to="india/categories/",
        blank=True,
        null=True,
    )

    banner_image = models.ImageField(
        upload_to="india/category_banners/",
        blank=True,
        null=True,
    )
    banner_title = models.CharField(max_length=180, blank=True)
    banner_subtitle = models.CharField(max_length=300, blank=True)

    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first.",
    )
    is_active = models.BooleanField(default=True)
    show_on_home = models.BooleanField(default=True)
    coming_soon = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "India Category"
        verbose_name_plural = "India Categories"

    def __str__(self):
        return self.name


class IndiaProduct(models.Model):
    category = models.ForeignKey(
        IndiaCategory,
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)

    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    image = models.ImageField(
        upload_to="india/products/",
        blank=True,
        null=True,
    )

    # Admin-controlled promotion badges
    show_sale_badge = models.BooleanField(default=False)
    sale_badge_text = models.CharField(
        max_length=40,
        blank=True,
        help_text="Example: Diwali Sale, Mega Deal, Special Offer",
    )
    sale_start_at = models.DateTimeField(blank=True, null=True)
    sale_end_at = models.DateTimeField(blank=True, null=True)

    is_featured = models.BooleanField(default=False)
    show_new_arrival_badge = models.BooleanField(default=False)
    show_bestseller_badge = models.BooleanField(default=False)
    show_trending_badge = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def discount_percent(self):
        if self.mrp and self.mrp > self.selling_price:
            return round(
                (self.mrp - self.selling_price) * 100 / self.mrp
            )
        return 0

    @property
    def reward_coins(self):
        # Own-inventory items do not award coins unless a dedicated field is added.
        return 0

    @property
    def sale_badge_is_active(self):
        if not self.show_sale_badge or not self.sale_badge_text.strip():
            return False

        now = timezone.now()

        if self.sale_start_at and now < self.sale_start_at:
            return False
        if self.sale_end_at and now > self.sale_end_at:
            return False

        return True

    def __str__(self):
        return self.name


class ResellingProduct(models.Model):
    SOURCE_STATUS = [
        ("unverified", "Availability Not Verified"),
        ("available", "Available from Source"),
        ("unavailable", "Currently Unavailable"),
    ]

    FULFILLMENT_CHOICES = [
        ("byxom", "BYXOM Sources and Ships"),
        ("supplier", "Supplier Ships to Customer"),
    ]

    LISTING_STATUS = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
    ]

    category = models.ForeignKey(
        IndiaCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reselling_products",
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="india/reselling/",
        blank=True,
        null=True,
    )

    image_2 = models.ImageField(
        upload_to="india/reselling/gallery/",
        blank=True,
        null=True,
        help_text="Optional second product photo",
    )
    image_3 = models.ImageField(
        upload_to="india/reselling/gallery/",
        blank=True,
        null=True,
        help_text="Optional third product photo",
    )

    source_name = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(blank=True)

    sourcing_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)

    source_status = models.CharField(
        max_length=20,
        choices=SOURCE_STATUS,
        default="unverified",
    )
    fulfillment_method = models.CharField(
        max_length=20,
        choices=FULFILLMENT_CHOICES,
        default="byxom",
    )
    listing_status = models.CharField(
        max_length=20,
        choices=LISTING_STATUS,
        default="draft",
    )

    stock_checked_at = models.DateTimeField(null=True, blank=True)

    # BYXOM-owned stock physically counted in our own inventory.
    inventory_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Units physically held by BYXOM. Leave blank until counted.",
    )
    reorder_level = models.PositiveIntegerField(
        default=5,
        help_text="Admin low-stock alert threshold for BYXOM-owned inventory.",
    )

    # Quantity reported by the external supplier/source.
    source_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Supplier-reported available units. Leave blank if unknown.",
    )
    source_reorder_level = models.PositiveIntegerField(
        default=5,
        help_text="Admin alert threshold for supplier-reported stock.",
    )
    stock_check_notes = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="When/how supplier availability was checked, or relevant notes.",
    )

    show_sale_badge = models.BooleanField(default=False)
    sale_badge_text = models.CharField(max_length=40, blank=True)
    sale_start_at = models.DateTimeField(null=True, blank=True)
    sale_end_at = models.DateTimeField(null=True, blank=True)

    is_featured = models.BooleanField(default=False)
    show_new_arrival_badge = models.BooleanField(default=False)
    show_bestseller_badge = models.BooleanField(default=False)
    show_trending_badge = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reselling Product"
        verbose_name_plural = "Reselling Products"

    @property
    def discount_percent(self):
        if self.mrp and self.mrp > self.selling_price:
            return round(
                (self.mrp - self.selling_price) * 100 / self.mrp
            )
        return 0

    @property
    def sale_badge_is_active(self):
        if not self.show_sale_badge or not self.sale_badge_text.strip():
            return False

        now = timezone.now()

        if self.sale_start_at and now < self.sale_start_at:
            return False
        if self.sale_end_at and now > self.sale_end_at:
            return False

        return True

    @property
    def estimated_gross_margin(self):
        # Safe when a new product form has empty prices.
        selling_price = self.selling_price or Decimal("0.00")
        sourcing_cost = self.sourcing_cost or Decimal("0.00")
        return selling_price - sourcing_cost

    def __str__(self):
        return f"{self.name} (Reselling)"
    reward_coins = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(100000)],
        help_text="Coins credited for each unit after the order is delivered.",
    )



class FinancePayable(models.Model):
    RECIPIENT_TYPES = [
        ("supplier", "Supplier"),
        ("seller", "Seller"),
        ("logistics", "Logistics Partner"),
        ("other", "Other"),
    ]

    recipient_type = models.CharField(
        max_length=20,
        choices=RECIPIENT_TYPES,
    )
    recipient_name = models.CharField(max_length=200)

    invoice_reference = models.CharField(max_length=100, blank=True)
    order_reference = models.CharField(max_length=100, blank=True)

    reselling_product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_payables",
    )

    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def amount_paid(self):
        result = self.transactions.filter(
            direction="outgoing",
            status="successful",
            is_verified=True,
        ).aggregate(total=models.Sum("amount"))

        return result["total"] or Decimal("0.00")

    @property
    def balance_due(self):
        remaining = self.amount_due - self.amount_paid
        return max(remaining, Decimal("0.00"))

    @property
    def payment_status(self):
        paid = self.amount_paid

        if paid >= self.amount_due:
            return "Paid"
        if paid > 0:
            return "Partially paid"
        return "Pending"

    class Meta:
        ordering = ["due_date", "-created_at"]
        verbose_name = "Supplier or Seller Payable"
        verbose_name_plural = "Supplier and Seller Payables"

    def __str__(self):
        return f"{self.recipient_name} - ₹{self.amount_due}"


class FinanceTransaction(models.Model):
    source_payment = models.OneToOneField(
        "customer.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_transaction",
    )

    DIRECTIONS = [
        ("incoming", "Money In"),
        ("outgoing", "Money Out"),
    ]

    TRANSACTION_TYPES = [
        ("customer_payment", "Customer Payment"),
        ("supplier_payment", "Supplier Payment"),
        ("seller_payout", "Seller Payout"),
        ("customer_refund", "Customer Refund"),
        ("gateway_fee", "Payment Gateway Fee"),
        ("operating_expense", "Operating Expense"),
        ("other_income", "Other Income"),
        ("other_expense", "Other Expense"),
    ]

    STATUSES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("successful", "Successful"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHODS = [
        ("gateway", "Payment Gateway"),
        ("upi", "UPI"),
        ("bank_transfer", "Bank Transfer"),
        ("card", "Card"),
        ("cash", "Cash"),
        ("other", "Other"),
    ]

    SOURCES = [
        ("manual", "Manually Recorded"),
        ("gateway_webhook", "Verified Gateway Event"),
        ("bank_statement", "Bank Statement"),
        ("system", "System Generated"),
    ]

    PARTY_TYPES = [
        ("customer", "Customer"),
        ("supplier", "Supplier"),
        ("seller", "Seller"),
        ("gateway", "Payment Gateway"),
        ("logistics", "Logistics Partner"),
        ("other", "Other"),
    ]

    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    transaction_type = models.CharField(
        max_length=25,
        choices=TRANSACTION_TYPES,
    )
    status = models.CharField(
        max_length=12,
        choices=STATUSES,
        default="pending",
    )

    party_type = models.CharField(
        max_length=15,
        choices=PARTY_TYPES,
        default="other",
    )
    party_name = models.CharField(max_length=200, blank=True)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default="other",
    )
    payment_source = models.CharField(
        max_length=20,
        choices=SOURCES,
        default="manual",
    )
    payment_provider = models.CharField(max_length=100, blank=True)

    transaction_reference = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
    )
    order_reference = models.CharField(max_length=100, blank=True)

    payable = models.ForeignKey(
        FinancePayable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    reselling_product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_transactions",
    )

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_finance_transactions",
    )

    transaction_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_finance_transactions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Finance Transaction"
        verbose_name_plural = "Finance Transactions"
        indexes = [
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["transaction_type", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.get_direction_display()} - "
            f"₹{self.amount} - {self.get_status_display()}"
        )

class IndiaCart(models.Model):
    """Separate shopping cart for All India reselling products."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="india_cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "All India Cart"
        verbose_name_plural = "All India Carts"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        )

    def __str__(self):
        return f"All India Cart - {self.user}"


class IndiaCartItem(models.Model):
    """Cart line with a price snapshot captured when the item is added."""

    cart = models.ForeignKey(
        IndiaCart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.CASCADE,
        related_name="india_cart_items",
        null=True,
        blank=True,
    )
    own_product = models.ForeignKey(
        IndiaProduct,
        on_delete=models.CASCADE,
        related_name="india_cart_items",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="uniq_india_cart_product",
            ),
            models.UniqueConstraint(
                fields=["cart", "own_product"],
                condition=models.Q(own_product__isnull=False),
                name="uniq_india_cart_own_product",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, own_product__isnull=True)
                    | models.Q(product__isnull=True, own_product__isnull=False)
                ),
                name="india_cart_item_exactly_one_product",
            ),
        ]

    @property
    def display_product(self):
        return self.own_product if self.own_product_id else self.product

    @property
    def is_own_inventory(self):
        return self.own_product_id is not None

    @property
    def line_total(self):
        if self.quantity is None or self.price is None:
            return None
        return self.quantity * self.price

    def __str__(self):
        product = self.display_product
        return f"{product.name if product else 'Product'} x {self.quantity}"



class IndiaOrder(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Processing", "Processing"),
        ("Shipped", "Shipped"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("ONLINE", "Online Payment"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
        ("Refunded", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="india_orders",
    )
    address = models.ForeignKey(
        "customer.Address",
        on_delete=models.PROTECT,
        related_name="india_orders",
    )
    shipping_full_name = models.CharField(max_length=150, blank=True, default="")
    shipping_mobile = models.CharField(max_length=15, blank=True, default="")
    shipping_address_line = models.CharField(max_length=255, blank=True, default="")
    shipping_city = models.CharField(max_length=100, blank=True, default="")
    shipping_state = models.CharField(max_length=100, blank=True, default="")
    shipping_pincode = models.CharField(max_length=10, blank=True, default="")
    order_number = models.CharField(max_length=40, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default="COD",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="Pending",
    )
    courier_name = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    razorpay_order_id = models.CharField(
        max_length=100, blank=True, null=True, unique=True
    )
    razorpay_payment_id = models.CharField(
        max_length=100, blank=True, null=True, unique=True
    )
    razorpay_amount_paise = models.PositiveBigIntegerField(
        null=True, blank=True
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    # BYXOM manual supplier/reselling operations.
    supplier_platform = models.CharField(
        max_length=40,
        default="Meesho",
        blank=True,
        help_text="External platform used to source this order.",
    )
    supplier_order_id = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="External supplier order ID; enter after placing the supplier order.",
    )
    supplier_ordered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Recorded automatically when a supplier order ID is saved.",
    )
    supplier_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total actual amount paid to the supplier for this BYXOM order.",
    )
    customer_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Recorded when Admin confirms a pending order after the customer call.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number
    delivered_at = models.DateTimeField(null=True, blank=True)
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    verified_payment_method = models.CharField(max_length=30, blank=True, default="")



class IndiaOrderItem(models.Model):
    order = models.ForeignKey(
        IndiaOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.PROTECT,
        related_name="india_order_items",
        null=True,
        blank=True,
    )
    own_product = models.ForeignKey(
        IndiaProduct,
        on_delete=models.PROTECT,
        related_name="india_order_items",
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)

    STOCK_POOL_CHOICES = [
        ("byxom", "BYXOM Inventory"),
        ("supplier", "Supplier-Reported Stock"),
        ("own", "BYXOM India Product Stock"),
        ("none", "Not Reserved"),
    ]
    stock_pool = models.CharField(
        max_length=10,
        choices=STOCK_POOL_CHOICES,
        default="none",
    )
    stock_deducted = models.BooleanField(default=False)
    stock_restored = models.BooleanField(default=False)
    stock_deducted_at = models.DateTimeField(null=True, blank=True)
    stock_restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=False, own_product__isnull=True)
                    | models.Q(product__isnull=True, own_product__isnull=False)
                ),
                name="india_order_item_exactly_one_product",
            ),
        ]

    @property
    def display_product(self):
        return self.own_product if self.own_product_id else self.product

    @property
    def is_own_inventory(self):
        return self.own_product_id is not None

    @property
    def line_total(self):
        if self.quantity is None or self.price is None:
            return None
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class IndiaWishlistItem(models.Model):
    """A product saved to a customer's All India wishlist."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="india_wishlist_items",
    )
    product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="uniq_india_wish_user_prod",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.product.name}"


class IndiaProductReview(models.Model):
    """Moderated review by a customer with a delivered All India order."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="india_product_reviews",
    )
    product = models.ForeignKey(
        ResellingProduct,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order_item = models.ForeignKey(
        IndiaOrderItem,
        on_delete=models.PROTECT,
        related_name="product_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=3000)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="uniq_india_review_user_prod",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.order_item_id or not self.product_id or not self.user_id:
            return
        order = self.order_item.order
        if self.order_item.product_id != self.product_id:
            raise ValidationError("The review product must match the order item.")
        if order.user_id != self.user_id:
            raise ValidationError("Only the purchasing customer may review this item.")
        if order.status != "Delivered":
            raise ValidationError("A review requires a delivered order.")

    def __str__(self):
        return f"{self.product.name} - {self.rating}/5"
class IndiaOrderNotification(models.Model):
    """In-app notifications for BYXOM All India orders."""

    EVENT_CHOICES = [
        ("ORDER_PLACED", "Order Placed"),
        ("CONFIRMED", "Order Confirmed"),
        ("PROCESSING", "Order Processing"),
        ("SHIPPED", "Order Shipped"),
        ("DELIVERED", "Order Delivered"),
        ("CANCELLED", "Order Cancelled"),
        ("PAYMENT_CONFIRMED", "Payment Confirmed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="india_order_notifications",
    )
    order = models.ForeignKey(
        IndiaOrder,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    title = models.CharField(max_length=120)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "event"],
                name="uniq_india_order_notification_event",
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.user}"

class IndiaShoppingSettings(models.Model):
    """Admin-controlled rules for BYXOM All India Shopping."""

    coins_enabled = models.BooleanField(default=True)
    diwali_gift_enabled = models.BooleanField(default=False)
    diwali_gift_name = models.CharField(
        max_length=150,
        default="BYXOM Diwali Special Gift",
    )
    diwali_gift_description = models.TextField(
        blank=True,
        default="A special gift for eligible delivered orders.",
    )
    return_window_days = models.PositiveSmallIntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
    )
    card_discount_enabled = models.BooleanField(default=True)
    card_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("50"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "All India Shopping Settings"
        verbose_name_plural = "All India Shopping Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return "BYXOM All India Shopping Settings"


class IndiaOrderReward(models.Model):
    """One reward/gift entitlement record per All India order."""

    GIFT_STATUS_CHOICES = [
        ("NOT_ELIGIBLE", "Not Eligible"),
        ("ELIGIBLE", "Gift Eligible"),
        ("PROCESSING", "Gift Being Prepared"),
        ("SHIPPED", "Gift Shipped"),
        ("DELIVERED", "Gift Delivered"),
        ("CANCELLED", "Gift Cancelled"),
    ]

    order = models.OneToOneField(
        IndiaOrder,
        on_delete=models.CASCADE,
        related_name="reward_record",
    )
    coins_awarded = models.PositiveIntegerField(default=0)
    coins_awarded_at = models.DateTimeField(null=True, blank=True)
    gift_name = models.CharField(max_length=150, blank=True, default="")
    gift_description = models.TextField(blank=True, default="")
    gift_status = models.CharField(
        max_length=20,
        choices=GIFT_STATUS_CHOICES,
        default="NOT_ELIGIBLE",
    )
    gift_shipped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "All India Order Reward"
        verbose_name_plural = "All India Order Rewards"

    def __str__(self):
        return f"Rewards for {self.order.order_number}"


class IndiaCoinTransaction(models.Model):
    """Auditable coin ledger for All India orders, separate from local orders."""

    TRANSACTION_CHOICES = [
        ("CREDIT", "Reward Credit"),
        ("REVERSAL", "Reward Reversal"),
    ]
    REASON_CHOICES = [
        ("DELIVERY_REWARD", "Delivered Order Reward"),
        ("RETURN_REVERSAL", "Return Reward Reversal"),
    ]

    wallet = models.ForeignKey(
        "customer.Wallet",
        on_delete=models.PROTECT,
        related_name="india_coin_transactions",
    )
    order = models.ForeignKey(
        IndiaOrder,
        on_delete=models.PROTECT,
        related_name="coin_transactions",
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    coins = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    balance_after = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "-created_at"]),
            models.Index(fields=["order", "reason"]),
        ]
        verbose_name = "All India Coin Transaction"
        verbose_name_plural = "All India Coin Transactions"

    def __str__(self):
        sign = "+" if self.transaction_type == "CREDIT" else "-"
        return f"{self.order.order_number}: {sign}{self.coins} coins"


class IndiaReturnRequest(models.Model):
    """Customer return request for an item from a delivered All India order."""

    STATUS_CHOICES = [
        ("REQUESTED", "Requested"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("PICKUP_SCHEDULED", "Pickup Scheduled"),
        ("RECEIVED", "Item Received"),
        ("REFUNDED", "Refunded"),
        ("CLOSED", "Closed"),
    ]
    ACTIVE_STATUSES = [
        "REQUESTED",
        "APPROVED",
        "PICKUP_SCHEDULED",
        "RECEIVED",
    ]

    order = models.ForeignKey(
        IndiaOrder,
        on_delete=models.CASCADE,
        related_name="return_requests",
    )
    order_item = models.ForeignKey(
        IndiaOrderItem,
        on_delete=models.PROTECT,
        related_name="return_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="india_return_requests",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reason = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="REQUESTED",
    )
    admin_note = models.TextField(blank=True, default="")
    refund_finance_transaction = models.OneToOneField(
        "FinanceTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="india_return_refund",
        help_text=(
            "Select the successful, verified outgoing customer-refund "
            "transaction that matches this return and order."
        ),
    )
    refund_processed_at = models.DateTimeField(null=True, blank=True)
    refund_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_india_return_refunds",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order_item"],
                condition=models.Q(status__in=[
                    "REQUESTED", "APPROVED", "PICKUP_SCHEDULED", "RECEIVED"
                ]),
                name="uniq_active_india_return_item",
            ),
        ]
        verbose_name = "All India Return Request"
        verbose_name_plural = "All India Return Requests"

    def clean(self):
        super().clean()
        if self.order_item_id and self.order_id:
            if self.order_item.order_id != self.order_id:
                raise ValidationError("The return item must belong to the selected order.")
            if self.quantity > self.order_item.quantity:
                raise ValidationError("Return quantity cannot exceed the purchased quantity.")
        if self.user_id and self.order_id:
            if self.order.user_id != self.user_id:
                raise ValidationError("Only the order owner can request a return.")

    def __str__(self):
        return f"Return request for {self.order.order_number}"
