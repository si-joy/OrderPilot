from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "sku",
        "selling_price",
        "cost_price",
        "stock_quantity",
        "low_stock_threshold",
        "is_active",
        "created_at",
    )

    list_filter = (
        "business",
        "is_active",
    )

    search_fields = (
        "name",
        "sku",
        "business__name",
    )

    ordering = (
        "business",
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )