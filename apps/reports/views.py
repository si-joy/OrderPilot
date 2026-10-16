from datetime import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import render

from apps.businesses.utils import get_current_business
from apps.orders.models import (
    CourierSettlement,
    Order,
    OrderItem,
)
from apps.products.models import Product
import csv

from django.http import HttpResponse
from apps.businesses.permissions import (
    can_manage_business,
    management_required,
)

# =========================================================
# REPORT DASHBOARD
# =========================================================

@login_required
def report_dashboard(request):

    business = get_current_business(
        request.user
    )

    # =====================================================
    # DATE FILTERS
    # =====================================================

    date_from = (
        request.GET
        .get(
            "date_from",
            "",
        )
        .strip()
    )

    date_to = (
        request.GET
        .get(
            "date_to",
            "",
        )
        .strip()
    )

    parsed_from = None
    parsed_to = None

    if date_from:

        try:

            parsed_from = datetime.strptime(
                date_from,
                "%Y-%m-%d",
            ).date()

        except ValueError:

            date_from = ""
            parsed_from = None

    if date_to:

        try:

            parsed_to = datetime.strptime(
                date_to,
                "%Y-%m-%d",
            ).date()

        except ValueError:

            date_to = ""
            parsed_to = None

    # =====================================================
    # BASE ORDER QUERY
    # =====================================================

    orders = (
        Order.objects
        .filter(
            business=business,
        )
        .select_related(
            "customer",
        )
        .order_by(
            "-created_at"
        )
    )

    # =====================================================
    # APPLY DATE RANGE
    # =====================================================

    if parsed_from:

        orders = orders.filter(
            created_at__date__gte=(
                parsed_from
            )
        )

    if parsed_to:

        orders = orders.filter(
            created_at__date__lte=(
                parsed_to
            )
        )

    # =====================================================
    # ORDER COUNTS
    # =====================================================

    total_orders = (
        orders.count()
    )

    delivered_orders = (
        orders.filter(
            status=(
                Order.STATUS_DELIVERED
            )
        )
    )

    returned_orders = (
        orders.filter(
            status=(
                Order.STATUS_RETURNED
            )
        )
    )

    cancelled_orders = (
        orders.filter(
            status=(
                Order.STATUS_CANCELLED
            )
        )
    )

    delivered_count = (
        delivered_orders.count()
    )

    returned_count = (
        returned_orders.count()
    )

    cancelled_count = (
        cancelled_orders.count()
    )

    # =====================================================
    # REFUND SUMMARY
    # =====================================================

    total_refunded = sum(
        (
            order.refunded_amount
            for order
            in orders
        ),
        Decimal(
            "0.00"
        ),
    )

    delivered_refunds = sum(
        (
            order.refunded_amount
            for order
            in delivered_orders
        ),
        Decimal(
            "0.00"
        ),
    )

    # =====================================================
    # TOTAL SALES
    #
    # Delivered order value - delivered refunds
    # =====================================================

    gross_delivered_sales = (
        delivered_orders
        .aggregate(
            total=Sum(
                "total_amount"
            )
        )
        .get(
            "total"
        )
        or Decimal(
            "0.00"
        )
    )

    total_sales = (
        gross_delivered_sales
        - delivered_refunds
    )

    if (
        total_sales
        < Decimal("0.00")
    ):
        total_sales = Decimal(
            "0.00"
        )

    # =====================================================
    # TOTAL COLLECTED
    #
    # Net cash retained:
    # Paid - Refunded
    # =====================================================

    total_collected = sum(
        (
            order.net_paid_amount
            for order
            in orders
        ),
        Decimal(
            "0.00"
        ),
    )

    # =====================================================
    # OUTSTANDING DUE
    #
    # Cancelled and returned orders excluded
    # =====================================================

    active_receivable_orders = (
        orders.exclude(
            status__in=[
                Order.STATUS_CANCELLED,
                Order.STATUS_RETURNED,
            ]
        )
    )

    outstanding_due = sum(
        (
            order.due_amount
            for order
            in active_receivable_orders
        ),
        Decimal(
            "0.00"
        ),
    )

    # =====================================================
    # DELIVERED ORDER IDS
    # =====================================================

    delivered_order_ids = list(
        delivered_orders
        .values_list(
            "id",
            flat=True,
        )
    )

    # =====================================================
    # DELIVERED ITEMS
    # =====================================================

    delivered_items = (
        OrderItem.objects
        .filter(
            order_id__in=(
                delivered_order_ids
            ),
        )
        .select_related(
            "product",
            "order",
        )
    )

    # =====================================================
    # ESTIMATED PROFIT
    #
    # Revenue - Cost - Refunds
    # =====================================================

    total_product_revenue = sum(
        (
            item.unit_price
            * item.quantity

            for item
            in delivered_items
        ),
        Decimal(
            "0.00"
        ),
    )

    total_product_cost = sum(
        (
            item.unit_cost
            * item.quantity

            for item
            in delivered_items
        ),
        Decimal(
            "0.00"
        ),
    )

    estimated_profit = (
        total_product_revenue
        - total_product_cost
        - delivered_refunds
    )

    # =====================================================
    # TOP SELLING PRODUCTS
    #
    # Product revenue stays gross because refunds are
    # currently stored at order level, not item level.
    # =====================================================

    revenue_expression = (
        ExpressionWrapper(
            F("unit_price")
            * F("quantity"),
            output_field=DecimalField(
                max_digits=14,
                decimal_places=2,
            ),
        )
    )

    top_products = (
        delivered_items
        .values(
            "product_id",
            "product_name",
            "sku",
        )
        .annotate(
            total_quantity=Sum(
                "quantity"
            ),
            total_revenue=Sum(
                revenue_expression
            ),
        )
        .order_by(
            "-total_quantity",
            "-total_revenue",
        )[:5]
    )

    # =====================================================
    # LOW STOCK PRODUCTS
    # =====================================================

    products = (
        Product.objects
        .filter(
            business=business,
            is_active=True,
        )
        .order_by(
            "stock_quantity",
            "name",
        )
    )

    low_stock_products = [
        product
        for product
        in products
        if product.is_low_stock
    ][:5]

    # =====================================================
    # RECENT DELIVERED ORDERS
    # =====================================================

    recent_delivered_orders = (
        delivered_orders
        .order_by(
            "-created_at"
        )[:5]
    )

    # =====================================================
    # COURIER + COD RECONCILIATION
    # =====================================================

    courier_settlements = (
        CourierSettlement.objects
        .filter(
            business=business,
        )
        .select_related(
            "order",
            "order__customer",
        )
    )

    # =====================================================
    # APPLY REPORT DATE FILTER TO COURIER DATA
    # =====================================================

    if parsed_from:

        courier_settlements = (
            courier_settlements
            .filter(
                order__created_at__date__gte=(
                    parsed_from
                )
            )
        )

    if parsed_to:

        courier_settlements = (
            courier_settlements
            .filter(
                order__created_at__date__lte=(
                    parsed_to
                )
            )
        )

    # =====================================================
    # COURIER OUTSTANDING PER ROW
    # =====================================================

    courier_settlements = (
        courier_settlements
        .annotate(
            outstanding=(
                ExpressionWrapper(
                    F(
                        "cod_expected"
                    )
                    - F(
                        "cod_received"
                    ),
                    output_field=(
                        DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        )
                    ),
                )
            )
        )
        .order_by(
            "-updated_at"
        )
    )

    # =====================================================
    # COURIER SUMMARY
    # =====================================================

    courier_summary = (
        courier_settlements
        .aggregate(

            total_expected=(
                Coalesce(
                    Sum(
                        "cod_expected"
                    ),
                    Value(
                        Decimal(
                            "0.00"
                        )
                    ),
                    output_field=(
                        DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        )
                    ),
                )
            ),

            total_received=(
                Coalesce(
                    Sum(
                        "cod_received"
                    ),
                    Value(
                        Decimal(
                            "0.00"
                        )
                    ),
                    output_field=(
                        DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        )
                    ),
                )
            ),

            courier_charges=(
                Coalesce(
                    Sum(
                        "courier_charge"
                    ),
                    Value(
                        Decimal(
                            "0.00"
                        )
                    ),
                    output_field=(
                        DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        )
                    ),
                )
            ),

            return_charges=(
                Coalesce(
                    Sum(
                        "return_charge"
                    ),
                    Value(
                        Decimal(
                            "0.00"
                        )
                    ),
                    output_field=(
                        DecimalField(
                            max_digits=14,
                            decimal_places=2,
                        )
                    ),
                )
            ),
        )
    )

    courier_total_expected = (
        courier_summary[
            "total_expected"
        ]
    )

    courier_total_received = (
        courier_summary[
            "total_received"
        ]
    )

    courier_charges = (
        courier_summary[
            "courier_charges"
        ]
    )

    courier_return_charges = (
        courier_summary[
            "return_charges"
        ]
    )

    # =====================================================
    # OUTSTANDING COD
    # =====================================================

    courier_outstanding = (
        courier_total_expected
        - courier_total_received
    )

    if (
        courier_outstanding
        < Decimal(
            "0.00"
        )
    ):

        courier_outstanding = (
            Decimal(
                "0.00"
            )
        )

    # =====================================================
    # NET COURIER RECEIVABLE
    # =====================================================

    courier_net_expected = (
        courier_total_expected
        - courier_charges
        - courier_return_charges
    )

    if (
        courier_net_expected
        < Decimal(
            "0.00"
        )
    ):

        courier_net_expected = (
            Decimal(
                "0.00"
            )
        )

    # =====================================================
    # NET COURIER OUTSTANDING
    # =====================================================

    courier_net_outstanding = (
        courier_net_expected
        - courier_total_received
    )

    if (
        courier_net_outstanding
        < Decimal(
            "0.00"
        )
    ):

        courier_net_outstanding = (
            Decimal(
                "0.00"
            )
        )

    # =====================================================
    # COURIER STATUS COUNTS
    # =====================================================

    courier_pending_count = (
        courier_settlements
        .filter(
            settlement_status=(
                CourierSettlement
                .STATUS_PENDING
            )
        )
        .count()
    )

    courier_partial_count = (
        courier_settlements
        .filter(
            settlement_status=(
                CourierSettlement
                .STATUS_PARTIAL
            )
        )
        .count()
    )

    courier_settled_count = (
        courier_settlements
        .filter(
            settlement_status=(
                CourierSettlement
                .STATUS_SETTLED
            )
        )
        .count()
    )

    courier_total_count = (
        courier_settlements
        .count()
    )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "business":
            business,

        "date_from":
            date_from,

        "date_to":
            date_to,

        "total_orders":
            total_orders,

        "delivered_count":
            delivered_count,

        "returned_count":
            returned_count,

        "cancelled_count":
            cancelled_count,

        "gross_delivered_sales":
            gross_delivered_sales,

        "total_sales":
            total_sales,

        "total_collected":
            total_collected,

        "total_refunded":
            total_refunded,

        "outstanding_due":
            outstanding_due,

        "estimated_profit":
            estimated_profit,

        "top_products":
            top_products,

        "low_stock_products":
            low_stock_products,

        "recent_delivered_orders":
            recent_delivered_orders,

        "courier_settlements":
            courier_settlements,

        "courier_total_expected":
            courier_total_expected,

        "courier_total_received":
            courier_total_received,

        "courier_outstanding":
            courier_outstanding,

        "courier_charges":
            courier_charges,

        "courier_return_charges":
            courier_return_charges,

        "courier_net_expected":
            courier_net_expected,

        "courier_net_outstanding":
            courier_net_outstanding,

        "courier_pending_count":
            courier_pending_count,

        "courier_partial_count":
            courier_partial_count,

        "courier_settled_count":
            courier_settled_count,

        "courier_total_count":
            courier_total_count,

        "can_export_reports":
            can_manage_business(
                request.user,
                business,
            ),
    }

    return render(
        request,
        "reports/report_dashboard.html",
        context,
    )


