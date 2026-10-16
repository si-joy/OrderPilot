from django import forms
from django.contrib.auth import (
    get_user_model,
)

from .models import (
    Business,
    BusinessInvitation,
    BusinessMember,
)


User = get_user_model()


# =========================================================
# BUSINESS SETTINGS
# =========================================================

class BusinessSettingsForm(
    forms.ModelForm,
):

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

            "name":
                forms.TextInput(
                    attrs={
                        "class":
                            "form-control",

                        "placeholder":
                            "Business name",
                    }
                ),

            "logo":
                forms.FileInput(
                    attrs={
                        "class":
                            "business-logo-input",

                        "accept":
                            (
                                "image/png,"
                                "image/jpeg,"
                                "image/webp"
                            ),
                    }
                ),

            "phone":
                forms.TextInput(
                    attrs={
                        "class":
                            "form-control",

                        "placeholder":
                            "Business phone",
                    }
                ),

            "email":
                forms.EmailInput(
                    attrs={
                        "class":
                            "form-control",

                        "placeholder":
                            "Business email",
                    }
                ),

            "address":
                forms.Textarea(
                    attrs={
                        "class":
                            "form-control",

                        "rows":
                            3,

                        "placeholder":
                            "Business address",
                    }
                ),

            "currency":
                forms.TextInput(
                    attrs={
                        "class":
                            "form-control",

                        "placeholder":
                            "BDT",
                    }
                ),

            "default_low_stock_threshold":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",

                        "min":
                            0,
                    }
                ),

            "order_prefix":
                forms.TextInput(
                    attrs={
                        "class":
                            "form-control",

                        "placeholder":
                            "ORD",
                    }
                ),

            "default_delivery_charge":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",

                        "min":
                            0,

                        "step":
                            "0.01",
                    }
                ),

            "invoice_note":
                forms.Textarea(
                    attrs={
                        "class":
                            "form-control",

                        "rows":
                            4,

                        "placeholder":
                            (
                                "Thank you "
                                "for your order."
                            ),
                    }
                ),
        }

    def clean_name(
        self,
    ):

        return (
            self.cleaned_data[
                "name"
            ]
            .strip()
        )

    def clean_phone(
        self,
    ):

        return (
            self.cleaned_data
            .get(
                "phone",
                "",
            )
            .strip()
        )

    def clean_email(
        self,
    ):

        return (
            self.cleaned_data
            .get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

    def clean_currency(
        self,
    ):

        currency = (
            self.cleaned_data
            .get(
                "currency",
                "BDT",
            )
            .strip()
            .upper()
        )

        return (
            currency
            or
            "BDT"
        )

    def clean_order_prefix(
        self,
    ):

        prefix = (
            self.cleaned_data
            .get(
                "order_prefix",
                "",
            )
            .strip()
            .upper()
        )

        return (
            prefix
            or
            "ORD"
        )

    def clean_logo(
        self,
    ):

        logo = (
            self.cleaned_data
            .get(
                "logo"
            )
        )

        if not logo:

            return logo

        # Existing ImageField object
        # does not need upload validation.

        if not hasattr(
            logo,
            "size",
        ):

            return logo

        max_size = (
            2
            * 1024
            * 1024
        )

        if (
            logo.size
            > max_size
        ):

            raise forms.ValidationError(
                (
                    "Business logo must "
                    "be smaller than 2 MB."
                )
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
            content_type
            not in allowed_types
        ):

            raise forms.ValidationError(
                (
                    "Please upload a JPG, "
                    "PNG, or WebP image."
                )
            )

        return logo


# =========================================================
# ADD / INVITE TEAM MEMBER
# =========================================================

class TeamMemberAddForm(
    forms.Form,
):

    email = forms.EmailField(
        label="Email Address",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class":
                    "form-control",

                "placeholder":
                    "team@example.com",

                "autocomplete":
                    "email",
            }
        ),
    )

    role = forms.ChoiceField(
        choices=[
            (
                BusinessMember
                .ROLE_ADMIN,
                "Admin",
            ),
            (
                BusinessMember
                .ROLE_STAFF,
                "Staff",
            ),
        ],
        widget=forms.Select(
            attrs={
                "class":
                    "form-control",
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

        self.existing_user = None

        if (
            current_membership
            and
            current_membership.role
            == BusinessMember
            .ROLE_ADMIN
        ):

            self.fields[
                "role"
            ].choices = [
                (
                    BusinessMember
                    .ROLE_STAFF,
                    "Staff",
                ),
            ]

    def clean_email(
        self,
    ):

        email = (
            self.cleaned_data[
                "email"
            ]
            .strip()
            .lower()
        )

        user = (
            User.objects
            .filter(
                email__iexact=email
            )
            .first()
        )

        if user:

            if not user.is_active:

                raise forms.ValidationError(
                    (
                        "This OrderPilot "
                        "account is inactive."
                    )
                )

            existing_member = (
                BusinessMember.objects
                .filter(
                    business=(
                        self.business
                    ),
                    user=user,
                )
                .first()
            )

            if existing_member:

                if (
                    existing_member
                    .is_active
                ):

                    raise forms.ValidationError(
                        (
                            "This user is already "
                            "an active member of "
                            "the team."
                        )
                    )

                raise forms.ValidationError(
                    (
                        "This user already belongs "
                        "to this team but is "
                        "inactive. Restore the "
                        "member instead."
                    )
                )

        existing_invitation = (
            BusinessInvitation.objects
            .filter(
                business=(
                    self.business
                ),
                email__iexact=email,
                status=(
                    BusinessInvitation
                    .STATUS_PENDING
                ),
            )
            .order_by(
                "-created_at"
            )
            .first()
        )

        if existing_invitation:

            if (
                existing_invitation
                .is_pending
            ):

                raise forms.ValidationError(
                    (
                        "A pending invitation "
                        "has already been sent "
                        "to this email."
                    )
                )

            existing_invitation \
                .mark_expired_if_needed()

        self.existing_user = (
            user
        )

        return email

    def clean_role(
        self,
    ):

        role = (
            self.cleaned_data[
                "role"
            ]
        )

        if (
            self.current_membership
            and
            self.current_membership.role
            == BusinessMember
            .ROLE_ADMIN
            and
            role
            != BusinessMember
            .ROLE_STAFF
        ):

            raise forms.ValidationError(
                (
                    "Admins can only invite "
                    "Staff members."
                )
            )

        return role

    def get_existing_user(
        self,
    ):

        return (
            self.existing_user
        )


# =========================================================
# TEAM MEMBER ROLE UPDATE
# =========================================================

class TeamMemberRoleForm(
    forms.Form,
):

    role = forms.ChoiceField(
        choices=[
            (
                BusinessMember
                .ROLE_ADMIN,
                "Admin",
            ),
            (
                BusinessMember
                .ROLE_STAFF,
                "Staff",
            ),
        ],
        widget=forms.Select(
            attrs={
                "class":
                    "form-control",
            }
        ),
    )