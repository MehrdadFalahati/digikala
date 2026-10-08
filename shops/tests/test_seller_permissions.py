from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from shops.models import Product, Store

User = get_user_model()


class SellerPermissionTests(TestCase):
    def setUp(self):
        self.seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        self.seller = SellerProfile.objects.create(user=self.seller_user)
        self.other_user = User.objects.create_user(username="other", password="StrongPass!234")
        self.other_seller = SellerProfile.objects.create(user=self.other_user)
        self.store = Store.objects.create(name="فروشگاه من", owner=self.seller)
        self.foreign_store = Store.objects.create(name="فروشگاه دیگری", owner=self.other_seller)
        self.product = Product.objects.create(
            name="محصول من", price=Decimal("1000.00"), stock=2, store=self.store
        )
        self.foreign_product = Product.objects.create(
            name="محصول دیگری", price=Decimal("2000.00"), stock=2, store=self.foreign_store
        )

    def test_foreign_store_and_product_edits_denied(self):
        self.client.force_login(self.seller_user)

        original_name = self.foreign_store.name
        response = self.client.get(reverse("shops:store_update", args=[self.foreign_store.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse("shops:store_update", args=[self.foreign_store.pk]),
            {"name": "تغییر یافته", "description": ""},
        )
        self.assertEqual(response.status_code, 404)
        self.foreign_store.refresh_from_db()
        self.assertEqual(self.foreign_store.name, original_name)

        response = self.client.get(reverse("shops:product_update", args=[self.foreign_product.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse("shops:product_update", args=[self.foreign_product.pk]),
            {"name": "دزدیده شده", "description": "", "price": "5.00", "stock": 1},
        )
        self.assertEqual(response.status_code, 404)
        self.foreign_product.refresh_from_db()
        self.assertEqual(self.foreign_product.name, "محصول دیگری")

        # Forged store id when creating a product for someone else's store.
        response = self.client.get(reverse("shops:product_create", args=[self.foreign_store.pk]))
        self.assertEqual(response.status_code, 404)

        # Missing objects.
        self.assertEqual(
            self.client.get(reverse("shops:store_update", args=[99999])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("shops:product_update", args=[99999])).status_code, 404
        )

        # Wrong role.
        customer_user = User.objects.create_user(username="customer", password="StrongPass!234")
        CustomerProfile.objects.create(user=customer_user, phone="09120000000")
        self.client.force_login(customer_user)
        self.assertEqual(self.client.get(reverse("shops:seller_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("shops:store_create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("shops:product_create", args=[self.store.pk])).status_code,
            403,
        )

    def test_owner_and_balance_fields_ignored(self):
        self.client.force_login(self.seller_user)

        response = self.client.post(
            reverse("shops:store_create"),
            {
                "name": "فروشگاه تازه",
                "description": "",
                "owner": str(self.other_seller.pk),
                "balance": "5000000.00",
            },
        )
        self.assertEqual(response.status_code, 302)

        store = Store.objects.get(name="فروشگاه تازه")
        self.assertEqual(store.owner_id, self.seller.pk)
        self.assertEqual(store.balance, Decimal("0.00"))

        response = self.client.post(
            reverse("shops:store_update", args=[self.store.pk]),
            {
                "name": "نام تازه",
                "description": "توضیح",
                "owner": str(self.other_seller.pk),
                "balance": "123456.00",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.store.refresh_from_db()
        self.assertEqual(self.store.name, "نام تازه")
        self.assertEqual(self.store.owner_id, self.seller.pk)
        self.assertEqual(self.store.balance, Decimal("0.00"))

    def test_invalid_product_values(self):
        self.client.force_login(self.seller_user)
        base = {"name": "محصول", "description": "", "price": "1000.00", "stock": 1}

        for overrides in (
            {"price": "0"},
            {"price": "-5.00"},
            {"price": "100000000000000.00"},
            {"stock": -1},
        ):
            payload = {**base, **overrides}
            response = self.client.post(
                reverse("shops:product_create", args=[self.store.pk]), payload
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)

        self.assertEqual(Product.objects.filter(store=self.store).count(), 1)
