from django.contrib import admin

from .models import (
    Order,
    OrderItem,
    OrderStatusHistory,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

    readonly_fields = (
        "product_name",
        "sku",
        "unit_price",
        "unit_cost",
    )


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0

    readonly_fields = (
        "from_status",
        "to_status",
        "changed_by",
        "note",
        "created_at",
    )

    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "business",
        "customer",
        "status",
        "payment_method",
        "payment_status",
        "total_amount",
        "paid_amount",
        "created_at",
    )

    list_filter = (
        "business",
        "status",
        "payment_method",
        "payment_status",
    )

    search_fields = (
        "order_number",
        "customer__full_name",
        "customer__phone",
        "tracking_number",
    )

    readonly_fields = (
        "order_number",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    inlines = [
        OrderItemInline,
        OrderStatusHistoryInline,
    ]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product_name",
        "sku",
        "quantity",
        "unit_price",
    )

    search_fields = (
        "order__order_number",
        "product_name",
        "sku",
    )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "from_status",
        "to_status",
        "changed_by",
        "created_at",
    )

    list_filter = (
        "from_status",
        "to_status",
    )

    search_fields = (
        "order__order_number",
        "note",
    )