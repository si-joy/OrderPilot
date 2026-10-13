from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import (
    Business,
    BusinessMember,
)


User = get_user_model()


# =========================================================
# BUSINESS SETTINGS
# =========================================================

class BusinessSettingsForm(forms.ModelForm):

    class Meta:
        model = Business

        fields = [
            "name",
            "logo",
            "phone",
            "email",
            "address",
            "currency",
            "default_low_stock_threshold",
            "order_prefix",
            "default_delivery_charge",
            "invoice_note",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Business name",
                }
            ),

            "logo": forms.FileInput(
                attrs={
                    "class": "business-logo-input",
                    "accept": (
                        "image/png,"
                        "image/jpeg,"
                        "image/webp"
                    ),
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Business phone",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Business email",
                }
            ),

            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Business address",
                }
            ),

            "currency": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "BDT",
                }
            ),

            "default_low_stock_threshold": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),

            "order_prefix": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ORD",
                }
            ),

            "default_delivery_charge": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "step": "0.01",
                }
            ),

            "invoice_note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Thank you for your order."
                    ),
                }
            ),
        }

    def clean_name(self):
        return (
            self.cleaned_data["name"]
            .strip()
        )

    def clean_phone(self):
        return (
            self.cleaned_data
            .get("phone", "")
            .strip()
        )

    def clean_email(self):
        return (
            self.cleaned_data
            .get("email", "")
            .strip()
            .lower()
        )

    def clean_currency(self):
        currency = (
            self.cleaned_data
            .get("currency", "BDT")
            .strip()
            .upper()
        )

        return currency or "BDT"

    def clean_order_prefix(self):
        prefix = (
            self.cleaned_data
            .get("order_prefix", "")
            .strip()
            .upper()
        )

        return prefix or "ORD"

    def clean_logo(self):
        logo = self.cleaned_data.get(
            "logo"
        )

        if not logo:
            return logo

        # Existing ImageField object
        # does not need upload validation.
        if not hasattr(logo, "size"):
            return logo

        max_size = (
            2
            * 1024
            * 1024
        )

        if logo.size > max_size:
            raise forms.ValidationError(
                "Business logo must be smaller "
                "than 2 MB."
            )

        content_type = getattr(
            logo,
            "content_type",
            "",
        )

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        if (
            content_type
            and
            content_type not in allowed_types
        ):
            raise forms.ValidationError(
                "Please upload a JPG, PNG, "
                "or WebP image."
            )

        return logo


# =========================================================
# ADD TEAM MEMBER
# =========================================================

class TeamMemberAddForm(forms.Form):
    user_identifier = forms.CharField(
        label="Username or Email",
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Enter username or email"
                ),
            }
        ),
    )

    role = forms.ChoiceField(
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
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    def __init__(
        self,
        *args,
        business=None,
        current_membership=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.business = business
        self.current_membership = (
            current_membership
        )

        if (
            current_membership
            and
            current_membership.role
            == BusinessMember.ROLE_ADMIN
        ):
            self.fields[
                "role"
            ].choices = [
                (
                    BusinessMember.ROLE_STAFF,
                    "Staff",
                ),
            ]

    def clean_user_identifier(self):
        value = (
            self.cleaned_data[
                "user_identifier"
            ]
            .strip()
        )

        user = (
            User.objects
            .filter(
                Q(
                    username__iexact=value
                )
                |
                Q(
                    email__iexact=value
                )
            )
            .first()
        )

        if not user:
            raise forms.ValidationError(
                "No OrderPilot account was "
                "found with that username "
                "or email."
            )

        if not user.is_active:
            raise forms.ValidationError(
                "This user account is inactive."
            )

        existing = (
            BusinessMember.objects
            .filter(
                business=self.business,
                user=user,
            )
            .first()
        )

        if existing:
            if existing.is_active:
                raise forms.ValidationError(
                    "This user is already an "
                    "active member of this "
                    "business."
                )

            raise forms.ValidationError(
                "This member already exists "
                "but is inactive. Restore the "
                "member instead."
            )

        self.cleaned_user = user

        return value

    def clean_role(self):
        role = self.cleaned_data[
            "role"
        ]

        if (
            self.current_membership
            and
            self.current_membership.role
            == BusinessMember.ROLE_ADMIN
            and
            role
            != BusinessMember.ROLE_STAFF
        ):
            raise forms.ValidationError(
                "Admins can only add Staff "
                "members."
            )

        return role

    def get_user(self):
        return getattr(
            self,
            "cleaned_user",
            None,
        )


# =========================================================
# TEAM MEMBER ROLE UPDATE
# =========================================================

class TeamMemberRoleForm(forms.Form):
    role = forms.ChoiceField(
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
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )