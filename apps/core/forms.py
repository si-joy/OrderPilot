from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import UserProfile


User = get_user_model()


# =========================================================
# LOGIN
# =========================================================

class OrderPilotAuthenticationForm(
    AuthenticationForm,
):

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autofocus": True,
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
            }
        )
    )


# =========================================================
# SIGNUP / BUSINESS ONBOARDING
# =========================================================

class OrderPilotSignupForm(
    UserCreationForm,
):

    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First name",
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last name",
            }
        ),
    )

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email address",
            }
        ),
    )

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autocomplete": "username",
            }
        ),
    )

    business_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Business name",
            }
        ),
    )

    business_phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Business phone",
            }
        ),
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Create password",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "email",
            "username",
            "business_name",
            "business_phone",
            "password1",
            "password2",
        ]

    def __init__(
        self,
        *args,
        invitation=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.invitation = invitation

        if invitation:

            self.fields[
                "email"
            ].initial = invitation.email

            self.fields[
                "email"
            ].disabled = True

            self.fields[
                "business_name"
            ].required = False

            self.fields[
                "business_phone"
            ].required = False

            self.fields[
                "business_name"
            ].widget = forms.HiddenInput()

            self.fields[
                "business_phone"
            ].widget = forms.HiddenInput()

    def clean_email(
        self,
    ):

        if self.invitation:

            email = (
                self.invitation.email
                .strip()
                .lower()
            )

        else:

            email = (
                self.cleaned_data
                .get(
                    "email",
                    "",
                )
                .strip()
                .lower()
            )

        if User.objects.filter(
            email__iexact=email
        ).exists():

            raise forms.ValidationError(
                (
                    "An account with this "
                    "email already exists."
                )
            )

        return email

    def clean_business_name(
        self,
    ):

        if self.invitation:

            return (
                self.invitation
                .business
                .name
            )

        business_name = (
            self.cleaned_data
            .get(
                "business_name",
                "",
            )
            .strip()
        )

        if len(
            business_name
        ) < 2:

            raise forms.ValidationError(
                (
                    "Please enter a valid "
                    "business name."
                )
            )

        return business_name

    def save(
        self,
        commit=True,
    ):

        user = super().save(
            commit=False
        )

        user.first_name = (
            self.cleaned_data[
                "first_name"
            ]
            .strip()
        )

        user.last_name = (
            self.cleaned_data[
                "last_name"
            ]
            .strip()
        )

        user.email = (
            self.cleaned_data[
                "email"
            ]
            .strip()
            .lower()
        )

        if commit:
            user.save()

        return user


# =========================================================
# PASSWORD CHANGE
# =========================================================

class OrderPilotPasswordChangeForm(
    PasswordChangeForm,
):

    old_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Current password"
                ),
            }
        )
    )

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "New password"
                ),
            }
        )
    )

    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Confirm new password"
                ),
            }
        )
    )


# =========================================================
# PASSWORD RESET
# =========================================================

class OrderPilotPasswordResetForm(
    PasswordResetForm,
):

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Email address"
                ),
            }
        )
    )


class OrderPilotSetPasswordForm(
    SetPasswordForm,
):

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "New password"
                ),
            }
        )
    )

    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Confirm new password"
                ),
            }
        )
    )


# =========================================================
# PROFILE UPDATE
# =========================================================

class ProfileUpdateForm(
    forms.Form,
):

    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "First name"
                ),
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Last name"
                ),
            }
        ),
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Email address"
                ),
            }
        ),
    )

    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Phone number"
                ),
            }
        ),
    )

    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": (
                    "profile-avatar-input"
                ),
                "accept": (
                    "image/png,"
                    "image/jpeg,"
                    "image/webp"
                ),
            }
        ),
    )

    remove_avatar = forms.BooleanField(
        required=False,
    )

    def __init__(
        self,
        *args,
        user=None,
        profile=None,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )

        self.user = user
        self.profile = profile

        if (
            user
            and
            not self.is_bound
        ):

            self.fields[
                "first_name"
            ].initial = (
                user.first_name
            )

            self.fields[
                "last_name"
            ].initial = (
                user.last_name
            )

            self.fields[
                "email"
            ].initial = (
                user.email
            )

        if (
            profile
            and
            not self.is_bound
        ):

            self.fields[
                "phone"
            ].initial = (
                profile.phone
            )

    def clean_email(
        self,
    ):

        email = (
            self.cleaned_data
            .get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        if not email:

            return email

        queryset = (
            User.objects
            .filter(
                email__iexact=email
            )
        )

        if self.user:

            queryset = (
                queryset.exclude(
                    pk=self.user.pk
                )
            )

        if queryset.exists():

            raise forms.ValidationError(
                (
                    "This email address "
                    "is already in use."
                )
            )

        return email

    def clean_avatar(
        self,
    ):

        avatar = (
            self.cleaned_data
            .get(
                "avatar"
            )
        )

        if not avatar:

            return avatar

        if (
            avatar.size
            > 2 * 1024 * 1024
        ):

            raise forms.ValidationError(
                (
                    "Avatar must be "
                    "smaller than 2 MB."
                )
            )

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        content_type = getattr(
            avatar,
            "content_type",
            "",
        )

        if (
            content_type
            not in allowed_types
        ):

            raise forms.ValidationError(
                (
                    "Please upload a JPG, "
                    "PNG, or WebP image."
                )
            )

        return avatar

    def save(
        self,
    ):

        user = self.user
        profile = self.profile

        user.first_name = (
            self.cleaned_data[
                "first_name"
            ]
            .strip()
        )

        user.last_name = (
            self.cleaned_data[
                "last_name"
            ]
            .strip()
        )

        user.email = (
            self.cleaned_data[
                "email"
            ]
            .strip()
            .lower()
        )

        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "email",
            ]
        )

        profile.phone = (
            self.cleaned_data[
                "phone"
            ]
            .strip()
        )

        if (
            self.cleaned_data
            .get(
                "remove_avatar"
            )
        ):

            if profile.avatar:

                profile.avatar.delete(
                    save=False
                )

            profile.avatar = None

        new_avatar = (
            self.cleaned_data
            .get(
                "avatar"
            )
        )

        if new_avatar:

            if profile.avatar:

                profile.avatar.delete(
                    save=False
                )

            profile.avatar = (
                new_avatar
            )

        profile.save()

        return (
            user,
            profile,
        )