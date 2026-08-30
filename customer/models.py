from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import math


class CustomerUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomerUser(AbstractUser):
    ROLE_CHOICES = [
        ('CUSTOMER', 'Customer'),
        ('SHOPKEEPER', 'Shopkeeper'),
        ('DELIVERY', 'Delivery Partner'),
        ('ADMIN', 'Admin'),
    ]

    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, blank=True)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='CUSTOMER')
    is_active_delivery = models.BooleanField(default=False)  # Delivery Boy Online/Offline status
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomerUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'phone']

    def __str__(self):
        return f"{self.email} ({self.role})"


class Address(models.Model):
    ADDRESS_TYPES = [
        ('Home', 'Home'),
        ('Work', 'Work'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='Home')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).exists():
            self.is_default = True

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} - {self.city}'


class OTPVerification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otp_verifications')
    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at and self.attempts < 3

    def __str__(self):
        return f'{self.phone} - {self.code}'


class Shop(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_shops')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def distance_to(self, user_lat, user_lon):
        """Haversine Distance calculation in KM"""
        if not (self.latitude and self.longitude and user_lat and user_lon):
            return 2.5
        R = 6371.0  # Earth radius in KM
        dlat = math.radians(float(user_lat) - float(self.latitude))
        dlon = math.radians(float(user_lon) - float(self.longitude))
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(float(self.latitude))) * math.cos(math.radians(float(user_lat))) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 2)

    @property
    def is_open(self):
        return self.is_active

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def discount_percentage(self):
        if not self.mrp or self.mrp <= 0:
            return 0
        return int(((self.mrp - self.price) / self.mrp) * 100)

    @property
    def availability(self):
        return 'In Stock' if self.stock_quantity > 0 else 'Out of Stock'

    def __str__(self):
        return self.name


class ProductBarcode(models.Model):
    BARCODE_TYPES = [
        ('UPC', 'UPC'),
        ('EAN', 'EAN'),
        ('GTIN', 'GTIN'),
        ('OTHER', 'Other'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='barcodes')
    barcode = models.CharField(max_length=50, unique=True, db_index=True)
    barcode_type = models.CharField(max_length=10, choices=BARCODE_TYPES, default='EAN')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductBarcode.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.barcode} - {self.product.name}'



class MasterOrder(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Partially Completed", "Partially Completed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="master_orders",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name="master_orders",
    )
    master_order_number = models.CharField(max_length=30, unique=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coins_redeemed = models.PositiveIntegerField(default=0)
    coin_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.master_order_number


class Order(models.Model):
    master_order = models.ForeignKey(
        MasterOrder,
        on_delete=models.CASCADE,
        related_name="shop_orders",
        blank=True,
        null=True,
    )
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Preparing', 'Preparing'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='orders')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, related_name='orders', blank=True, null=True)
    order_number = models.CharField(max_length=20, unique=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
    payment_status = models.CharField(max_length=20, default='Pending')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='Pending')
    delivery_otp = models.CharField(max_length=6, blank=True, null=True)  # Secure Delivery Verification
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=20)
    cancellation_reason = models.CharField(max_length=100, blank=True)
    cancellation_description = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def item_count(self):
        return self.items.count()

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    def can_cancel(self):
        return self.status in {'Pending', 'Confirmed'}

    def create_status_history(self, status, note=''):
        return OrderStatusHistory.objects.create(order=self, status=status, note=note)

    def __str__(self):
        return self.order_number


