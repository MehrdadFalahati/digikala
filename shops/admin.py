from django import forms
from django.contrib import admin
from django.core import signing

from .models import Category, Product, Store


class StoreAdminForm(forms.ModelForm):
    """Admin form that never rewrites a possibly stale balance."""

    class Meta:
        model = Store
        fields = ("name", "description", "owner")

    def save(self, commit=True):
        store = super().save(commit=False)
        if not commit:
            return store
        if store.pk is None:
            store.save()
        else:
            store.save(update_fields=["name", "description", "owner"])
        return store


class ProductAdminForm(forms.ModelForm):
    """Reject inventory edits based on a page opened before stock changed."""

    stock_version = forms.CharField(widget=forms.HiddenInput, required=False)
    stock_version_salt = "shops.admin.product.stock"

    class Meta:
        model = Product
        fields = ("name", "description", "price", "stock", "category", "image", "store")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is not None:
            self.fields["stock_version"].required = True
            self.initial["stock_version"] = signing.dumps(
                {"product_id": self.instance.pk, "stock": self.instance.stock},
                salt=self.stock_version_salt,
            )

    def clean_stock_version(self):
        if self.instance.pk is None:
            return None
        try:
            baseline = signing.loads(
                self.cleaned_data["stock_version"], salt=self.stock_version_salt
            )
        except signing.BadSignature:
            raise forms.ValidationError("فرم ویرایش نامعتبر است؛ صفحه را دوباره باز کنید.")
        if not isinstance(baseline, dict) or baseline.get("product_id") != self.instance.pk:
            raise forms.ValidationError("فرم ویرایش نامعتبر است؛ صفحه را دوباره باز کنید.")
        return baseline

    def clean(self):
        cleaned_data = super().clean()
        baseline = cleaned_data.get("stock_version")
        if baseline is not None and baseline.get("stock") != self.instance.stock:
            self.add_error(
                "stock",
                "موجودی کالا تغییر کرده است؛ صفحه را دوباره باز کنید و ویرایش را تکرار کنید.",
            )
        return cleaned_data


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    form = StoreAdminForm
    list_display = ("name", "owner", "balance")
    search_fields = ("name",)
    readonly_fields = ("balance",)

    def save_model(self, request, obj, form, change):
        if change:
            # Admin saves the instance separately from form.save(commit=False).
            # Keep checkout credits out of this nonfinancial update.
            obj.save(update_fields=["name", "description", "owner"])
        else:
            super().save_model(request, obj, form, change)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("name", "store", "price", "stock", "category", "created_at")
    list_filter = ("store", "category")
    search_fields = ("name",)

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is not None and request.method == "POST":
            # Django wraps change/delete POSTs in a transaction. Re-read under
            # a row lock before constructing the form, and hold it until save.
            return (
                self.get_queryset(request)
                .select_for_update(of=("self",))
                .filter(pk=obj.pk)
                .first()
            )
        return obj

    def save_model(self, request, obj, form, change):
        if change:
            # Metadata edits must not rewrite unchanged stock or prices.
            obj.save(
                update_fields=[field for field in form.changed_data if field != "stock_version"]
            )
        else:
            super().save_model(request, obj, form, change)
