from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.businesses.utils import get_current_business

from .models import Notification


@login_required
def notification_list(request):

    business = get_current_business(
        request.user
    )

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

    return render(
        request,
        "notifications/notification_list.html",
        {
            "notifications":
                notifications,

            "business":
                business,
        },
    )


@login_required
@require_POST
def notification_mark_read(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    notification = get_object_or_404(
        Notification,
        pk=pk,
        business=business,
    )

    if not notification.is_read:

        notification.is_read = True

        notification.read_at = (
            timezone.now()
        )

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

    next_url = (
        request.POST
        .get(
            "next",
            "",
        )
        .strip()
    )

    if next_url:
        return redirect(
            next_url
        )

    if notification.url:
        return redirect(
            notification.url
        )

    return redirect(
        "notifications:list"
    )


@login_required
@require_POST
def notification_mark_all_read(
    request,
):

    business = get_current_business(
        request.user
    )

    Notification.objects.filter(
        business=business,
        is_read=False,
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )

    return redirect(
        request.POST.get(
            "next",
            "notifications:list",
        )
    )