from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Address, Cart, CartItem, Category, Order, OrderStatusHistory, OTPVerification, Product, Shop


class CustomerUserTests(TestCase):
    def test_create_user_with_email_and_phone(self):
        user = get_user_model().objects.create_user(
            email='customer@example.com',
            password='securepass123',
            name='Amina',
            phone='07000000000',
        )

        self.assertEqual(user.email, 'customer@example.com')
        self.assertEqual(user.name, 'Amina')
        self.assertEqual(user.phone, '07000000000')
        self.assertTrue(user.check_password('securepass123'))


class AddressTests(TestCase):
    def test_default_address_is_set_and_previous_default_is_cleared(self):
        user = get_user_model().objects.create_user(
            email='addr@example.com',
            password='securepass123',
            name='Amina',
            phone='07000000000',
        )

        first = Address.objects.create(
            user=user,
            full_name='Amina',
            mobile='07000000000',
            address_line='12 Green Road',
            city='Lagos',
            state='Lagos',
            pincode='101233',
            address_type='Home',
            is_default=True,
        )
        second = Address.objects.create(
            user=user,
            full_name='Amina',
            mobile='07000000000',
            address_line='88 Yellow Avenue',
            city='Abuja',
            state='FCT',
            pincode='900108',
            address_type='Work',
            is_default=True,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)


class CatalogBrowsingTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(
            name='Green Valley Store',
            slug='green-valley-store',
            address='123 Main Street',
            phone='9999999999',
            rating=4.8,
        )
        self.category = Category.objects.create(name='Grocery', slug='grocery')
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name='Fresh Apples',
            slug='fresh-apples',
            description='Crisp apples from local farms',
            price=120.00,
            mrp=150.00,
            stock_quantity=10,
        )

    def test_shop_detail_page_renders(self):
        response = self.client.get(reverse('shop_detail', args=[self.shop.slug]))
        self.assertEqual(response.status_code, 200)

    def test_category_products_page_renders(self):
        response = self.client.get(reverse('category_products', args=[self.category.slug]))
        self.assertEqual(response.status_code, 200)

    def test_product_detail_page_renders(self):
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)


class OtpAuthTests(TestCase):
    def test_otp_login_creates_user_and_authenticates(self):
        response = self.client.post(reverse('login'), {'name': 'Amina', 'phone': '07000000000'})

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(phone='07000000000')
        otp = OTPVerification.objects.get(phone='07000000000', user=user)

        verify_response = self.client.post(reverse('login'), {'name': 'Amina', 'phone': '07000000000', 'otp_code': otp.code})

        self.assertEqual(verify_response.status_code, 302)
        self.assertTrue(verify_response.wsgi_request.user.is_authenticated)


class OrderFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='orders@example.com',
            password='securepass123',
            name='Amina',
            phone='07000000000',
        )
        self.other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='securepass123',
            name='Bola',
            phone='08000000001',
        )
        self.shop = Shop.objects.create(
            name='Sharma General Store',
            slug='sharma-general-store',
            address='1 Main Road',
            phone='08000000000',
            rating=4.7,
        )
        self.category = Category.objects.create(name='Dairy', slug='dairy')
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name='Milk 1L',
            slug='milk-1l',
            description='Fresh milk',
            price=60.00,
            mrp=70.00,
            stock_quantity=10,
        )
        self.address = Address.objects.create(
            user=self.user,
            full_name='Amina Yusuf',
            mobile='07000000000',
            address_line='12 Green Road',
            city='Lagos',
            state='Lagos',
            pincode='101233',
            address_type='Home',
            is_default=True,
        )

    def _create_order(self):
        self.client.force_login(self.user)
        self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 2})
        self.client.post(reverse('checkout'), {'address_id': self.address.id})
        return Order.objects.get(user=self.user)

    def test_orders_page_and_detail_render_for_customer(self):
        order = self._create_order()

        response = self.client.get(reverse('orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)

        detail_response = self.client.get(reverse('order_detail', args=[order.order_number]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Order Tracking')

    def test_pending_order_can_be_cancelled_and_restores_stock(self):
        order = self._create_order()

        cancel_response = self.client.post(
            reverse('cancel_order', args=[order.id]),
            {'reason': 'Changed my mind', 'description': ''},
        )

        self.assertEqual(cancel_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'Cancelled')
        self.assertEqual(order.cancellation_reason, 'Changed my mind')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(OrderStatusHistory.objects.filter(order=order, status='Cancelled').exists())

    def test_other_user_cannot_access_order_detail(self):
        order = self._create_order()
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('order_detail', args=[order.order_number]))

        self.assertEqual(response.status_code, 404)


class CartTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='cart@example.com',
            password='securepass123',
            name='Amina',
            phone='07000000000',
        )
        self.shop = Shop.objects.create(
            name='Sharma General Store',
            slug='sharma-general-store',
            address='1 Main Road',
            phone='08000000000',
            rating=4.7,
        )
        self.other_shop = Shop.objects.create(
            name='Another Store',
            slug='another-store',
            address='2 Main Road',
            phone='08111111111',
            rating=4.3,
        )
        self.category = Category.objects.create(name='Dairy', slug='dairy')
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name='Milk 1L',
            slug='milk-1l',
            description='Fresh milk',
            price=60.00,
            mrp=70.00,
            stock_quantity=5,
        )
        self.other_product = Product.objects.create(
            shop=self.other_shop,
            category=self.category,
            name='Bread',
            slug='bread',
            description='Fresh bread',
            price=40.00,
            mrp=50.00,
            stock_quantity=8,
        )

    def test_add_to_cart_creates_cart_item(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 2})

        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.price, self.product.price)

    def test_cross_shop_cart_conflict_requires_clear_or_keep(self):
        self.client.force_login(self.user)
        self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 1})

        response = self.client.post(reverse('cart_add', args=[self.other_product.id]), {'quantity': 1})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your cart contains products from another shop')

    def test_quantity_update_caps_at_available_stock(self):
        self.client.force_login(self.user)
        self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 1})
        item = CartItem.objects.get(product=self.product)

        response = self.client.post(reverse('cart_update', args=[item.id]), {'quantity': 99})

        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.quantity, self.product.stock_quantity)

    def test_checkout_creates_order_and_reduces_stock(self):
        self.client.force_login(self.user)
        self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 2})
        address = Address.objects.create(
            user=self.user,
            full_name='Amina Yusuf',
            mobile='07000000000',
            address_line='12 Green Road',
            city='Lagos',
            state='Lagos',
            pincode='101233',
            address_type='Home',
            is_default=True,
        )

        response = self.client.post(reverse('checkout'), {'address_id': address.id})

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.address, address)
        self.assertEqual(order.total_amount, self.product.price * 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
