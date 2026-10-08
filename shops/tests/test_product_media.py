import io
import os
import shutil
import tempfile

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import SellerProfile
from shops.forms import ProductForm
from shops.models import Category, Product, Store

User = get_user_model()


def make_image_bytes(fmt="PNG", image=None):
    if image is None:
        image = Image.new("RGB", (20, 20), "red")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    buffer.seek(0)
    return buffer.read()


def make_oversized_png():
    noise = os.urandom(1500 * 1500 * 3)
    image = Image.frombytes("RGB", (1500, 1500), noise)
    return make_image_bytes("PNG", image=image)


class ProductMediaTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix="dijikala-media-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.settings_override.enable()

        self.seller_user = User.objects.create_user(
            username="seller", password="StrongPass!234"
        )
        self.seller = SellerProfile.objects.create(user=self.seller_user)
        self.store = Store.objects.create(name="فروشگاه", owner=self.seller)
        self.category = Category.objects.create(name="دیجیتال")

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def base_payload(self, **overrides):
        payload = {
            "name": "محصول تصویری",
            "description": "",
            "price": "1000.00",
            "stock": 1,
            "category": self.category.pk,
        }
        payload.update(overrides)
        return payload

    def test_valid_image_upload(self):
        self.client.force_login(self.seller_user)
        upload = SimpleUploadedFile(
            "photo.png", make_image_bytes("PNG"), content_type="image/png"
        )

        response = self.client.post(
            reverse("shops:product_create", args=[self.store.pk]),
            {**self.base_payload(), "image": upload},
        )

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="محصول تصویری")
        self.assertTrue(product.image)
        self.assertTrue(os.path.exists(product.image.path))
        self.assertEqual(product.category, self.category)

    def test_invalid_image_upload(self):
        oversized = SimpleUploadedFile(
            "large.png", make_oversized_png(), content_type="image/png"
        )
        non_image = SimpleUploadedFile(
            "fake.png", b"this is not an image", content_type="image/png"
        )
        gif = SimpleUploadedFile(
            "animation.gif", make_image_bytes("GIF"), content_type="image/gif"
        )

        for label, upload in (
            ("oversized", oversized),
            ("renamed non-image", non_image),
            ("unsupported format", gif),
        ):
            form = ProductForm(
                data=self.base_payload(name=f"محصول {label}"),
                files={"image": upload},
            )
            self.assertFalse(form.is_valid(), label)

        self.client.force_login(self.seller_user)
        view_upload = SimpleUploadedFile(
            "fake.png", b"this is not an image", content_type="image/png"
        )
        response = self.client.post(
            reverse("shops:product_create", args=[self.store.pk]),
            {**self.base_payload(name="محصول نامعتبر"), "image": view_upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name="محصول نامعتبر").exists())
