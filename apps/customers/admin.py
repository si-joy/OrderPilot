from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "email",
        "city",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "city",
        "district",
    )

    search_fields = (
        "full_name",
        "phone",
        "email",
        "city",
        "district",
    )

    ordering = ("-created_at",)