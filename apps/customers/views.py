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

from apps.businesses.permissions import (
    can_manage_business,
    management_required,
)


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

        customers = (
            customers.filter(
                is_active=True
            )
        )

    elif status == "inactive":

        customers = (
            customers.filter(
                is_active=False
            )
        )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if query:

        customers = (
            customers.filter(

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
        )

    # -----------------------------------------------------
    # PAGINATION
    # -----------------------------------------------------

    paginator = Paginator(
        customers,
        10,
    )

    page_number = (
        request.GET.get(
            "page"
        )
    )

    page_obj = (
        paginator.get_page(
            page_number
        )
    )

    # -----------------------------------------------------
    # PRESERVE SEARCH / FILTER QUERY
    # -----------------------------------------------------

    query_params = (
        request.GET.copy()
    )

    query_params.pop(
        "page",
        None,
    )

    filter_query = (
        query_params.urlencode()
    )

    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {
        "page_obj":
            page_obj,

        "customers":
            page_obj.object_list,

        "query":
            query,

        "status":
            status,

        "filter_query":
            filter_query,

        "business":
            business,
    }

    # -----------------------------------------------------
    # HTMX PARTIAL RESPONSE
    # -----------------------------------------------------

    if (
        request.headers.get(
            "HX-Request"
        )
        == "true"
    ):

        return render(
            request,
            (
                "customers/partials/"
                "customer_table.html"
            ),
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
def customer_detail(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    customer = get_object_or_404(
        Customer,
        pk=pk,
        business=business,
    )

    # =====================================================
    # CUSTOMER ORDERS
    # =====================================================

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
            "refunds",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    order_list = list(
        orders
    )

    # =====================================================
    # TOTAL ORDERS
    # =====================================================

    total_orders = len(
        order_list
    )

    # =====================================================
    # DELIVERED ORDERS
    # =====================================================

    delivered_orders = [
        order
        for order in order_list
        if (
            order.status
            == Order.STATUS_DELIVERED
        )
    ]

    delivered_orders_count = len(
        delivered_orders
    )

    # =====================================================
    # DELIVERED SALES
    #
    # Refund-aware completed sales.
    # =====================================================

    delivered_sales = sum(
        (
            max(
                (
                    order.total_amount
                    - order.refunded_amount
                ),
                0,
            )
            for order in delivered_orders
        ),
        0,
    )

    # Backwards-compatible context name.
    total_spent = delivered_sales

    # =====================================================
    # GROSS PAID
    # =====================================================

    gross_paid = sum(
        (
            order.paid_amount
            for order in order_list
        ),
        0,
    )

    # =====================================================
    # TOTAL REFUNDED
    # =====================================================

    total_refunded = sum(
        (
            order.refunded_amount
            for order in order_list
        ),
        0,
    )

    # =====================================================
    # NET PAID
    # =====================================================

    net_paid = sum(
        (
            order.net_paid_amount
            for order in order_list
        ),
        0,
    )

    # Backwards-compatible context name.
    total_paid = net_paid

    # =====================================================
    # OUTSTANDING DUE
    #
    # Cancelled and returned orders are excluded because
    # they are no longer collectible active receivables.
    # =====================================================

    active_receivable_orders = [
        order
        for order in order_list
        if order.status not in {
            Order.STATUS_CANCELLED,
            Order.STATUS_RETURNED,
        }
    ]

    total_due = sum(
        (
            order.due_amount
            for order
            in active_receivable_orders
        ),
        0,
    )

    # =====================================================
    # CUSTOMER INSIGHTS
    # =====================================================

    last_order = (
        order_list[0]
        if order_list
        else None
    )

    average_delivered_order_value = 0

    if delivered_orders_count:

        average_delivered_order_value = (
            delivered_sales
            / delivered_orders_count
        )

    is_repeat_customer = (
        total_orders > 1
    )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {
        "customer":
            customer,

        "business":
            business,

        "orders":
            order_list,

        "total_orders":
            total_orders,

        "delivered_orders_count":
            delivered_orders_count,

        "delivered_sales":
            delivered_sales,

        "total_spent":
            total_spent,

        "gross_paid":
            gross_paid,

        "total_refunded":
            total_refunded,

        "net_paid":
            net_paid,

        "total_paid":
            total_paid,

        "total_due":
            total_due,

        "last_order":
            last_order,

        "average_delivered_order_value":
            average_delivered_order_value,

        "is_repeat_customer":
            is_repeat_customer,

        "can_manage_customer":
            can_manage_business(
                request.user,
                business,
            ),
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
def customer_create(
    request,
):

    business = get_current_business(
        request.user
    )

    if request.method == "POST":

        form = CustomerForm(
            request.POST
        )

        if form.is_valid():

            customer = (
                form.save(
                    commit=False
                )
            )

            customer.business = (
                business
            )

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
            "form":
                form,

            "business":
                business,

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
def customer_update(
    request,
    pk,
):

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

            customer = (
                form.save(
                    commit=False
                )
            )

            customer.business = (
                business
            )

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
            "form":
                form,

            "customer":
                customer,

            "business":
                business,

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
@management_required
@require_POST
def customer_archive(
    request,
    pk,
):

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
@management_required
@require_POST
def customer_restore(
    request,
    pk,
):

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