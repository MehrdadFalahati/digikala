from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.detail, name="detail"),
    path("add/", views.add, name="add"),
    path("items/<int:item_id>/", views.update, name="update"),
    path("items/<int:item_id>/remove/", views.remove, name="remove"),
]
