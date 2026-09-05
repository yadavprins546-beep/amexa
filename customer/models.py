from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.text import slugify
import math

from .storage_backends import private_delivery_document_storage


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
        ('PICKER', 'Order Picker'),
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


class CustomerSavedLocation(models.Model):
    """
    Permanent current/delivery GPS pin for a customer.
    Survives browser/app restarts and future logins.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_location",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    address_text = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Customer Saved Location"
        verbose_name_plural = "Customer Saved Locations"

    def __str__(self):
        return f"{self.user} @ {self.latitude}, {self.longitude}"


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
    SHOP_TYPE_CHOICES = [
        ("GROCERY", "Grocery / Kirana"),
        ("FRUITS_VEGETABLES", "Fruits & Vegetables"),
        ("DAIRY", "Dairy"),
        ("BAKERY", "Bakery"),
        ("RESTAURANT", "Restaurant / Cloud Kitchen"),
        ("PHARMACY", "Pharmacy"),
        ("ELECTRONICS", "Electronics"),
        ("FASHION", "Fashion"),
        ("GENERAL", "General Store"),
        ("OTHER", "Other"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_shops')
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=180, blank=True)
    shop_type = models.CharField(
        max_length=30,
        choices=SHOP_TYPE_CHOICES,
        default="GROCERY",
    )
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    gstin = models.CharField(max_length=15, blank=True)
    fssai_number = models.CharField(max_length=14, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=True)
    auto_accept_orders = models.BooleanField(default=False)
    minimum_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "shop"
            candidate = base_slug
            number = 2
            while Shop.objects.exclude(pk=self.pk).filter(
                slug=candidate
            ).exists():
                candidate = f"{base_slug}-{number}"
                number += 1
            self.slug = candidate
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
        return self.is_active and self.is_online

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
    pack_size = models.CharField(
        max_length=40,
        default="1 unit",
        help_text="Examples: 500 g, 1 litre, Pack of 6",
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "product"
            candidate = base_slug
            number = 2
            while Product.objects.exclude(pk=self.pk).filter(
                slug=candidate
            ).exists():
                candidate = f"{base_slug}-{number}"
                number += 1
            self.slug = candidate
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
    barcode = models.CharField(max_length=50, db_index=True)
    barcode_type = models.CharField(max_length=10, choices=BARCODE_TYPES, default='EAN')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=["product", "barcode"],
                name="unique_barcode_per_product",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductBarcode.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.barcode} - {self.product.name}'


class InventoryBatch(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("DAMAGED", "Damaged"),
        ("DEPLETED", "Depleted"),
    ]

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="inventory_batches",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory_batches",
    )
    batch_number = models.CharField(max_length=80, blank=True)
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_available = models.PositiveIntegerField(default=0)
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expiry_date", "created_at"]
        indexes = [
            models.Index(fields=["shop", "status", "expiry_date"]),
            models.Index(fields=["shop", "product", "status"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.batch_number or self.pk}"


class BadInventoryRecord(models.Model):
    REASON_CHOICES = [
        ("EXPIRED", "Expired"),
        ("DAMAGED", "Damaged"),
        ("CUSTOMER_RETURN", "Customer Return"),
        ("MISSING", "Missing"),
        ("OTHER", "Other"),
    ]

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="bad_inventory_records",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="bad_inventory_records",
    )
    batch = models.ForeignKey(
        InventoryBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bad_inventory_records",
    )
    quantity = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_bad_inventory",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "reason", "created_at"]),
        ]

    @property
    def loss_amount(self):
        return self.unit_cost * self.quantity

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.reason}"



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


# =========================================================
# DELIVERY PARTNER ONBOARDING / KYC / BANK VERIFICATION
# =========================================================

class DeliveryPartnerProfile(models.Model):
    VERIFICATION_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Verification Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("BLOCKED", "Blocked"),
    ]

    VEHICLE_TYPE_CHOICES = [
        ("BICYCLE", "Bicycle"),
        ("BIKE", "Bike"),
        ("SCOOTER", "Scooter"),
        ("EV", "Electric Vehicle"),
        ("OTHER", "Other"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_profile",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    profile_photo = models.ImageField(
        upload_to="private/delivery/profile/",
        null=True,
        blank=True,
    )
    full_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        blank=True,
    )
    vehicle_number = models.CharField(max_length=20, blank=True)

    # =====================================================
    # RIDER PERMANENT LIVE LOCATION
    # Used before order assignment so AMEXA can choose
    # a nearby online rider.
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
    location_accuracy = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GPS accuracy in metres.",
    )
    current_area = models.CharField(max_length=180, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    onboarding_step = models.PositiveSmallIntegerField(default=1)
    terms_accepted = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_delivery_profiles",
    )
    rejection_reason = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verification_status", "created_at"]),
        ]

    @property
    def is_approved(self):
        return self.verification_status == "APPROVED"

    @property
    def can_access_dashboard(self):
        return (
            self.is_approved
            and self.user.is_active
            and getattr(self.user, "role", "") == "DELIVERY"
        )

    def submit_for_verification(self):
        self.verification_status = "PENDING"
        self.submitted_at = timezone.now()
        self.reviewed_at = None
        self.reviewed_by = None
        self.rejection_reason = ""
        self.save(
            update_fields=[
                "verification_status",
                "submitted_at",
                "reviewed_at",
                "reviewed_by",
                "rejection_reason",
                "updated_at",
            ]
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if (
            self.verification_status != "APPROVED"
            and self.user.is_active_delivery
        ):
            type(self.user).objects.filter(pk=self.user_id).update(
                is_active_delivery=False
            )
            self.user.is_active_delivery = False

    def __str__(self):
        return f"{self.user} - {self.get_verification_status_display()}"


class DeliveryPartnerDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("AADHAAR_FRONT", "Aadhaar Front"),
        ("AADHAAR_BACK", "Aadhaar Back"),
        ("PAN", "PAN Card"),
        ("DRIVING_LICENCE", "Driving Licence"),
        ("VEHICLE_RC", "Vehicle RC"),
        ("SELFIE", "Verification Selfie"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]

    profile = models.ForeignKey(
        DeliveryPartnerProfile,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
    )
    document_file = models.FileField(
        upload_to="private/delivery/documents/",
        storage=private_delivery_document_storage,
    )
    document_number_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    document_number_last4 = models.CharField(
        max_length=4,
        blank=True,
        editable=False,
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_delivery_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "document_type"],
                name="unique_delivery_profile_document_type",
            ),
        ]

    def set_document_number(self, number):
        normalized = "".join(
            character
            for character in str(number or "").upper()
            if character.isalnum()
        )
        self.document_number_last4 = normalized[-4:]
        self.document_number_hash = (
            salted_hmac(
                "amexa.delivery.document",
                normalized,
            ).hexdigest()
            if normalized
            else ""
        )

    @property
    def masked_document_number(self):
        if not self.document_number_last4:
            return "Not provided"
        return f"XXXX-XXXX-{self.document_number_last4}"

    def __str__(self):
        return f"{self.profile.user} - {self.get_document_type_display()}"


class DeliveryPartnerBankAccount(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]

    profile = models.OneToOneField(
        DeliveryPartnerProfile,
        on_delete=models.CASCADE,
        related_name="bank_account",
    )
    account_holder_name = models.CharField(max_length=150)
    bank_name = models.CharField(max_length=150, blank=True)
    account_number_hash = models.CharField(
        max_length=64,
        editable=False,
    )
    account_number_last4 = models.CharField(
        max_length=4,
        editable=False,
    )
    ifsc_code = models.CharField(max_length=11)
    cancelled_cheque = models.FileField(
        upload_to="private/delivery/bank/",
        storage=private_delivery_document_storage,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_delivery_bank_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Partner Bank Account"
        verbose_name_plural = "Delivery Partner Bank Accounts"

    def set_account_number(self, account_number):
        normalized = "".join(
            character
            for character in str(account_number or "")
            if character.isdigit()
        )
        self.account_number_last4 = normalized[-4:]
        self.account_number_hash = (
            salted_hmac(
                "amexa.delivery.bank",
                normalized,
            ).hexdigest()
            if normalized
            else ""
        )

    @property
    def masked_account_number(self):
        return f"XXXXXX{self.account_number_last4}"

    def save(self, *args, **kwargs):
        self.ifsc_code = (self.ifsc_code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user} - {self.masked_account_number}"


# =========================================================
# SHOPKEEPER ONBOARDING / KYC / BANK VERIFICATION
# =========================================================

class ShopkeeperProfile(models.Model):
    VERIFICATION_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Verification Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("BLOCKED", "Blocked"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shopkeeper_profile",
    )
    shop = models.OneToOneField(
        Shop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopkeeper_profile",
    )
    owner_photo = models.ImageField(
        upload_to="shopkeeper/profile/",
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    residential_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    onboarding_step = models.PositiveSmallIntegerField(default=1)
    terms_accepted = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_shopkeeper_profiles",
    )
    rejection_reason = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verification_status", "created_at"]),
        ]

    @property
    def is_approved(self):
        return self.verification_status == "APPROVED"

    @property
    def can_access_dashboard(self):
        return (
            self.is_approved
            and self.user.is_active
            and self.user.role == "SHOPKEEPER"
            and self.shop_id is not None
            and self.shop.is_active
        )

    def submit_for_verification(self):
        self.verification_status = "PENDING"
        self.submitted_at = timezone.now()
        self.reviewed_at = None
        self.reviewed_by = None
        self.rejection_reason = ""
        self.save(
            update_fields=[
                "verification_status",
                "submitted_at",
                "reviewed_at",
                "reviewed_by",
                "rejection_reason",
                "updated_at",
            ]
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.verification_status != "APPROVED" and self.shop_id:
            Shop.objects.filter(pk=self.shop_id).update(
                is_active=False,
                is_online=False,
            )

    def __str__(self):
        return f"{self.user} - {self.get_verification_status_display()}"


class ShopkeeperDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("AADHAAR_FRONT", "Aadhaar Front"),
        ("AADHAAR_BACK", "Aadhaar Back"),
        ("PAN", "PAN Card"),
        ("GST_CERTIFICATE", "GST Certificate"),
        ("FSSAI_CERTIFICATE", "FSSAI / Food Licence"),
        ("OWNER_SELFIE", "Owner Live Selfie"),
        ("SHOP_FRONT", "Shop Front Photo"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]

    profile = models.ForeignKey(
        ShopkeeperProfile,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
    )
    document_file = models.FileField(
        upload_to="private/shopkeeper/documents/",
        storage=private_delivery_document_storage,
    )
    document_number_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    document_number_last4 = models.CharField(
        max_length=4,
        blank=True,
        editable=False,
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_shopkeeper_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "document_type"],
                name="unique_shopkeeper_profile_document_type",
            ),
        ]

    def set_document_number(self, number):
        normalized = "".join(
            character
            for character in str(number or "").upper()
            if character.isalnum()
        )
        self.document_number_last4 = normalized[-4:]
        self.document_number_hash = (
            salted_hmac(
                "amexa.shopkeeper.document",
                normalized,
            ).hexdigest()
            if normalized
            else ""
        )

    @property
    def masked_document_number(self):
        if not self.document_number_last4:
            return "Not provided"
        return f"XXXX-XXXX-{self.document_number_last4}"

    def __str__(self):
        return f"{self.profile.user} - {self.get_document_type_display()}"


class ShopkeeperBankAccount(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]

    profile = models.OneToOneField(
        ShopkeeperProfile,
        on_delete=models.CASCADE,
        related_name="bank_account",
    )
    account_holder_name = models.CharField(max_length=150)
    bank_name = models.CharField(max_length=150, blank=True)
    account_number_hash = models.CharField(max_length=64, editable=False)
    account_number_last4 = models.CharField(max_length=4, editable=False)
    ifsc_code = models.CharField(max_length=11)
    cancelled_cheque = models.FileField(
        upload_to="private/shopkeeper/bank/",
        storage=private_delivery_document_storage,
        null=True,
        blank=True,
    )
    upi_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    rejection_reason = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_shopkeeper_bank_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_account_number(self, account_number):
        normalized = "".join(
            character
            for character in str(account_number or "")
            if character.isdigit()
        )
        self.account_number_last4 = normalized[-4:]
        self.account_number_hash = (
            salted_hmac(
                "amexa.shopkeeper.bank",
                normalized,
            ).hexdigest()
            if normalized
            else ""
        )

    @property
    def masked_account_number(self):
        return f"XXXXXX{self.account_number_last4}"

    def save(self, *args, **kwargs):
        self.ifsc_code = (self.ifsc_code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user} - {self.masked_account_number}"


class PickerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="picker_profile",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="pickers",
    )
    employee_code = models.CharField(max_length=30, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shop", "user__name"]

    def save(self, *args, **kwargs):
        if not self.employee_code:
            self.employee_code = f"AMXP-{self.user_id or 'NEW'}-{timezone.now():%H%M%S}"
        super().save(*args, **kwargs)
        type(self.user).objects.filter(pk=self.user_id).update(
            role="PICKER",
            is_staff=False,
            is_superuser=False,
        )

    def __str__(self):
        return f"{self.user.name} - {self.shop.name}"


# =========================================================
# DELIVERY INCENTIVES / TARGET PROGRESS
# =========================================================

class DeliveryIncentive(models.Model):
    INCENTIVE_TYPE_CHOICES = [
        ("DAILY", "Daily Target"),
        ("WEEKLY", "Weekly Target"),
        ("PEAK_HOURS", "Peak Hours"),
        ("STREAK", "Target Streak"),
        ("FESTIVAL", "Festival Bonus"),
    ]

    title = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    incentive_type = models.CharField(
        max_length=20,
        choices=INCENTIVE_TYPE_CHOICES,
        default="DAILY",
    )
    required_deliveries = models.PositiveIntegerField(default=10)
    bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100,
    )
    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(null=True, blank=True)
    peak_start_time = models.TimeField(null=True, blank=True)
    peak_end_time = models.TimeField(null=True, blank=True)
    terms = models.TextField(
        blank=True,
        default="Only successfully delivered orders count towards this target.",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_delivery_incentives",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["is_active", "start_at", "end_at"]),
        ]

    @property
    def is_currently_active(self):
        now = timezone.now()
        return (
            self.is_active
            and self.start_at <= now
            and (self.end_at is None or now <= self.end_at)
        )

    def __str__(self):
        return f"{self.title} - ₹{self.bonus_amount}"


class DeliveryIncentiveProgress(models.Model):
    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("CREDITED", "Bonus Credited"),
        ("EXPIRED", "Expired"),
    ]

    incentive = models.ForeignKey(
        DeliveryIncentive,
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    delivery_partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_incentive_progress",
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    completed_deliveries = models.PositiveIntegerField(default=0)
    bonus_earned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="IN_PROGRESS",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    credited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "incentive",
                    "delivery_partner",
                    "period_start",
                ],
                name="unique_delivery_incentive_period",
            ),
        ]
        indexes = [
            models.Index(fields=["delivery_partner", "status"]),
            models.Index(fields=["period_start", "period_end"]),
        ]

    @property
    def progress_percentage(self):
        target = self.incentive.required_deliveries
        if target <= 0:
            return 100
        return min(
            100,
            int(self.completed_deliveries * 100 / target),
        )

    @property
    def remaining_deliveries(self):
        return max(
            0,
            self.incentive.required_deliveries
            - self.completed_deliveries,
        )

    def __str__(self):
        return (
            f"{self.delivery_partner} - {self.incentive.title} "
            f"({self.completed_deliveries}/"
            f"{self.incentive.required_deliveries})"
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


class OrderPickingTask(models.Model):
    STATUS_CHOICES = [
        ("WAITING", "Waiting for Picker"),
        ("ACCEPTED", "Accepted by Picker"),
        ("PICKING", "Picking Items"),
        ("PACKED", "Packed / Rider Assigned"),
        ("HANDED_OVER", "Handed to Rider"),
        ("CANCELLED", "Cancelled"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="picking_task",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="picking_tasks",
    )
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="picking_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="WAITING",
        db_index=True,
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    packed_at = models.DateTimeField(null=True, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "status", "created_at"]),
        ]

    @property
    def required_units(self):
        return sum(item.required_quantity for item in self.picking_items.all())

    @property
    def picked_units(self):
        return sum(item.picked_quantity for item in self.picking_items.all())

    @property
    def progress_percentage(self):
        required = self.required_units
        if required <= 0:
            return 0
        return min(100, int((self.picked_units / required) * 100))

    @property
    def is_complete(self):
        items = list(self.picking_items.all())
        return bool(items) and all(item.is_complete for item in items)

    def __str__(self):
        return f"{self.order.order_number} - {self.get_status_display()}"


class OrderPickingItem(models.Model):
    task = models.ForeignKey(
        OrderPickingTask,
        on_delete=models.CASCADE,
        related_name="picking_items",
    )
    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="picking_item",
    )
    required_quantity = models.PositiveIntegerField(default=1)
    picked_quantity = models.PositiveIntegerField(default=0)
    last_scanned_barcode = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_item__created_at"]

    @property
    def remaining_quantity(self):
        return max(0, self.required_quantity - self.picked_quantity)

    @property
    def is_complete(self):
        return self.picked_quantity >= self.required_quantity

    def __str__(self):
        return f"{self.order_item} ({self.picked_quantity}/{self.required_quantity})"


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

class Banner(models.Model):
    title = models.CharField(max_length=150, blank=True)
    image = models.ImageField(upload_to="banners/")
    link = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return self.title or f"Banner {self.id}"