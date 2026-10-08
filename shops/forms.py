from django import forms
from PIL import Image

from .models import Category, Product, Store

# Product images: at most 5 MiB, and the decoded bytes must be PNG, JPEG, or WebP.
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MiB
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}


class StoreForm(forms.ModelForm):
    """Seller-facing store form. `owner` and `balance` are never editable."""

    class Meta:
        model = Store
        fields = ("name", "description")

    def save(self, commit=True):
        store = super().save(commit=False)
        if not commit:
            return store
        if store.pk is None:
            store.save()
        else:
            # Never write a possibly stale in-memory balance; update only the
            # fields this form is allowed to change.
            store.save(update_fields=["name", "description"])
        return store


class ProductForm(forms.ModelForm):
    """Seller-facing product form. The store relationship is set by the view."""

    class Meta:
        model = Product
        fields = ("name", "description", "price", "stock", "category", "image")

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image
        if image.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("حجم تصویر نباید بیشتر از ۵ مگابایت باشد.")
        try:
            # Decode the actual contents instead of trusting the file name or
            # the browser-provided content type.
            with Image.open(image) as probe:
                probe.verify()
            image.seek(0)
            with Image.open(image) as probe:
                detected_format = probe.format
        except Exception as error:
            raise forms.ValidationError("فایل ارسالی یک تصویر معتبر نیست.") from error
        if detected_format not in ALLOWED_IMAGE_FORMATS:
            raise forms.ValidationError("فقط تصاویر PNG، JPEG و WebP پذیرفته می‌شوند.")
        image.seek(0)
        return image


class ProductSearchForm(forms.Form):
    q = forms.CharField(label="جست‌وجو", max_length=100, required=False)
    category = forms.ModelChoiceField(
        label="دسته‌بندی",
        queryset=Category.objects.all(),
        required=False,
        empty_label="همهٔ دسته‌بندی‌ها",
    )
