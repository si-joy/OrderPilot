from .models import Notification


def notification_context(request):

    if not request.user.is_authenticated:
        return {
            "header_notifications": [],
            "unread_notification_count": 0,
        }

    try:

        from apps.businesses.utils import (
            get_current_business,
        )

        business = get_current_business(
            request.user
        )

    except Exception:

        return {
            "header_notifications": [],
            "unread_notification_count": 0,
        }

    notifications = (
        Notification.objects
        .filter(
            business=business,
        )
        .filter(
            user__isnull=True,
        )
        .order_by(
            "-created_at"
        )
    )

    unread_count = (
        notifications
        .filter(
            is_read=False,
        )
        .count()
    )

    return {
        "header_notifications":
            notifications[:8],

        "unread_notification_count":
            unread_count,
    }