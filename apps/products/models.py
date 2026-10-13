from decimal import Decimal

from django.db import models


class Product(models.Model):
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="products",
    )

    name = models.CharField(
        max_length=160
    )

    sku = models.CharField(
        max_length=80,
        blank=True,
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    stock_quantity = models.PositiveIntegerField(
        default=0,
    )

    low_stock_threshold = models.PositiveIntegerField(
        default=5,
    )

    description = models.TextField(
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
        ordering = ["name"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "business",
                    "sku",
                ],
                condition=~models.Q(
                    sku=""
                ),
                name="unique_product_sku_per_business",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "name",
                ]
            ),
            models.Index(
                fields=[
                    "business",
                    "sku",
                ]
            ),
            models.Index(
                fields=[
                    "business",
                    "is_active",
                ]
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return (
            self.stock_quantity
            <= self.low_stock_threshold
        )