@login_required
@management_required
def report_export_csv(request):

    business = get_current_business(
        request.user
    )

    date_from = (
        request.GET
        .get(
            "date_from",
            "",
        )
        .strip()
    )

    date_to = (
        request.GET
        .get(
            "date_to",
            "",
        )
        .strip()
    )

    parsed_from = None
    parsed_to = None

    if date_from:

        try:
            parsed_from = datetime.strptime(
                date_from,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            parsed_from = None

    if date_to:

        try:
            parsed_to = datetime.strptime(
                date_to,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            parsed_to = None

    orders = (
        Order.objects
        .filter(
            business=business,
        )
        .select_related(
            "customer",
        )
        .order_by(
            "-created_at",
        )
    )

    if parsed_from:

        orders = orders.filter(
            created_at__date__gte=(
                parsed_from
            )
        )

    if parsed_to:

        orders = orders.filter(
            created_at__date__lte=(
                parsed_to
            )
        )

    response = HttpResponse(
        content_type=(
            "text/csv; charset=utf-8"
        )
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; '
        'filename="orderpilot-report.csv"'
    )

    response.write(
        "\ufeff"
    )

    writer = csv.writer(
        response
    )

    writer.writerow(
        [
            "Order Number",
            "Customer",
            "Phone",
            "Status",
            "Payment Status",
            "Total",
            "Gross Paid",
            "Refunded",
            "Net Paid",
            "Due",
            "Created Date",
        ]
    )

    for order in orders:

        writer.writerow(
            [
                order.order_number,
                order.customer.full_name,
                order.customer.phone,
                order.get_status_display(),
                order.get_payment_status_display(),
                order.total_amount,
                order.paid_amount,
                order.refunded_amount,
                order.net_paid_amount,
                order.due_amount,
                order.created_at.strftime(
                    "%Y-%m-%d %H:%M"
                ),
            ]
        )

    return response

    