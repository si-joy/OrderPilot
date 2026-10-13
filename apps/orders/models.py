import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


def generate_order_number():
    return f"OP-{uuid.uuid4().hex[:8].upper()}"


class Order(models.Model):

    # =====================================================
    # ORDER STATUS
    # =====================================================

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_RETURNED = "returned"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_RETURNED, "Returned"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # =====================================================
    # PAYMENT METHOD
    # =====================================================

    PAYMENT_COD = "cod"
    PAYMENT_BKASH = "bkash"
    PAYMENT_NAGAD = "nagad"
    PAYMENT_BANK = "bank"
    PAYMENT_OTHER = "other"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_COD, "Cash"),
        (PAYMENT_BKASH, "bKash"),
        (PAYMENT_NAGAD, "Nagad"),
        (PAYMENT_BANK, "Bank Transfer"),
        (PAYMENT_OTHER, "Other"),
    ]

    # =====================================================
    # PAYMENT STATUS
    # =====================================================

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUNDED = "refunded"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_UNPAID, "Unpaid"),
        (PAYMENT_PARTIAL, "Partial"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_REFUNDED, "Refunded"),
    ]

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="orders",
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    # =====================================================
    # ORDER INFORMATION
    # =====================================================

    order_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_number,
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # =====================================================
    # PAYMENT SUMMARY
    # =====================================================

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_COD,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_UNPAID,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    delivery_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # =====================================================
    # INVENTORY STATE
    # =====================================================

    stock_deducted = models.BooleanField(
        default=False,
        help_text=(
            "Indicates whether inventory has already "
            "been deducted for this order."
        ),
    )

    # =====================================================
    # DELIVERY / COURIER
    # =====================================================

    courier_name = models.CharField(
        max_length=120,
        blank=True,
    )

    tracking_number = models.CharField(
        max_length=120,
        blank=True,
    )

    delivery_address = models.TextField(
        blank=True,
    )

    # =====================================================
    # OTHER INFORMATION
    # =====================================================

    notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_orders",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["business", "status"],
            ),
            models.Index(
                fields=["business", "created_at"],
            ),
            models.Index(
                fields=["business", "customer"],
            ),
            models.Index(
                fields=["order_number"],
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="order_subtotal_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(discount__gte=0),
                name="order_discount_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(delivery_charge__gte=0),
                name="order_delivery_charge_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="order_total_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(paid_amount__gte=0),
                name="order_paid_amount_non_negative",
            ),
        ]

    # =====================================================
    # METHODS
    # =====================================================

    def __str__(self):
        return self.order_number

    @property
    def due_amount(self):

        due = (
            self.total_amount
            - self.paid_amount
        )

        if due < Decimal("0.00"):
            return Decimal("0.00")

        return due


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_name = models.CharField(
        max_length=160,
    )

    sku = models.CharField(
        max_length=80,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="order_item_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="order_item_cost_non_negative",
            ),
        ]

    def __str__(self):
        return (
            f"{self.product_name} "
            f"× {self.quantity}"
        )

    @property
    def line_total(self):
        return (
            self.unit_price
            * self.quantity
        )

    @property
    def line_cost(self):
        return (
            self.unit_cost
            * self.quantity
        )


class OrderStatusHistory(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    from_status = models.CharField(
        max_length=20,
        choices=Order.STATUS_CHOICES,
        blank=True,
    )

    to_status = models.CharField(
        max_length=20,
        choices=Order.STATUS_CHOICES,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.order.order_number}: "
            f"{self.from_status or 'New'} "
            f"→ {self.to_status}"
        )


# =========================================================
# ORDER PAYMENT
# =========================================================

class OrderPayment(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="order_payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Order.PAYMENT_METHOD_CHOICES,
    )

    reference = models.CharField(
        max_length=120,
        blank=True,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_order_payments",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "order",
                    "created_at",
                ],
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="order_payment_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.order.order_number} "
            f"- {self.amount}"
        )


class CourierSettlement(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PARTIAL = "partial"
    STATUS_SETTLED = "settled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_SETTLED, "Settled"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="courier_settlement",
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="courier_settlements",
    )

    courier_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    return_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    cod_expected = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    cod_received = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    settlement_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    reference = models.CharField(
        max_length=120,
        blank=True,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    settled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "settlement_status",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(courier_charge__gte=0),
                name="courier_charge_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(return_charge__gte=0),
                name="courier_return_charge_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(cod_expected__gte=0),
                name="courier_cod_expected_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(cod_received__gte=0),
                name="courier_cod_received_non_negative",
            ),
        ]

    @property
    def outstanding_amount(self):
        due = self.cod_expected - self.cod_received

        if due < Decimal("0.00"):
            return Decimal("0.00")

        return due

    def __str__(self):
        return (
            f"{self.order.order_number} - "
            f"{self.get_settlement_status_display()}"
        )