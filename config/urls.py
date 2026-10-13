from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "",
        include("apps.core.urls"),
    ),

    path(
        "customers/",
        include("apps.customers.urls"),
    ),

    path(
        "products/",
        include("apps.products.urls"),
    ),

    path(
        "orders/",
        include("apps.orders.urls"),
    ),

    path(
        "reports/",
        include("apps.reports.urls"),
    ),

    path(
        "business/",
        include("apps.businesses.urls"),
    ),
    path(
        "notifications/",
        include(
            "apps.notifications.urls"),
),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )