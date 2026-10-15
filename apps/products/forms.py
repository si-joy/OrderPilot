from django import forms

from .models import (
    Product,
    StockAdjustment,
)


class ProductForm(forms.ModelForm):

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

        # Existing product stock must not be changed
        # directly from the normal product edit form.
        if (
            self.instance
            and self.instance.pk
        ):
            self.fields[
                "stock_quantity"
            ].disabled = True

            self.fields[
                "stock_quantity"
            ].help_text = (
                "Use Adjust Stock from the product "
                "details page to change inventory."
            )

    class Meta:
        model = Product

        fields = [
            "name",
            "sku",
            "selling_price",
            "cost_price",
            "stock_quantity",
            "low_stock_threshold",
            "description",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class":
                        "form-control",
                    "placeholder":
                        "Enter product name",
                }
            ),

            "sku": forms.TextInput(
                attrs={
                    "class":
                        "form-control",
                    "placeholder":
                        "Example: PROD-001",
                }
            ),

            "selling_price":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",
                        "step":
                            "0.01",
                        "min":
                            "0",
                    }
                ),

            "cost_price":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",
                        "step":
                            "0.01",
                        "min":
                            "0",
                    }
                ),

            "stock_quantity":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",
                        "min":
                            "0",
                    }
                ),

            "low_stock_threshold":
                forms.NumberInput(
                    attrs={
                        "class":
                            "form-control",
                        "min":
                            "0",
                    }
                ),

            "description":
                forms.Textarea(
                    attrs={
                        "class":
                            "form-control",
                        "rows":
                            4,
                        "placeholder":
                            "Optional product description",
                    }
                ),

            "is_active":
                forms.CheckboxInput(
                    attrs={
                        "class":
                            "form-checkbox",
                    }
                ),
        }

    def clean_sku(self):

        sku = (
            self.cleaned_data
            .get(
                "sku",
                "",
            )
            .strip()
        )

        if not sku:
            return sku

        if not self.business:
            return sku

        queryset = (
            Product.objects
            .filter(
                business=self.business,
                sku__iexact=sku,
            )
        )

        if (
            self.instance
            and self.instance.pk
        ):
            queryset = (
                queryset.exclude(
                    pk=self.instance.pk
                )
            )

        if queryset.exists():

            raise forms.ValidationError(
                (
                    "A product with this SKU "
                    "already exists for this business."
                )
            )

        return sku


# =========================================================
# STOCK ADJUSTMENT FORM
# =========================================================

class StockAdjustmentForm(forms.Form):

    MANUAL_TYPE_CHOICES = [
        (
            StockAdjustment.TYPE_RESTOCK,
            "Restock",
        ),
        (
            StockAdjustment.TYPE_RETURN,
            "Customer Return",
        ),
        (
            StockAdjustment.TYPE_CORRECTION_ADD,
            "Stock Correction (+)",
        ),
        (
            StockAdjustment.TYPE_CORRECTION_REMOVE,
            "Stock Correction (-)",
        ),
        (
            StockAdjustment.TYPE_DAMAGED,
            "Damaged Stock",
        ),
        (
            StockAdjustment.TYPE_LOST,
            "Lost Stock",
        ),
    ]

    adjustment_type = forms.ChoiceField(
        choices=MANUAL_TYPE_CHOICES,
        widget=forms.Select(
            attrs={
                "class":
                    "form-control",
            }
        ),
    )

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class":
                    "form-control",
                "min":
                    "1",
                "placeholder":
                    "Quantity",
            }
        ),
    )

    note = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class":
                    "form-control",
                "placeholder":
                    "Optional reason or note",
            }
        ),
    )