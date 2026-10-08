from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/checkout/", views.checkout, name="checkout"),
    path("orders/", views.history, name="history"),
    path("orders/<int:order_id>/", views.detail, name="detail"),
    path("orders/<int:order_id>/thank-you/", views.thank_you, name="thank_you"),
]
