from django import forms
from django.contrib import admin

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


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    form = StoreAdminForm
    list_display = ("name", "owner", "balance")
    search_fields = ("name",)
    readonly_fields = ("balance",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "store", "price", "stock", "category", "created_at")
    list_filter = ("store", "category")
    search_fields = ("name",)
