from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================================================
# BUSINESS
# =========================================================

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

    default_low_stock_threshold = (
        models.PositiveIntegerField(
            default=5,
        )
    )

    order_prefix = models.CharField(
        max_length=20,
        default="ORD",
    )

    default_delivery_charge = (
        models.DecimalField(
            max_digits=12,
            decimal_places=2,
            default=Decimal("0.00"),
        )
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


# =========================================================
# BUSINESS MEMBER
# =========================================================

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
                name=(
                    "unique_business_member"
                ),
            ),
        ]

    def __str__(self):

        return (
            f"{self.user} - "
            f"{self.business} - "
            f"{self.get_role_display()}"
        )


# =========================================================
# BUSINESS INVITATION
# =========================================================

class BusinessInvitation(models.Model):

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (
            STATUS_PENDING,
            "Pending",
        ),
        (
            STATUS_ACCEPTED,
            "Accepted",
        ),
        (
            STATUS_CANCELLED,
            "Cancelled",
        ),
        (
            STATUS_EXPIRED,
            "Expired",
        ),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="invitations",
    )

    email = models.EmailField()

    role = models.CharField(
        max_length=20,
        choices=[
            (
                BusinessMember.ROLE_ADMIN,
                "Admin",
            ),
            (
                BusinessMember.ROLE_STAFF,
                "Staff",
            ),
        ],
        default=BusinessMember.ROLE_STAFF,
    )

    token = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "sent_business_invitations"
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    expires_at = models.DateTimeField()

    accepted_at = models.DateTimeField(
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

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "email",
                    "status",
                ],
                name=(
                    "business_invite_lookup"
                ),
            ),
        ]

    @property
    def is_expired(self):

        return (
            self.expires_at
            <= timezone.now()
        )

    @property
    def is_pending(self):

        return (
            self.status
            == self.STATUS_PENDING
            and
            not self.is_expired
        )

    def mark_expired_if_needed(
        self,
    ):

        if (
            self.status
            == self.STATUS_PENDING
            and
            self.is_expired
        ):

            self.status = (
                self.STATUS_EXPIRED
            )

            self.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return True

        return False

    def __str__(self):

        return (
            f"{self.email} → "
            f"{self.business.name} "
            f"({self.get_role_display()})"
        )