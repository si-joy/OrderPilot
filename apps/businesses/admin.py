from django.contrib import admin

from .models import Business, BusinessMember


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "phone",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "phone",
        "email",
    )

    list_filter = (
        "is_active",
    )


@admin.register(BusinessMember)
class BusinessMemberAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "business",
        "role",
        "is_active",
        "created_at",
    )

    list_filter = (
        "role",
        "is_active",
        "business",
    )

    search_fields = (
        "user__username",
        "user__email",
        "business__name",
    )