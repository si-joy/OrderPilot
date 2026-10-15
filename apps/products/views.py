from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.businesses.utils import get_current_business

from .forms import (
    ProductForm,
    StockAdjustmentForm,
)
from .models import (
    Product,
    StockAdjustment,
)


@login_required
def product_list(request):

    business = get_current_business(
        request.user
    )

    query = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    status = (
        request.GET
        .get(
            "status",
            "active",
        )
        .strip()
    )

    stock = (
        request.GET
        .get(
            "stock",
            "all",
        )
        .strip()
    )

    products = (
        Product.objects
        .filter(
            business=business
        )
    )

    if status == "active":

        products = (
            products.filter(
                is_active=True
            )
        )

    elif status == "inactive":

        products = (
            products.filter(
                is_active=False
            )
        )

    if query:

        products = (
            products.filter(
                Q(
                    name__icontains=query
                )
                | Q(
                    sku__icontains=query
                )
            )
        )

    if stock == "low":

        products = (
            products.filter(
                stock_quantity__lte=models.F(
                    "low_stock_threshold"
                )
            )
        )

    elif stock == "out":

        products = (
            products.filter(
                stock_quantity=0
            )
        )

    paginator = Paginator(
        products,
        10,
    )

    page_number = (
        request.GET
        .get(
            "page"
        )
    )

    page_obj = (
        paginator.get_page(
            page_number
        )
    )

    query_params = request.GET.copy()

    query_params.pop(
        "page",
        None,
    )

    filter_query = (
        query_params.urlencode()
    )

    context = {
        "products":
            page_obj.object_list,

        "page_obj":
            page_obj,

        "query":
            query,

        "status":
            status,

        "stock":
            stock,

        "business":
            business,

        "filter_query":
            filter_query,
    }

    if (
        request.headers.get(
            "HX-Request"
        )
        == "true"
    ):

        return render(
            request,
            (
                "products/partials/"
                "product_table.html"
            ),
            context,
        )

    return render(
        request,
        "products/product_list.html",
        context,
    )


@login_required
def product_detail(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    product = get_object_or_404(
        Product.objects.prefetch_related(
            "stock_adjustments__adjusted_by",
            "stock_adjustments__order",
        ),
        pk=pk,
        business=business,
    )

    stock_adjustments = (
        product.stock_adjustments
        .all()[:50]
    )

    adjustment_form = (
        StockAdjustmentForm()
    )

    return render(
        request,
        "products/product_detail.html",
        {
            "product":
                product,

            "business":
                business,

            "stock_adjustments":
                stock_adjustments,

            "adjustment_form":
                adjustment_form,
        },
    )


@login_required
def product_create(request):

    business = get_current_business(
        request.user
    )

    if request.method == "POST":

        form = ProductForm(
            request.POST,
            business=business,
        )

        if form.is_valid():

            with transaction.atomic():

                product = form.save(
                    commit=False
                )

                product.business = (
                    business
                )

                product.save()

                # =============================================
                # OPENING STOCK HISTORY
                # =============================================

                if (
                    product.stock_quantity
                    > 0
                ):

                    StockAdjustment.objects.create(
                        business=business,
                        product=product,
                        adjustment_type=(
                            StockAdjustment
                            .TYPE_OPENING
                        ),
                        quantity=(
                            product.stock_quantity
                        ),
                        before_quantity=0,
                        after_quantity=(
                            product.stock_quantity
                        ),
                        note=(
                            "Opening stock when "
                            "product was created."
                        ),
                        adjusted_by=(
                            request.user
                        ),
                    )

            messages.success(
                request,
                (
                    f"{product.name} "
                    "was created successfully."
                ),
            )

            return redirect(
                "products:detail",
                pk=product.pk,
            )

    else:

        form = ProductForm(
            business=business,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "form":
                form,

            "business":
                business,

            "page_title":
                "Add Product",

            "submit_label":
                "Create Product",
        },
    )


@login_required
def product_update(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    product = get_object_or_404(
        Product,
        pk=pk,
        business=business,
    )

    if request.method == "POST":

        form = ProductForm(
            request.POST,
            instance=product,
            business=business,
        )

        if form.is_valid():

            product = form.save(
                commit=False
            )

            product.business = (
                business
            )

            product.save()

            messages.success(
                request,
                (
                    f"{product.name} "
                    "was updated successfully."
                ),
            )

            return redirect(
                "products:detail",
                pk=product.pk,
            )

    else:

        form = ProductForm(
            instance=product,
            business=business,
        )

    return render(
        request,
        "products/product_form.html",
        {
            "form":
                form,

            "product":
                product,

            "business":
                business,

            "page_title":
                "Edit Product",

            "submit_label":
                "Save Changes",
        },
    )


# =========================================================
# MANUAL STOCK ADJUSTMENT
# =========================================================

@login_required
@require_POST
def product_stock_adjust(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    with transaction.atomic():

        product = get_object_or_404(
            Product.objects
            .select_for_update(),
            pk=pk,
            business=business,
        )

        form = StockAdjustmentForm(
            request.POST
        )

        if not form.is_valid():

            for errors in (
                form.errors.values()
            ):

                for error in errors:

                    messages.error(
                        request,
                        error,
                    )

            return redirect(
                "products:detail",
                pk=product.pk,
            )

        adjustment_type = (
            form.cleaned_data[
                "adjustment_type"
            ]
        )

        quantity = (
            form.cleaned_data[
                "quantity"
            ]
        )

        note = (
            form.cleaned_data[
                "note"
            ]
        )

        before_quantity = (
            product.stock_quantity
        )

        if (
            adjustment_type
            in StockAdjustment.INCREASE_TYPES
        ):

            after_quantity = (
                before_quantity
                + quantity
            )

        elif (
            adjustment_type
            in StockAdjustment.DECREASE_TYPES
        ):

            if (
                quantity
                > before_quantity
            ):

                messages.error(
                    request,
                    (
                        "Stock cannot be reduced "
                        "below zero. "
                        f"Available stock: "
                        f"{before_quantity}."
                    ),
                )

                return redirect(
                    "products:detail",
                    pk=product.pk,
                )

            after_quantity = (
                before_quantity
                - quantity
            )

        else:

            messages.error(
                request,
                "Invalid stock adjustment type.",
            )

            return redirect(
                "products:detail",
                pk=product.pk,
            )

        product.stock_quantity = (
            after_quantity
        )

        product.save(
            update_fields=[
                "stock_quantity",
                "updated_at",
            ]
        )

        StockAdjustment.objects.create(
            business=business,
            product=product,
            adjustment_type=(
                adjustment_type
            ),
            quantity=quantity,
            before_quantity=(
                before_quantity
            ),
            after_quantity=(
                after_quantity
            ),
            note=note,
            adjusted_by=request.user,
        )

    messages.success(
        request,
        (
            f"Stock updated from "
            f"{before_quantity} to "
            f"{after_quantity}."
        ),
    )

    return redirect(
        "products:detail",
        pk=product.pk,
    )


@login_required
@require_POST
def product_archive(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    product = get_object_or_404(
        Product,
        pk=pk,
        business=business,
    )

    product.is_active = False

    product.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"{product.name} "
            "was archived."
        ),
    )

    return redirect(
        "products:detail",
        pk=product.pk,
    )


@login_required
@require_POST
def product_restore(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    product = get_object_or_404(
        Product,
        pk=pk,
        business=business,
    )

    product.is_active = True

    product.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"{product.name} "
            "was restored."
        ),
    )

    return redirect(
        "products:detail",
        pk=product.pk,
    )