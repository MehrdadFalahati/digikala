from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import seller_for_user

from .forms import ProductForm, StoreForm
from .models import Product, Store


def home(request):
    """Landing page: all products, newest first."""
    products = Product.objects.select_related("store", "category")
    return render(request, "home.html", {"products": products})


def stores(request):
    """Public list of all stores."""
    store_list = Store.objects.select_related("owner__user").order_by("name")
    return render(request, "stores.html", {"stores": store_list})


def store_detail(request, store_id):
    """Public store page with only this store's products."""
    store = get_object_or_404(Store, pk=store_id)
    products = store.products.select_related("category")
    seller = getattr(request.user, "seller_profile", None)
    is_owner = seller is not None and store.owner_id == seller.pk
    context = {"store": store, "products": products, "is_owner": is_owner}
    return render(request, "store_detail.html", context)


@login_required
def seller_dashboard(request):
    seller = seller_for_user(request.user)
    store_list = seller.stores.order_by("name")
    return render(request, "seller/dashboard.html", {"seller": seller, "stores": store_list})


@login_required
def store_create(request):
    seller = seller_for_user(request.user)
    if request.method == "POST":
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = seller
            store.balance = Decimal("0.00")
            store.save()
            messages.success(request, "فروشگاه ساخته شد.")
            return redirect("shops:seller_dashboard")
    else:
        form = StoreForm()
    return render(request, "seller/store_form.html", {"form": form})


@login_required
def store_update(request, store_id):
    seller = seller_for_user(request.user)
    store = get_object_or_404(Store, pk=store_id, owner=seller)
    if request.method == "POST":
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "فروشگاه به‌روزرسانی شد.")
            return redirect("shops:seller_dashboard")
    else:
        form = StoreForm(instance=store)
    return render(request, "seller/store_form.html", {"form": form, "store": store})


@login_required
def product_create(request, store_id):
    seller = seller_for_user(request.user)
    store = get_object_or_404(Store, pk=store_id, owner=seller)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.save()
            messages.success(request, "محصول افزوده شد.")
            return redirect("shops:store_detail", store_id=store.pk)
    else:
        form = ProductForm()
    return render(request, "seller/product_form.html", {"form": form, "store": store})


@login_required
def product_update(request, product_id):
    seller = seller_for_user(request.user)
    with transaction.atomic():
        # Lock the row while stock and price edits are processed.
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=product_id,
            store__owner=seller,
        )
        if request.method == "POST":
            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                form.save()
                messages.success(request, "محصول به‌روزرسانی شد.")
                return redirect("shops:store_detail", store_id=product.store_id)
        else:
            form = ProductForm(instance=product)
        context = {"form": form, "store": product.store, "product": product}
    return render(request, "seller/product_form.html", context)
