from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import (
    OrderPilotPasswordChangeForm,
    OrderPilotPasswordResetForm,
    OrderPilotSetPasswordForm,
)


app_name = "core"


urlpatterns = [
    path(
        "",
        views.dashboard,
        name="dashboard",
    ),

    path(
        "login/",
        views.OrderPilotLoginView.as_view(),
        name="login",
    ),

    path(
        "signup/",
        views.signup,
        name="signup",
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),

    path(
        "profile/",
        views.profile,
        name="profile",
    ),

    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="auth/password_change.html",
            form_class=OrderPilotPasswordChangeForm,
            success_url=reverse_lazy(
                "core:profile"
            ),
        ),
        name="password_change",
    ),

    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset.html",
            form_class=OrderPilotPasswordResetForm,
            email_template_name="auth/password_reset_email.txt",
            subject_template_name="auth/password_reset_subject.txt",
            success_url=reverse_lazy(
                "core:password_reset_done"
            ),
        ),
        name="password_reset",
    ),

    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html",
        ),
        name="password_reset_done",
    ),

    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            form_class=OrderPilotSetPasswordForm,
            success_url=reverse_lazy(
                "core:password_reset_complete"
            ),
        ),
        name="password_reset_confirm",
    ),

    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    
]