from django.urls import path

from . import views


app_name = "products"


urlpatterns = [
    path("", views.product_list, name="list"),

    path(
        "new/",
        views.product_create,
        name="create",
    ),

    path(
        "<int:pk>/",
        views.product_detail,
        name="detail",
    ),

    path(
        "<int:pk>/edit/",
        views.product_update,
        name="update",
    ),

    path(
        "<int:pk>/archive/",
        views.product_archive,
        name="archive",
    ),

    path(
        "<int:pk>/restore/",
        views.product_restore,
        name="restore",
    ),
]