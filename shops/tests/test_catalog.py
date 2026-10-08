from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import SellerProfile
from shops.models import Category, Product, Store

User = get_user_model()


class CatalogTests(TestCase):
    def setUp(self):
        self.seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        self.seller = SellerProfile.objects.create(user=self.seller_user)

    def test_newest_products_first(self):
        store = Store.objects.create(name="فروشگاه", owner=self.seller)
        older = Product.objects.create(
            name="محصول قدیمی", price=Decimal("1000.00"), stock=1, store=store
        )
        newer = Product.objects.create(
            name="محصول جدید", price=Decimal("2000.00"), stock=1, store=store
        )

        response = self.client.get(reverse("shops:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["products"]), [newer, older])

    def test_store_product_scope(self):
        store = Store.objects.create(name="فروشگاه الف", owner=self.seller)
        other_store = Store.objects.create(name="فروشگاه ب", owner=self.seller)
        first = Product.objects.create(
            name="محصول یک", price=Decimal("1000.00"), stock=1, store=store
        )
        second = Product.objects.create(
            name="محصول دو", price=Decimal("2000.00"), stock=1, store=store
        )
        foreign = Product.objects.create(
            name="محصول بیگانه", price=Decimal("3000.00"), stock=1, store=other_store
        )

        response = self.client.get(reverse("shops:store_detail", args=[store.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["store"], store)
        self.assertEqual(list(response.context["products"]), [second, first])
        self.assertNotIn(foreign, response.context["products"])
        self.assertNotIn(
            reverse("shops:product_create", args=[store.pk]), response.content.decode()
        )

        self.client.force_login(self.seller_user)
        owner_response = self.client.get(reverse("shops:store_detail", args=[store.pk]))
        self.assertIn(
            reverse("shops:product_create", args=[store.pk]), owner_response.content.decode()
        )

    def test_seller_can_own_multiple_stores(self):
        self.client.force_login(self.seller_user)

        for name in ("فروشگاه یک", "فروشگاه دو"):
            response = self.client.post(
                reverse("shops:store_create"), {"name": name, "description": ""}
            )
            self.assertEqual(response.status_code, 302)

        stores = Store.objects.filter(owner=self.seller).order_by("name")
        self.assertEqual(stores.count(), 2)
        for store in stores:
            self.assertEqual(store.owner_id, self.seller.pk)
            self.assertEqual(store.balance, Decimal("0.00"))

    def test_product_search(self):
        store = Store.objects.create(name="فروشگاه", owner=self.seller)
        category = Category.objects.create(name="دیجیتال")
        matching = Product.objects.create(
            name="گوشی سامسونگ",
            price=Decimal("1000.00"),
            stock=1,
            store=store,
            category=category,
        )
        Product.objects.create(
            name="لپ‌تاپ ایسوس", price=Decimal("2000.00"), stock=1, store=store
        )

        response = self.client.get(reverse("shops:home"), {"q": "سامسونگ"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["products"]), [matching])

    def test_category_and_combined_filters(self):
        store = Store.objects.create(name="فروشگاه", owner=self.seller)
        digital = Category.objects.create(name="دیجیتال")
        home_category = Category.objects.create(name="خانه")
        phone = Product.objects.create(
            name="گوشی سامسونگ",
            price=Decimal("1000.00"),
            stock=1,
            store=store,
            category=digital,
        )
        laptop = Product.objects.create(
            name="لپ‌تاپ سامسونگ",
            price=Decimal("2000.00"),
            stock=1,
            store=store,
            category=digital,
        )
        Product.objects.create(
            name="کتری برقی",
            price=Decimal("3000.00"),
            stock=1,
            store=store,
            category=home_category,
        )

        by_category = self.client.get(reverse("shops:home"), {"category": digital.pk})
        self.assertEqual(by_category.status_code, 200)
        self.assertEqual(list(by_category.context["products"]), [laptop, phone])

        combined = self.client.get(
            reverse("shops:home"), {"q": "گوشی", "category": digital.pk}
        )
        self.assertEqual(combined.status_code, 200)
        self.assertEqual(list(combined.context["products"]), [phone])

    def test_invalid_search_parameters(self):
        response = self.client.get(reverse("shops:home"), {"category": "not-a-number"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["search_form"].errors)

        response = self.client.get(reverse("shops:home"), {"q": "x" * 101})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["search_form"].errors)