class DeliveryAssignment(models.Model):
    STATUS_CHOICES = [
        ('Assigned', 'Assigned'),
        ('Accepted', 'Accepted'),
        ('Picked', 'Picked Up'),
        ('Completed', 'Completed'),
        ('Rejected', 'Rejected'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='delivery_assignments')
    delivery_partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deliveries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Assigned')
    assigned_at = models.DateTimeField(auto_now_add=True)

    # Persistent delivery-stage timestamps.
    # These keep dashboard timers correct even after refresh/re-login.
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    out_for_delivery_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # =====================================================
    # RIDER LIVE LOCATION
    # =====================================================
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    location_updated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Order {self.order.order_number} -> {self.delivery_partner.name} ({self.status})"


class DeliverySupportRequest(models.Model):
    REQUEST_TYPES = [
        ("HELP", "Help Request"),
        ("CLAIM", "Claim / Issue"),
    ]

    STATUS_CHOICES = [
        ("Open", "Open"),
        ("In Review", "In Review"),
        ("Resolved", "Resolved"),
        ("Rejected", "Rejected"),
    ]

    delivery_partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_support_requests",
    )
    request_type = models.CharField(
        max_length=10,
        choices=REQUEST_TYPES,
        default="HELP",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_support_requests",
    )
    subject = models.CharField(max_length=160)
    description = models.TextField()
    amount_claimed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Open",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.get_request_type_display()} - "
            f"{self.delivery_partner} - {self.status}"
        )


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=25)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.order.order_number} - {self.status}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, related_name='order_items', blank=True, null=True)
    product_name = models.CharField(max_length=150, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    @property
    def line_total(self):
        return self.quantity * self.price

    def __str__(self):
        return f'{self.product_name or self.product.name} x {self.quantity}'


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, related_name='carts', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Cart for {self.user.email}'

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    @property
    def line_total(self):
        return self.quantity * self.price

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class ShopProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='shop_listings')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='product_listings')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop'], name='unique_product_shop_listing')
        ]
        indexes = [
            models.Index(fields=['shop', 'is_active']),
            models.Index(fields=['product', 'is_active']),
        ]

    @property
    def discount_percentage(self):
        if not self.mrp or self.mrp <= 0:
            return 0
        return int(((self.mrp - self.selling_price) / self.mrp) * 100)

    @property
    def availability(self):
        return 'In Stock' if self.stock_quantity > 0 and self.is_active else 'Out of Stock'

    def __str__(self):
        return f'{self.product.name} - {self.shop.name}'

class Payment(models.Model):
    METHOD_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("NETBANKING", "Net Banking"),
        ("WALLET", "Wallet"),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
        ("Refund Pending", "Refund Pending"),
        ("Refunded", "Refunded"),
    ]

    master_order = models.OneToOneField(
        MasterOrder,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="COD")
    payment_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Pending")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_id = models.CharField(max_length=150, blank=True, null=True)
    gateway_name = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.master_order.master_order_number} - {self.payment_status}"


class Settlement(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Settled", "Settled"),
        ("On Hold", "On Hold"),
        ("Refunded", "Refunded"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="settlement",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="settlements",
    )
    product_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shop_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shop_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_partner_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amexa_earning = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    settled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.shop.name}"


# =========================================================
# COUPONS / OFFERS
# =========================================================

class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ("FIXED", "Fixed Amount"),
        ("PERCENTAGE", "Percentage"),
    ]

    code = models.CharField(max_length=30, unique=True, db_index=True)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)

    discount_type = models.CharField(
        max_length=15,
        choices=DISCOUNT_TYPES,
        default="FIXED",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    minimum_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    maximum_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Useful for percentage coupons. Leave blank for no cap.",
    )

    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total allowed uses. Leave blank for unlimited.",
    )
    per_user_limit = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_currently_valid(self):
        now = timezone.now()

        if not self.is_active:
            return False

        if self.start_at and now < self.start_at:
            return False

        if self.end_at and now > self.end_at:
            return False

        if (
            self.usage_limit is not None
            and self.usages.count() >= self.usage_limit
        ):
            return False

        return True

    def calculate_discount(self, subtotal):
        from decimal import Decimal

        subtotal = Decimal(subtotal or 0)

        if subtotal <= 0:
            return Decimal("0.00")

        if subtotal < self.minimum_order_amount:
            return Decimal("0.00")

        if self.discount_type == "PERCENTAGE":
            discount = (
                subtotal * self.discount_value / Decimal("100")
            )
        else:
            discount = self.discount_value

        if self.maximum_discount is not None:
            discount = min(discount, self.maximum_discount)

        discount = min(discount, subtotal)

        return discount.quantize(Decimal("0.01"))

    def can_user_use(self, user):
        if not user or not user.is_authenticated:
            return False

        if not self.is_currently_valid:
            return False

        return (
            self.usages.filter(user=user).count()
            < self.per_user_limit
        )

    def __str__(self):
        return self.code


