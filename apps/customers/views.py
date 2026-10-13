from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from apps.businesses.utils import get_current_business
from apps.orders.models import Order

from .forms import CustomerForm
from .models import Customer


# =========================================================
# CUSTOMER LIST
# =========================================================

@login_required
def customer_list(request):
    business = get_current_business(
        request.user
    )

    query = (
        request.GET
        .get("q", "")
        .strip()
    )

    status = (
        request.GET
        .get("status", "active")
        .strip()
    )

    customers = (
        Customer.objects
        .filter(
            business=business
        )
    )

    # -----------------------------------------------------
    # STATUS FILTER
    # -----------------------------------------------------

    if status == "active":

        customers = customers.filter(
            is_active=True
        )

    elif status == "inactive":

        customers = customers.filter(
            is_active=False
        )


    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if query:

        customers = customers.filter(

            Q(
                full_name__icontains=query
            )

            | Q(
                phone__icontains=query
            )

            | Q(
                email__icontains=query
            )

            | Q(
                city__icontains=query
            )

            | Q(
                district__icontains=query
            )
        )


    # -----------------------------------------------------
    # PAGINATION
    # -----------------------------------------------------

    paginator = Paginator(
        customers,
        10,
    )

    page_number = (
        request.GET
        .get("page")
    )

    page_obj = (
        paginator
        .get_page(page_number)
    )


    context = {
        "page_obj": page_obj,
        "customers": page_obj.object_list,
        "query": query,
        "status": status,
        "business": business,
    }


    # -----------------------------------------------------
    # HTMX PARTIAL RESPONSE
    # -----------------------------------------------------

    if (
        request.headers.get("HX-Request")
        == "true"
    ):

        return render(
            request,
            "customers/partials/customer_table.html",
            context,
        )


    return render(
        request,
        "customers/customer_list.html",
        context,
    )


# =========================================================
# CUSTOMER DETAIL
# =========================================================

@login_required
def customer_detail(request, pk):
    business = get_current_business(
        request.user
    )

    customer = get_object_or_404(
        Customer,
        pk=pk,
        business=business,
    )


    # -----------------------------------------------------
    # CUSTOMER ORDERS
    # -----------------------------------------------------

    orders = (
        Order.objects
        .filter(
            business=business,
            customer=customer,
        )
        .select_related(
            "customer",
        )
        .prefetch_related(
            "items",
            "payments",
        )
        .order_by(
            "-created_at"
        )
    )


    # -----------------------------------------------------
    # TOTAL ORDERS
    # -----------------------------------------------------

    total_orders = (
        orders.count()
    )


    # -----------------------------------------------------
    # TOTAL SPENT
    #
    # Only delivered orders are treated as completed sales.
    # -----------------------------------------------------

    delivered_orders = (
        orders.filter(
            status=Order.STATUS_DELIVERED
        )
    )

    total_spent = (
        delivered_orders
        .aggregate(
            total=Sum(
                "total_amount"
            )
        )
        .get("total")
        or 0
    )


    # -----------------------------------------------------
    # TOTAL PAID
    #
    # Includes payments against all orders.
    # -----------------------------------------------------

    total_paid = (
        orders
        .aggregate(
            total=Sum(
                "paid_amount"
            )
        )
        .get("total")
        or 0
    )


    # -----------------------------------------------------
    # TOTAL DUE
    #
    # Uses the order due_amount property.
    # -----------------------------------------------------

    total_due = sum(
        (
            order.due_amount
            for order in orders
        ),
        0,
    )


    context = {
        "customer": customer,
        "business": business,

        "orders": orders,

        "total_orders": total_orders,
        "total_spent": total_spent,
        "total_paid": total_paid,
        "total_due": total_due,
    }


    return render(
        request,
        "customers/customer_detail.html",
        context,
    )


# =========================================================
# CREATE CUSTOMER
# =========================================================

@login_required
def customer_create(request):
    business = get_current_business(
        request.user
    )

    if request.method == "POST":

        form = CustomerForm(
            request.POST
        )

        if form.is_valid():

            customer = form.save(
                commit=False
            )

            customer.business = business

            customer.save()


            messages.success(
                request,
                (
                    f"{customer.full_name} "
                    "was added successfully."
                ),
            )


            return redirect(
                "customers:detail",
                pk=customer.pk,
            )


    else:

        form = CustomerForm()


    return render(
        request,
        "customers/customer_form.html",
        {
            "form": form,
            "business": business,

            "page_title":
            "Add Customer",

            "submit_label":
            "Create Customer",
        },
    )


# =========================================================
# UPDATE CUSTOMER
# =========================================================

@login_required
def customer_update(request, pk):
    business = get_current_business(
        request.user
    )

    customer = get_object_or_404(
        Customer,
        pk=pk,
        business=business,
    )


    if request.method == "POST":

        form = CustomerForm(
            request.POST,
            instance=customer,
        )

        if form.is_valid():

            customer = form.save(
                commit=False
            )

            customer.business = business

            customer.save()


            messages.success(
                request,
                (
                    f"{customer.full_name} "
                    "was updated successfully."
                ),
            )


            return redirect(
                "customers:detail",
                pk=customer.pk,
            )


    else:

        form = CustomerForm(
            instance=customer
        )


    return render(
        request,
        "customers/customer_form.html",
        {
            "form": form,
            "customer": customer,
            "business": business,

            "page_title":
            "Edit Customer",

            "submit_label":
            "Save Changes",
        },
    )


# =========================================================
# ARCHIVE CUSTOMER
# =========================================================

@login_required
@require_POST
def customer_archive(request, pk):
    business = get_current_business(
        request.user
    )

    customer = get_object_or_404(
        Customer,
        pk=pk,
        business=business,
    )


    customer.is_active = False

    customer.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )


    messages.success(
        request,
        (
            f"{customer.full_name} "
            "was archived."
        ),
    )


    return redirect(
        "customers:detail",
        pk=customer.pk,
    )


# =========================================================
# RESTORE CUSTOMER
# =========================================================

@login_required
@require_POST
def customer_restore(request, pk):
    business = get_current_business(
        request.user
    )

    customer = get_object_or_404(
        Customer,
        pk=pk,
        business=business,
    )


    customer.is_active = True

    customer.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )


    messages.success(
        request,
        (
            f"{customer.full_name} "
            "was restored."
        ),
    )


    return redirect(
        "customers:detail",
        pk=customer.pk,
    )