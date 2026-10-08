from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import CustomerProfile
from cart.models import CartItem
from orders.models import Order
from orders.services import checkout
from shops.management.commands.seed_demo import DEMO_PASSWORD
from shops.models import Category, Product, Store

User = get_user_model()


class SeedDemoTests(TestCase):
    def test_seed_demo_is_repeatable(self):
        call_command("seed_demo", verbosity=0)
        counts = {
            "users": User.objects.count(),
            "stores": Store.objects.count(),
            "categories": Category.objects.count(),
            "products": Product.objects.count(),
        }

        call_command("seed_demo", verbosity=0)

        self.assertEqual(User.objects.count(), counts["users"])
        self.assertEqual(Store.objects.count(), counts["stores"])
        self.assertEqual(Category.objects.count(), counts["categories"])
        self.assertEqual(Product.objects.count(), counts["products"])

        seller_user = User.objects.get(username="seller_digital")
        self.assertTrue(seller_user.check_password(DEMO_PASSWORD))
        seller = seller_user.seller_profile
        self.assertTrue(seller.stores.exists())
        self.assertTrue(seller.stores.first().products.exists())

        customer_user = User.objects.get(username="customer_demo")
        self.assertTrue(customer_user.check_password(DEMO_PASSWORD))
        customer = customer_user.customer_profile
        self.assertEqual(customer.phone, "09120000001")
        self.assertGreater(customer.balance, Decimal("0.00"))

        self.assertTrue(Product.objects.filter(category__isnull=False).exists())
        self.assertGreaterEqual(Store.objects.count(), 2)

    def test_seed_demo_preserves_existing_data(self):
        call_command("seed_demo", verbosity=0)

        # Build purchase history for the seeded customer.
        customer_user = User.objects.get(username="customer_demo")
        customer = customer_user.customer_profile
        product = Product.objects.get(name="تی‌شرت نخی")
        CartItem.objects.create(customer=customer, product=product, quantity=1)
        order = checkout(customer_id=customer.pk, checkout_key=customer.checkout_key)
        customer.refresh_from_db()
        balance_after_purchase = customer.balance

        # Manual changes that reseeding must never overwrite.
        customer_user.set_password("MyOwnPass!234")
        customer_user.save()
        store = Store.objects.get(name="دیجی‌استور")
        store.description = "توضیح دستی"
        store.balance = Decimal("999.00")
        store.save(update_fields=["description", "balance"])
        product.price = Decimal("1.00")
        product.save(update_fields=["price"])
        category_count = Category.objects.count()
        user_count = User.objects.count()

        call_command("seed_demo", verbosity=0)

        customer_user.refresh_from_db()
        self.assertTrue(customer_user.check_password("MyOwnPass!234"))
        customer.refresh_from_db()
        self.assertEqual(customer.balance, balance_after_purchase)

        store.refresh_from_db()
        self.assertEqual(store.balance, Decimal("999.00"))
        self.assertEqual(store.description, "توضیح دستی")

        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("1.00"))

        self.assertEqual(Order.objects.filter(customer=customer).count(), 1)
        self.assertEqual(Order.objects.get(customer=customer).items.count(), 1)
        self.assertEqual(Category.objects.count(), category_count)
        self.assertEqual(User.objects.count(), user_count)