class CouponUsage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupon_usages",
    )
    master_order = models.ForeignKey(
        MasterOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_usages",
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at"]
        indexes = [
            models.Index(fields=["coupon", "user"]),
        ]

    def __str__(self):
        return f"{self.coupon.code} - {self.user}"


# =========================================================
# MONTHLY GROCERY PACKS
# =========================================================

class MonthlyPack(models.Model):
    DISCOUNT_TYPES = [
        ("FIXED", "Fixed Amount"),
        ("PERCENTAGE", "Percentage"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monthly_packs",
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="monthly_packs",
    )

    name = models.CharField(
        max_length=120,
        default="Monthly Grocery Pack",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    discount_type = models.CharField(
        max_length=15,
        choices=DISCOUNT_TYPES,
        default="FIXED",
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_favorite = models.BooleanField(
        default=False,
    )

    last_ordered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at"]

    @property
    def subtotal(self):
        from decimal import Decimal

        total = Decimal("0.00")

        for item in self.items.select_related("product").all():
            total += (
                item.quantity
                * item.product.price
            )

        return total.quantize(
            Decimal("0.01")
        )

    @property
    def discount_amount(self):
        from decimal import Decimal

        subtotal = self.subtotal

        if subtotal <= 0:
            return Decimal("0.00")

        if self.discount_type == "PERCENTAGE":
            discount = (
                subtotal
                * self.discount_value
                / Decimal("100")
            )
        else:
            discount = self.discount_value

        discount = min(
            discount,
            subtotal,
        )

        return discount.quantize(
            Decimal("0.01")
        )

    @property
    def total_amount(self):
        from decimal import Decimal

        total = (
            self.subtotal
            - self.discount_amount
        )

        return max(
            Decimal("0.00"),
            total,
        ).quantize(
            Decimal("0.01")
        )

    @property
    def item_count(self):
        return sum(
            item.quantity
            for item in self.items.all()
        )

    def __str__(self):
        return (
            f"{self.name} - "
            f"{self.user} - "
            f"{self.shop.name}"
        )


class MonthlyPackItem(models.Model):
    pack = models.ForeignKey(
        MonthlyPack,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="monthly_pack_items",
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    added_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "pack",
                    "product",
                ],
                name=(
                    "unique_monthly_pack_product"
                ),
            ),
        ]

    @property
    def line_total(self):
        from decimal import Decimal

        total = (
            self.quantity
            * self.product.price
        )

        return Decimal(total).quantize(
            Decimal("0.01")
        )

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.pack_id
            and self.product_id
            and self.product.shop_id
            != self.pack.shop_id
        ):
            raise ValidationError(
                "Monthly pack items must belong "
                "to the same shop as the pack."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.product.name} x "
            f"{self.quantity}"
        )
# =========================================================
# ABOUT AMEXA
# Admin panel se editable content
# =========================================================

