from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.businesses.utils import get_current_business

from .forms import ProductForm
from .models import Product


@login_required
def product_list(request):
    business = get_current_business(request.user)

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active").strip()
    stock = request.GET.get("stock", "all").strip()

    products = Product.objects.filter(
        business=business
    )

    if status == "active":
        products = products.filter(
            is_active=True
        )

    elif status == "inactive":
        products = products.filter(
            is_active=False
        )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
        )

    if stock == "low":
        products = products.filter(
            stock_quantity__lte=models.F(
                "low_stock_threshold"
            )
        )

    elif stock == "out":
        products = products.filter(
            stock_quantity=0
        )

    paginator = Paginator(
        products,
        10,
    )

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(
        page_number
    )

    context = {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "stock": stock,
        "business": business,
    }

    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "products/partials/product_table.html",
            context,
        )

    return render(
        request,
        "products/product_list.html",
        context,
    )


@login_required
def product_detail(request, pk):
    business = get_current_business(request.user)

    product = get_object_or_404(
        Product,
        pk=pk,
        business=business,
    )

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "business": business,
        },
    )


@login_required
def product_create(request):
    business = get_current_business(request.user)

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            business=business,
        )

        if form.is_valid():
            product = form.save(
                commit=False
            )

            product.business = business
            product.save()

            messages.success(
                request,
                f"{product.name} was created successfully.",
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
            "form": form,
            "business": business,
            "page_title": "Add Product",
            "submit_label": "Create Product",
        },
    )


@login_required
def product_update(request, pk):
    business = get_current_business(request.user)

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

            product.business = business
            product.save()

            messages.success(
                request,
                f"{product.name} was updated successfully.",
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
            "form": form,
            "product": product,
            "business": business,
            "page_title": "Edit Product",
            "submit_label": "Save Changes",
        },
    )


@login_required
@require_POST
def product_archive(request, pk):
    business = get_current_business(request.user)

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
        f"{product.name} was archived.",
    )

    return redirect(
        "products:detail",
        pk=product.pk,
    )


@login_required
@require_POST
def product_restore(request, pk):
    business = get_current_business(request.user)

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
        f"{product.name} was restored.",
    )

    return redirect(
        "products:detail",
        pk=product.pk,
    )