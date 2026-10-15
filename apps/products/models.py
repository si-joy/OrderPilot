from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


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


# =========================================================
# STOCK ADJUSTMENT / MOVEMENT HISTORY
# =========================================================

class StockAdjustment(models.Model):

    TYPE_OPENING = "opening"
    TYPE_RESTOCK = "restock"
    TYPE_RETURN = "return"
    TYPE_CORRECTION_ADD = "correction_add"
    TYPE_CORRECTION_REMOVE = "correction_remove"
    TYPE_DAMAGED = "damaged"
    TYPE_LOST = "lost"
    TYPE_ORDER_DEDUCT = "order_deduct"
    TYPE_ORDER_RESTORE = "order_restore"

    TYPE_CHOICES = [
        (
            TYPE_OPENING,
            "Opening Stock",
        ),
        (
            TYPE_RESTOCK,
            "Restock",
        ),
        (
            TYPE_RETURN,
            "Customer Return",
        ),
        (
            TYPE_CORRECTION_ADD,
            "Stock Correction (+)",
        ),
        (
            TYPE_CORRECTION_REMOVE,
            "Stock Correction (-)",
        ),
        (
            TYPE_DAMAGED,
            "Damaged Stock",
        ),
        (
            TYPE_LOST,
            "Lost Stock",
        ),
        (
            TYPE_ORDER_DEDUCT,
            "Order Stock Deduction",
        ),
        (
            TYPE_ORDER_RESTORE,
            "Order Stock Restore",
        ),
    ]

    INCREASE_TYPES = {
        TYPE_OPENING,
        TYPE_RESTOCK,
        TYPE_RETURN,
        TYPE_CORRECTION_ADD,
        TYPE_ORDER_RESTORE,
    }

    DECREASE_TYPES = {
        TYPE_CORRECTION_REMOVE,
        TYPE_DAMAGED,
        TYPE_LOST,
        TYPE_ORDER_DEDUCT,
    }

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="stock_adjustments",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_adjustments",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )

    adjustment_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
    )

    quantity = models.PositiveIntegerField()

    before_quantity = models.PositiveIntegerField()

    after_quantity = models.PositiveIntegerField()

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "created_at",
                ]
            ),
            models.Index(
                fields=[
                    "product",
                    "created_at",
                ]
            ),
            models.Index(
                fields=[
                    "business",
                    "adjustment_type",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=0
                ),
                name="stock_adjustment_quantity_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.get_adjustment_type_display()} "
            f"({self.quantity})"
        )

    @property
    def is_increase(self):
        return (
            self.adjustment_type
            in self.INCREASE_TYPES
        )

    @property
    def is_decrease(self):
        return (
            self.adjustment_type
            in self.DECREASE_TYPES
        )

    @property
    def signed_quantity(self):
        if self.is_increase:
            return self.quantity

        if self.is_decrease:
            return -self.quantity

        return 0