class AboutPage(models.Model):

    title = models.CharField(
        max_length=200,
        default="About AMEXA",
    )

    short_description = models.CharField(
        max_length=300,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    mission = models.TextField(
        blank=True,
    )

    vision = models.TextField(
        blank=True,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address = models.CharField(
        max_length=255,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "About AMEXA"
        verbose_name_plural = "About AMEXA"

    def __str__(self):
        return self.title
    # =========================================================
# HELP & SUPPORT
# Admin panel se editable customer support content
# =========================================================

class HelpSupport(models.Model):

    title = models.CharField(
        max_length=200,
        default="Help & Support",
    )

    short_description = models.CharField(
        max_length=300,
        blank=True,
        default="How can we help you?",
    )

    order_help = models.TextField(
        blank=True,
        help_text="Order related help information",
    )

    delivery_help = models.TextField(
        blank=True,
        help_text="Delivery related help information",
    )

    payment_help = models.TextField(
        blank=True,
        help_text="Payment related help information",
    )

    cancellation_help = models.TextField(
        blank=True,
        help_text="Cancellation and refund information",
    )

    faq = models.TextField(
        blank=True,
        help_text="Frequently asked questions",
    )

    support_phone = models.CharField(
        max_length=20,
        blank=True,
    )

    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
    )

    support_email = models.EmailField(
        blank=True,
    )

    support_hours = models.CharField(
        max_length=150,
        blank=True,
        default="9:00 AM - 9:00 PM",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Help & Support"
        verbose_name_plural = "Help & Support"

    def __str__(self):
        return self.title
# =========================================================
# PRIVACY POLICY
# Admin panel se editable privacy policy
# =========================================================

class PrivacyPolicy(models.Model):

    title = models.CharField(
        max_length=200,
        default="Privacy Policy",
    )

    content = models.TextField()

    is_active = models.BooleanField(
        default=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Privacy Policy"
        verbose_name_plural = "Privacy Policy"

    def __str__(self):
        return self.title
    # =========================================================
# TERMS & CONDITIONS
# Admin panel se editable terms and conditions
# =========================================================

class TermsConditions(models.Model):

    title = models.CharField(
        max_length=200,
        default="Terms & Conditions",
    )

    content = models.TextField()

    is_active = models.BooleanField(
        default=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Terms & Conditions"
        verbose_name_plural = "Terms & Conditions"

    def __str__(self):
        return self.title

# =========================================================
# SMART SEARCH ALIASES
# Admin se alternate / Hindi / Hinglish search words map honge
# Example: chappal -> slipper sandal footwear
# =========================================================

class SearchAlias(models.Model):
    keyword = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
    )

    mapped_text = models.CharField(
        max_length=255,
        help_text="Example: chappal -> slipper sandal footwear",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["keyword"]
        verbose_name = "Search Alias"
        verbose_name_plural = "Search Aliases"

    def __str__(self):
        return f"{self.keyword} → {self.mapped_text}"


# =========================================================
# AMEXA WALLET / COINS
# Customer coin balance + transaction history
# =========================================================

class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    coin_balance = models.PositiveIntegerField(default=0)
    lifetime_earned = models.PositiveIntegerField(default=0)
    lifetime_spent = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AMEXA Wallet"
        verbose_name_plural = "AMEXA Wallets"

    def __str__(self):
        return f"{self.user} - {self.coin_balance} coins"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("CREDIT", "Credit"),
        ("DEBIT", "Debit"),
    ]

    REASON_CHOICES = [
        ("ORDER_REWARD", "Order Reward"),
        ("REFERRAL", "Referral Reward"),
        ("PROMOTION", "Promotion"),
        ("REDEEM", "Coins Redeemed"),
        ("REFUND", "Coins Refunded"),
        ("REVERSAL", "Reward Reversal"),
        ("EXPIRED", "Coins Expired"),
        ("ADMIN", "Admin Adjustment"),
        ("OTHER", "Other"),
    ]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES,
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default="OTHER",
    )
    coins = models.PositiveIntegerField()
    balance_after = models.PositiveIntegerField(default=0)
    master_order = models.ForeignKey(
        MasterOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    description = models.CharField(max_length=255, blank=True)
    remaining_coins = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "-created_at"]),
            models.Index(fields=["reason"]),
            models.Index(fields=["wallet", "expires_at"]),
        ]
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"

    def __str__(self):
        sign = "+" if self.transaction_type == "CREDIT" else "-"
        return f"{self.wallet.user} {sign}{self.coins} coins"


class Referral(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made")
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_received")
    referral_code = models.CharField(max_length=40, db_index=True)
    reward_coins = models.PositiveIntegerField(default=50)
    is_rewarded = models.BooleanField(default=False)
    rewarded_at = models.DateTimeField(null=True, blank=True)
    qualifying_master_order = models.ForeignKey(MasterOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="referral_rewards")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} -> {self.referred_user}"

