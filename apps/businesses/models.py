from decimal import Decimal

from django.conf import settings
from django.db import models


class Business(models.Model):
    name = models.CharField(
        max_length=150,
    )

    slug = models.SlugField(
        max_length=160,
        unique=True,
    )

    logo = models.ImageField(
        upload_to="business_logos/%Y/%m/",
        blank=True,
        null=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    currency = models.CharField(
        max_length=10,
        default="BDT",
    )

    default_low_stock_threshold = models.PositiveIntegerField(
        default=5,
    )

    order_prefix = models.CharField(
        max_length=20,
        default="ORD",
    )

    default_delivery_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    invoice_note = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "name",
        ]

    def __str__(self):
        return self.name


class BusinessMember(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_STAFF = "staff"

    ROLE_CHOICES = [
        (
            ROLE_OWNER,
            "Owner",
        ),
        (
            ROLE_ADMIN,
            "Admin",
        ),
        (
            ROLE_STAFF,
            "Staff",
        ),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STAFF,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "role",
            "id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "business",
                    "user",
                ],
                name="unique_business_member",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.business} - "
            f"{self.get_role_display()}"
        )