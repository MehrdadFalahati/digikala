from django.urls import path

from . import views

app_name = "shops"

urlpatterns = [
    path("", views.home, name="home"),
    path("stores/", views.stores, name="stores"),
    path("stores/<int:store_id>/", views.store_detail, name="store_detail"),
    path("seller/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/stores/new/", views.store_create, name="store_create"),
    path("seller/stores/<int:store_id>/edit/", views.store_update, name="store_update"),
    path(
        "seller/stores/<int:store_id>/products/new/",
        views.product_create,
        name="product_create",
    ),
    path("seller/products/<int:product_id>/edit/", views.product_update, name="product_update"),
]
