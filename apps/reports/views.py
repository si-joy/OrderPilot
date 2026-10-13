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
    # TOTAL SALES
    #
    # Only delivered orders count as completed sales.
    # =====================================================

    total_sales = (
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


    # =====================================================
    # TOTAL COLLECTED
    # =====================================================

    total_collected = (
        orders
        .aggregate(
            total=Sum(
                "paid_amount"
            )
        )
        .get(
            "total"
        )
        or Decimal(
            "0.00"
        )
    )


    # =====================================================
    # OUTSTANDING DUE
    #
    # Cancelled and returned orders are excluded.
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
    # Revenue:
    # unit_price * quantity
    #
    # Cost:
    # unit_cost * quantity
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
    )


    # =====================================================
    # TOP SELLING PRODUCTS
    #
    # line_total is a Python property,
    # not a database field.
    #
    # Revenue is calculated using:
    # unit_price * quantity
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
    # APPLY SAME REPORT DATE RANGE TO COURIER DATA
    #
    # The date range is based on the related order date.
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
    #
    # Outstanding =
    # COD Expected - COD Received
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
    #
    # Gross COD Expected
    # - Courier Charge
    # - Return Charge
    #
    # This is informational only.
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
    #
    # Net Expected - Received
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

        # -------------------------------------------------
        # BUSINESS
        # -------------------------------------------------

        "business":
            business,


        # -------------------------------------------------
        # FILTERS
        # -------------------------------------------------

        "date_from":
            date_from,

        "date_to":
            date_to,


        # -------------------------------------------------
        # ORDER COUNTS
        # -------------------------------------------------

        "total_orders":
            total_orders,

        "delivered_count":
            delivered_count,

        "returned_count":
            returned_count,

        "cancelled_count":
            cancelled_count,


        # -------------------------------------------------
        # FINANCIAL SUMMARY
        # -------------------------------------------------

        "total_sales":
            total_sales,

        "total_collected":
            total_collected,

        "outstanding_due":
            outstanding_due,

        "estimated_profit":
            estimated_profit,


        # -------------------------------------------------
        # PRODUCT REPORTS
        # -------------------------------------------------

        "top_products":
            top_products,

        "low_stock_products":
            low_stock_products,


        # -------------------------------------------------
        # ORDER REPORTS
        # -------------------------------------------------

        "recent_delivered_orders":
            recent_delivered_orders,


        # -------------------------------------------------
        # COURIER + COD
        # -------------------------------------------------

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
    }


    return render(
        request,
        "reports/report_dashboard.html",
        context,
    )