from django.conf import settings
from django.db import models


class Notification(models.Model):

    TYPE_INFO = "info"
    TYPE_SUCCESS = "success"
    TYPE_WARNING = "warning"
    TYPE_DANGER = "danger"

    TYPE_CHOICES = [
        (TYPE_INFO, "Info"),
        (TYPE_SUCCESS, "Success"),
        (TYPE_WARNING, "Warning"),
        (TYPE_DANGER, "Danger"),
    ]

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=160,
    )

    message = models.CharField(
        max_length=500,
    )

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_INFO,
    )

    url = models.CharField(
        max_length=500,
        blank=True,
    )

    event_key = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "business",
                    "is_read",
                    "-created_at",
                ]
            ),
        ]

    def __str__(self):
        return self.title