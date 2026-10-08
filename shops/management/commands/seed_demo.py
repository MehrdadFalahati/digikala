from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import CustomerProfile, SellerProfile
from shops.models import Category, Product, Store

User = get_user_model()

DEMO_PASSWORD = "DemoPass!234"

CATEGORIES = ["دیجیتال", "خانه و آشپزخانه", "مد و پوشاک"]

SELLERS = [
    {
        "username": "seller_digital",
        "first_name": "سارا",
        "last_name": "محمدی",
        "stores": [
            {
                "name": "دیجی‌استور",
                "description": "فروشگاه نمونهٔ محصولات دیجیتال",
                "products": [
                    {
                        "name": "گوشی هوشمند",
                        "description": "گوشی نمونه با گارانتی آزمایشی",
                        "price": "15000000.00",
                        "stock": 8,
                        "category": "دیجیتال",
                    },
                    {
                        "name": "هدفون بی‌سیم",
                        "description": "هدفون نمونهٔ بلوتوثی",
                        "price": "2500000.00",
                        "stock": 20,
                        "category": "دیجیتال",
                    },
                ],
            },
        ],
    },
    {
        "username": "seller_home",
        "first_name": "رضا",
        "last_name": "کریمی",
        "stores": [
            {
                "name": "خانهٔ سبز",
                "description": "فروشگاه نمونهٔ لوازم خانه",
                "products": [
                    {
                        "name": "کتری برقی",
                        "description": "کتری نمونهٔ ۱.۷ لیتری",
                        "price": "1200000.00",
                        "stock": 15,
                        "category": "خانه و آشپزخانه",
                    },
                    {
                        "name": "تی‌شرت نخی",
                        "description": "تی‌شرت نمونهٔ نخی",
                        "price": "450000.00",
                        "stock": 30,
                        "category": "مد و پوشاک",
                    },
                ],
            },
        ],
    },
]

CUSTOMERS = [
    {
        "username": "customer_demo",
        "first_name": "علی",
        "last_name": "رضایی",
        "phone": "09120000001",
        "balance": "5000000.00",
    },
    {
        "username": "customer_guest",
        "first_name": "مینا",
        "last_name": "حسینی",
        "phone": "09120000002",
        "balance": "100000.00",
    },
]


class Command(BaseCommand):
    help = "Create repeatable demo data: users, stores, categories, and products."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for name in CATEGORIES:
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category

        for seller_spec in SELLERS:
            user, created = User.objects.get_or_create(username=seller_spec["username"])
            if created:
                user.first_name = seller_spec["first_name"]
                user.last_name = seller_spec["last_name"]
                user.set_password(DEMO_PASSWORD)
                user.save()
            seller, _ = SellerProfile.objects.get_or_create(user=user)

            for store_spec in seller_spec["stores"]:
                store, store_created = Store.objects.get_or_create(
                    owner=seller, name=store_spec["name"]
                )
                if store_created:
                    store.description = store_spec["description"]
                    store.save(update_fields=["description"])

                for product_spec in store_spec["products"]:
                    Product.objects.get_or_create(
                        store=store,
                        name=product_spec["name"],
                        defaults={
                            "description": product_spec.get("description", ""),
                            "price": Decimal(product_spec["price"]),
                            "stock": product_spec["stock"],
                            "category": categories[product_spec["category"]],
                        },
                    )

        for customer_spec in CUSTOMERS:
            user, created = User.objects.get_or_create(username=customer_spec["username"])
            if created:
                user.first_name = customer_spec["first_name"]
                user.last_name = customer_spec["last_name"]
                user.set_password(DEMO_PASSWORD)
                user.save()
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "phone": customer_spec["phone"],
                    "balance": Decimal(customer_spec["balance"]),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "دادهٔ نمونه آماده است. نام کاربری نمونه‌ها با رمز "
                f"{DEMO_PASSWORD} قابل استفاده‌اند و اجرای دوباره، داده‌ها را تکراری نمی‌کند."
            )
        )
