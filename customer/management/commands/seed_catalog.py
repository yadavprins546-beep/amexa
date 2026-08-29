from django.core.management.base import BaseCommand

from customer.models import Category, Product, Shop


class Command(BaseCommand):
    help = 'Seed development data for shops, categories, and products.'

    def handle(self, *args, **options):
        Category.objects.all().delete()
        Product.objects.all().delete()
        Shop.objects.all().delete()

        shops = [
            {'name': 'Green Valley Mart', 'address': '12, Lekki Phase 1, Lagos', 'phone': '08012345678', 'latitude': 6.4654, 'longitude': 3.4418, 'rating': 4.8},
            {'name': 'Fresh Basket Hub', 'address': '45, Yaba, Lagos', 'phone': '08087654321', 'latitude': 6.5092, 'longitude': 3.3792, 'rating': 4.6},
            {'name': 'Daily Needs Corner', 'address': '88, Ikeja, Lagos', 'phone': '08123456789', 'latitude': 6.6018, 'longitude': 3.3515, 'rating': 4.7},
        ]
        created_shops = []
        for shop_data in shops:
            shop = Shop.objects.create(**shop_data)
            created_shops.append(shop)

        categories = [
            {'name': 'Grocery', 'slug': 'grocery'},
            {'name': 'Dairy', 'slug': 'dairy'},
            {'name': 'Snacks', 'slug': 'snacks'},
            {'name': 'Beverages', 'slug': 'beverages'},
            {'name': 'Personal Care', 'slug': 'personal-care'},
        ]
        created_categories = []
        for category_data in categories:
            category = Category.objects.create(**category_data)
            created_categories.append(category)

        products = [
            {'shop': created_shops[0], 'category': created_categories[0], 'name': 'Fresh Apples', 'slug': 'fresh-apples', 'description': 'Crisp apples sourced from local farms.', 'price': 120.00, 'mrp': 150.00, 'stock_quantity': 20},
            {'shop': created_shops[0], 'category': created_categories[0], 'name': 'Rice Pack', 'slug': 'rice-pack', 'description': 'Premium long grain rice.', 'price': 950.00, 'mrp': 1100.00, 'stock_quantity': 15},
            {'shop': created_shops[0], 'category': created_categories[2], 'name': 'Crunchy Chips', 'slug': 'crunchy-chips', 'description': 'Golden chips with a savory crunch.', 'price': 180.00, 'mrp': 220.00, 'stock_quantity': 25},
            {'shop': created_shops[1], 'category': created_categories[1], 'name': 'Organic Milk', 'slug': 'organic-milk', 'description': 'Fresh dairy milk with rich taste.', 'price': 180.00, 'mrp': 220.00, 'stock_quantity': 30},
            {'shop': created_shops[1], 'category': created_categories[1], 'name': 'Yogurt Cup', 'slug': 'yogurt-cup', 'description': 'Creamy yogurt for quick breakfasts.', 'price': 90.00, 'mrp': 110.00, 'stock_quantity': 18},
            {'shop': created_shops[1], 'category': created_categories[3], 'name': 'Orange Juice', 'slug': 'orange-juice', 'description': 'Fresh orange juice with vitamin C.', 'price': 250.00, 'mrp': 300.00, 'stock_quantity': 12},
            {'shop': created_shops[1], 'category': created_categories[4], 'name': 'Body Wash', 'slug': 'body-wash', 'description': 'Moisturizing body wash for daily care.', 'price': 320.00, 'mrp': 380.00, 'stock_quantity': 10},
            {'shop': created_shops[2], 'category': created_categories[0], 'name': 'Tomato Paste', 'slug': 'tomato-paste', 'description': 'Rich tomato paste for cooking.', 'price': 140.00, 'mrp': 170.00, 'stock_quantity': 14},
            {'shop': created_shops[2], 'category': created_categories[2], 'name': 'Popcorn Mix', 'slug': 'popcorn-mix', 'description': 'Sweet and salty popcorn assortment.', 'price': 160.00, 'mrp': 200.00, 'stock_quantity': 22},
            {'shop': created_shops[2], 'category': created_categories[3], 'name': 'Sparkling Water', 'slug': 'sparkling-water', 'description': 'Refreshing sparkling water in bottles.', 'price': 100.00, 'mrp': 130.00, 'stock_quantity': 26},
            {'shop': created_shops[2], 'category': created_categories[4], 'name': 'Shampoo', 'slug': 'shampoo', 'description': 'Gentle shampoo for soft, healthy hair.', 'price': 280.00, 'mrp': 340.00, 'stock_quantity': 16},
            {'shop': created_shops[0], 'category': created_categories[4], 'name': 'Toothpaste', 'slug': 'toothpaste', 'description': 'Minty toothpaste with cavity protection.', 'price': 160.00, 'mrp': 190.00, 'stock_quantity': 20},
            {'shop': created_shops[0], 'category': created_categories[3], 'name': 'Iced Tea', 'slug': 'iced-tea', 'description': 'Chilled tea with a light citrus finish.', 'price': 220.00, 'mrp': 260.00, 'stock_quantity': 13},
            {'shop': created_shops[1], 'category': created_categories[2], 'name': 'Trail Mix', 'slug': 'trail-mix', 'description': 'Nutty snack mix for on-the-go energy.', 'price': 240.00, 'mrp': 280.00, 'stock_quantity': 17},
            {'shop': created_shops[2], 'category': created_categories[1], 'name': 'Cheese Slice', 'slug': 'cheese-slice', 'description': 'Creamy cheese slices for sandwiches.', 'price': 210.00, 'mrp': 250.00, 'stock_quantity': 9},
        ]

        for product_data in products:
            Product.objects.create(**product_data)

        self.stdout.write(self.style.SUCCESS('Catalog data seeded successfully.'))
