from django import forms

from .models import Product, Store


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
        fields = ("name", "description", "price", "stock")
