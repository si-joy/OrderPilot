from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.customers.models import Customer
from apps.products.models import Product

from .models import (
    CourierSettlement,
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
)

from django.db.models import Q

# =========================================================
# ORDER FORM
# =========================================================

class OrderForm(forms.ModelForm):

    class Meta:
        model = Order

        fields = [
            "customer",
            "status",
            "payment_method",
            "discount",
            "delivery_charge",
            "paid_amount",
            "courier_name",
            "tracking_number",
            "delivery_address",
            "notes",
        ]

        widgets = {
            "customer": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "payment_method": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "discount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "delivery_charge": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "paid_amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "courier_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Courier name",
                }
            ),

            "tracking_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Tracking number",
                }
            ),

            "delivery_address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Delivery address",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Optional notes",
                }
            ),
        }

    def __init__(
        self,
        *args,
        business=None,
        edit_mode=False,
        financial_editable=True,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.business = business
        self.edit_mode = edit_mode
        self.financial_editable = (
            financial_editable
        )

        # =====================================================
        # CUSTOMER QUERYSET
        #
        # Include the currently selected customer even if that
        # customer has since been archived/inactivated.
        # =====================================================

        if business:

            customer_queryset = (
                Customer.objects
                .filter(
                    business=business,
                )
            )

            current_customer_id = (
                getattr(
                    self.instance,
                    "customer_id",
                    None,
                )
            )

            if current_customer_id:

                customer_queryset = (
                    customer_queryset
                    .filter(
                        Q(is_active=True)
                        | Q(
                            pk=current_customer_id
                        )
                    )
                )

            else:

                customer_queryset = (
                    customer_queryset
                    .filter(
                        is_active=True,
                    )
                )

            self.fields[
                "customer"
            ].queryset = (
                customer_queryset
                .order_by(
                    "full_name"
                )
            )

        else:

            self.fields[
                "customer"
            ].queryset = (
                Customer.objects.none()
            )

        # =====================================================
        # EDIT MODE SAFETY
        # =====================================================

        if edit_mode:

            # Status changes must always go through the
            # dedicated status workflow.
            self.fields[
                "status"
            ].disabled = True

            # Payment totals must only change through
            # payment/refund history.
            self.fields[
                "paid_amount"
            ].disabled = True

            if not financial_editable:

                # Shipped / delivered / returned /
                # cancelled orders only allow operational
                # information corrections.

                for field_name in [
                    "customer",
                    "payment_method",
                    "discount",
                    "delivery_charge",
                ]:

                    self.fields[
                        field_name
                    ].disabled = True

    def clean_customer(self):

        customer = (
            self.cleaned_data
            .get("customer")
        )

        if (
            customer
            and self.business
            and customer.business_id
            != self.business.id
        ):

            raise forms.ValidationError(
                "Invalid customer selected."
            )

        return customer

# =========================================================
# ORDER ITEM FORM
# =========================================================

class OrderItemForm(forms.ModelForm):

    class Meta:
        model = OrderItem

        fields = [
            "product",
            "quantity",
        ]

        widgets = {
            "product": forms.Select(
                attrs={
                    "class":
                    "form-control "
                    "order-product-select",
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class":
                    "form-control "
                    "order-quantity-input",
                    "min": "1",
                }
            ),
        }

    def __init__(
        self,
        *args,
        business=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.business = business

        if business:

            product_queryset = (
                Product.objects
                .filter(
                    business=business,
                )
            )

            current_product_id = (
                getattr(
                    self.instance,
                    "product_id",
                    None,
                )
            )

            if current_product_id:

                product_queryset = (
                    product_queryset
                    .filter(
                        Q(is_active=True)
                        | Q(
                            pk=current_product_id
                        )
                    )
                )

            else:

                product_queryset = (
                    product_queryset
                    .filter(
                        is_active=True,
                    )
                )

            self.fields[
                "product"
            ].queryset = (
                product_queryset
                .order_by(
                    "name"
                )
            )

        else:

            self.fields[
                "product"
            ].queryset = (
                Product.objects.none()
            )

    def clean_product(self):

        product = (
            self.cleaned_data
            .get("product")
        )

        if (
            product
            and self.business
            and product.business_id
            != self.business.id
        ):

            raise forms.ValidationError(
                "Invalid product selected."
            )

        return product

OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# =========================================================
# RECORD PAYMENT FORM
# =========================================================

class OrderPaymentForm(forms.ModelForm):

    class Meta:
        model = OrderPayment

        fields = [
            "amount",
            "payment_method",
            "reference",
            "note",
        ]

        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "Payment amount",
                }
            ),

            "payment_method": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Transaction / reference ID",
                }
            ),

            "note": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Optional payment note",
                }
            ),
        }

    def __init__(
        self,
        *args,
        order=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.order = order

    def clean_amount(self):

        amount = (
            self.cleaned_data
            .get("amount")
        )

        if amount is None:
            return amount

        if amount <= Decimal("0.00"):
            raise forms.ValidationError(
                "Payment amount must be greater than zero."
            )

        if self.order:

            if self.order.status in {
                Order.STATUS_CANCELLED,
                Order.STATUS_RETURNED,
            }:
                raise forms.ValidationError(
                    (
                        "Payments cannot be recorded for "
                        f"{self.order.get_status_display().lower()} orders."
                    )
                )

            if (
                self.order.due_amount
                <= Decimal("0.00")
            ):
                raise forms.ValidationError(
                    "This order has already been fully paid."
                )

            if (
                amount
                > self.order.due_amount
            ):
                raise forms.ValidationError(
                    (
                        "Payment cannot exceed "
                        f"the due amount of "
                        f"৳{self.order.due_amount}."
                    )
                )

        return amount


# =========================================================
# ORDER REFUND FORM
# =========================================================

class OrderRefundForm(forms.ModelForm):

    class Meta:
        model = OrderRefund

        fields = [
            "amount",
            "refund_method",
            "reference",
            "note",
        ]

        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "Refund amount",
                }
            ),

            "refund_method": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Refund transaction / reference ID",
                }
            ),

            "note": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Optional refund note",
                }
            ),
        }

    def __init__(
        self,
        *args,
        order=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.order = order

    def clean_amount(self):

        amount = (
            self.cleaned_data
            .get("amount")
        )

        if amount is None:
            return amount

        if amount <= Decimal("0.00"):
            raise forms.ValidationError(
                "Refund amount must be greater than zero."
            )

        if self.order:

            refundable_amount = (
                self.order.refundable_amount
            )

            if (
                refundable_amount
                <= Decimal("0.00")
            ):
                raise forms.ValidationError(
                    "This order has no refundable payment."
                )

            if (
                amount
                > refundable_amount
            ):
                raise forms.ValidationError(
                    (
                        "Refund cannot exceed "
                        f"the refundable amount of "
                        f"৳{refundable_amount}."
                    )
                )

        return amount


# =========================================================
# COURIER + COD SETTLEMENT FORM
# =========================================================

class CourierSettlementForm(forms.ModelForm):

    courier_name = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Pathao Courier",
            }
        ),
    )

    tracking_number = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Courier tracking ID",
            }
        ),
    )

    class Meta:
        model = CourierSettlement

        fields = [
            "courier_charge",
            "return_charge",
            "cod_expected",
            "cod_received",
            "reference",
            "note",
        ]

        widgets = {
            "courier_charge": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "return_charge": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "cod_expected": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "cod_received": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),

            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Settlement / transaction reference",
                }
            ),

            "note": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder":
                    "Optional settlement note",
                }
            ),
        }

    def __init__(
        self,
        *args,
        order=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.order = order

        if order:

            self.fields[
                "courier_name"
            ].initial = (
                order.courier_name
            )

            self.fields[
                "tracking_number"
            ].initial = (
                order.tracking_number
            )

            if not self.instance.pk:

                self.fields[
                    "cod_expected"
                ].initial = (
                    order.due_amount
                )

                self.fields[
                    "cod_received"
                ].initial = Decimal(
                    "0.00"
                )

    def clean(self):

        cleaned_data = super().clean()

        cod_expected = (
            cleaned_data.get(
                "cod_expected"
            )
            or Decimal("0.00")
        )

        cod_received = (
            cleaned_data.get(
                "cod_received"
            )
            or Decimal("0.00")
        )

        if (
            cod_received
            > cod_expected
        ):
            self.add_error(
                "cod_received",
                (
                    "COD received cannot exceed "
                    "the expected COD amount."
                ),
            )

        return cleaned_data