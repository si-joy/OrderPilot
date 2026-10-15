from django.utils import timezone

from collections import defaultdict

from decimal import Decimal

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.db import transaction

from django.shortcuts import (

    get_object_or_404,

    redirect,

    render,

)

from django.views.decorators.http import require_POST

from apps.businesses.utils import get_current_business

from apps.products.models import (
    Product,
    StockAdjustment,
)
from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from .forms import (

    CourierSettlementForm,

    OrderForm,

    OrderItemFormSet,

    OrderPaymentForm,

    OrderRefundForm,

)

from .models import (
    CourierSettlement,
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
    OrderStatusHistory,
)

from django.core.paginator import Paginator
from django.db.models import Q


from django.http import HttpResponse

from io import BytesIO

from reportlab.lib import colors

from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from reportlab.lib.pagesizes import A4

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from reportlab.lib.units import mm

from reportlab.platypus import (

    Image,

    Paragraph,

    SimpleDocTemplate,

    Spacer,

    Table,

    TableStyle,

)

# =========================================================

# ORDER STATUS TRANSITION RULES

# =========================================================

ALLOWED_STATUS_TRANSITIONS = {

    Order.STATUS_PENDING: {

        Order.STATUS_CONFIRMED,

        Order.STATUS_CANCELLED,

    },

    Order.STATUS_CONFIRMED: {

        Order.STATUS_PROCESSING,

        Order.STATUS_CANCELLED,

    },

    Order.STATUS_PROCESSING: {

        Order.STATUS_SHIPPED,

        Order.STATUS_CANCELLED,

    },

    Order.STATUS_SHIPPED: {

        Order.STATUS_DELIVERED,

        Order.STATUS_RETURNED,

    },

    Order.STATUS_DELIVERED: {

        Order.STATUS_RETURNED,

    },

    Order.STATUS_RETURNED: set(),

    Order.STATUS_CANCELLED: {

        Order.STATUS_CONFIRMED,

    },

}

# =========================================================

# INVENTORY-COMMITTED STATUSES

# =========================================================

INVENTORY_COMMITTED_STATUSES = {

    Order.STATUS_CONFIRMED,

    Order.STATUS_PROCESSING,

    Order.STATUS_SHIPPED,

    Order.STATUS_DELIVERED,

}

class InsufficientStockError(Exception):

    pass

# =========================================================

# PAYMENT STATUS

# =========================================================

def calculate_payment_status(order):

    paid_amount = (

        order.paid_amount

        or Decimal("0.00")

    )

    refunded_amount = (

        order.refunded_amount

        or Decimal("0.00")

    )

    total_amount = (

        order.total_amount

        or Decimal("0.00")

    )

    net_paid_amount = (

        paid_amount

        - refunded_amount

    )

    if (

        net_paid_amount

        < Decimal("0.00")

    ):

        net_paid_amount = Decimal(

            "0.00"

        )

    if (

        refunded_amount

        > Decimal("0.00")

        and paid_amount

        > Decimal("0.00")

        and net_paid_amount

        <= Decimal("0.00")

    ):

        return Order.PAYMENT_REFUNDED

    if (

        net_paid_amount

        <= Decimal("0.00")

    ):

        return Order.PAYMENT_UNPAID

    if (

        net_paid_amount

        < total_amount

    ):

        return Order.PAYMENT_PARTIAL

    return Order.PAYMENT_PAID

# =========================================================

# ORDER PRODUCT QUANTITIES

# =========================================================

def get_order_product_quantities(order):

    quantities = defaultdict(
        int
    )

    items = (
        OrderItem.objects
        .filter(
            order=order
        )
        .only(
            "product_id",
            "quantity",
        )
    )

    for item in items:

        quantities[
            item.product_id
        ] += item.quantity

    return quantities

# =========================================================

# DEDUCT STOCK

# =========================================================

def deduct_order_stock(
    order,
    adjusted_by=None,
):

    if order.stock_deducted:
        return

    quantities = (
        get_order_product_quantities(
            order
        )
    )

    if not quantities:

        raise InsufficientStockError(
            "This order does not contain any products."
        )

    product_ids = list(
        quantities.keys()
    )

    products = (
        Product.objects
        .select_for_update()
        .filter(
            business=order.business,
            id__in=product_ids,
        )
    )

    product_map = {
        product.id: product
        for product in products
    }

    # =====================================================
    # VALIDATE ALL PRODUCTS FIRST
    # =====================================================

    for product_id, required in (
        quantities.items()
    ):

        product = product_map.get(
            product_id
        )

        if product is None:

            raise InsufficientStockError(
                (
                    "One or more products are "
                    "no longer available."
                )
            )

        if (
            product.stock_quantity
            < required
        ):

            raise InsufficientStockError(
                (
                    f"Not enough stock for "
                    f"{product.name}. "
                    f"Available: "
                    f"{product.stock_quantity}, "
                    f"required: {required}."
                )
            )

    # =====================================================
    # DEDUCT + AUDIT
    # =====================================================

    for product_id, required in (
        quantities.items()
    ):

        product = product_map[
            product_id
        ]

        before_quantity = (
            product.stock_quantity
        )

        after_quantity = (
            before_quantity
            - required
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
            business=order.business,
            product=product,
            order=order,
            adjustment_type=(
                StockAdjustment
                .TYPE_ORDER_DEDUCT
            ),
            quantity=required,
            before_quantity=(
                before_quantity
            ),
            after_quantity=(
                after_quantity
            ),
            note=(
                f"Stock deducted for "
                f"{order.order_number}."
            ),
            adjusted_by=adjusted_by,
        )

    order.stock_deducted = True

    order.save(
        update_fields=[
            "stock_deducted",
            "updated_at",
        ]
    )


# =========================================================

# RESTORE STOCK

# =========================================================

def restore_order_stock(
    order,
    adjusted_by=None,
):

    if not order.stock_deducted:
        return

    quantities = (
        get_order_product_quantities(
            order
        )
    )

    product_ids = list(
        quantities.keys()
    )

    products = (
        Product.objects
        .select_for_update()
        .filter(
            business=order.business,
            id__in=product_ids,
        )
    )

    product_map = {
        product.id: product
        for product in products
    }

    # =====================================================
    # RESTORE + AUDIT
    # =====================================================

    for product_id, quantity in (
        quantities.items()
    ):

        product = product_map.get(
            product_id
        )

        if product is None:
            continue

        before_quantity = (
            product.stock_quantity
        )

        after_quantity = (
            before_quantity
            + quantity
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
            business=order.business,
            product=product,
            order=order,
            adjustment_type=(
                StockAdjustment
                .TYPE_ORDER_RESTORE
            ),
            quantity=quantity,
            before_quantity=(
                before_quantity
            ),
            after_quantity=(
                after_quantity
            ),
            note=(
                f"Stock restored for "
                f"{order.order_number}."
            ),
            adjusted_by=adjusted_by,
        )

    order.stock_deducted = False

    order.save(
        update_fields=[
            "stock_deducted",
            "updated_at",
        ]
    )

# =========================================================

# SYNC INVENTORY

# =========================================================

def sync_order_inventory(
    order,
    adjusted_by=None,
):

    should_be_deducted = (
        order.status
        in INVENTORY_COMMITTED_STATUSES
    )

    if (
        should_be_deducted
        and not order.stock_deducted
    ):

        deduct_order_stock(
            order,
            adjusted_by=adjusted_by,
        )

    elif (
        not should_be_deducted
        and order.stock_deducted
    ):

        restore_order_stock(
            order,
            adjusted_by=adjusted_by,
        )

# =========================================================

# ORDER LIST

# =========================================================

@login_required
def order_list(request):

    business = get_current_business(
        request.user
    )

    # =====================================================
    # FILTER VALUES
    # =====================================================

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
            "",
        )
        .strip()
    )

    payment_status = (
        request.GET
        .get(
            "payment_status",
            "",
        )
        .strip()
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

    # =====================================================
    # BASE QUERYSET
    # =====================================================

    orders = (
        Order.objects
        .filter(
            business=business,
        )
        .select_related(
            "customer",
        )
        .prefetch_related(
            "items",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    if query:

        orders = orders.filter(

            Q(
                order_number__icontains=query
            )

            | Q(
                customer__full_name__icontains=query
            )

            | Q(
                customer__phone__icontains=query
            )

            | Q(
                tracking_number__icontains=query
            )

            | Q(
                courier_name__icontains=query
            )

        )

    # =====================================================
    # ORDER STATUS
    # =====================================================

    valid_statuses = {
        value
        for value, label
        in Order.STATUS_CHOICES
    }

    if (
        status
        and status in valid_statuses
    ):

        orders = orders.filter(
            status=status
        )

    # =====================================================
    # PAYMENT STATUS
    # =====================================================

    valid_payment_statuses = {
        value
        for value, label
        in Order.PAYMENT_STATUS_CHOICES
    }

    if (
        payment_status
        and payment_status
        in valid_payment_statuses
    ):

        orders = orders.filter(
            payment_status=payment_status
        )

    # =====================================================
    # DATE RANGE
    # =====================================================

    if date_from:

        orders = orders.filter(
            created_at__date__gte=date_from
        )

    if date_to:

        orders = orders.filter(
            created_at__date__lte=date_to
        )

    # =====================================================
    # PAGINATION
    # =====================================================

    paginator = Paginator(
        orders,
        15,
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

    # =====================================================
    # PRESERVE FILTER QUERY STRING
    # =====================================================

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

    context = {
        "orders":
            page_obj.object_list,

        "page_obj":
            page_obj,

        "query":
            query,

        "status":
            status,

        "payment_status":
            payment_status,

        "date_from":
            date_from,

        "date_to":
            date_to,

        "status_choices":
            Order.STATUS_CHOICES,

        "payment_status_choices":
            Order.PAYMENT_STATUS_CHOICES,

        "filter_query":
            filter_query,

        "business":
            business,
    }

    return render(
        request,
        "orders/order_list.html",
        context,
    )

# =========================================================

# ORDER DETAIL

# =========================================================

@login_required

def order_detail(request, pk):

    business = get_current_business(

        request.user

    )

    order = get_object_or_404(

        Order.objects

        .select_related(

            "customer",

            "created_by",

        )

        .prefetch_related(

            "items",

            "status_history",

            "payments",

            "refunds",

        ),

        pk=pk,

        business=business,

    )

    allowed_statuses = (

        ALLOWED_STATUS_TRANSITIONS.get(

            order.status,

            set(),

        )

    )

    status_choices = [

        (value, label)

        for value, label

        in Order.STATUS_CHOICES

        if value in allowed_statuses

    ]

    payment_form = OrderPaymentForm(

        order=order,

        initial={

            "payment_method":

            order.payment_method,

        },

    )


    refund_form = OrderRefundForm(

        order=order,

        initial={

            "refund_method":

            order.payment_method,

        },

    )

    # =====================================================

    # COURIER SETTLEMENT

    # =====================================================

    try:

        courier_settlement = (

            order.courier_settlement

        )

    except CourierSettlement.DoesNotExist:

        courier_settlement = None

    courier_form = CourierSettlementForm(

        order=order,

        instance=courier_settlement,

    )

    return render(

        request,

        "orders/order_detail.html",

        {

            "order": order,

            "business": business,

            "status_choices":

            status_choices,

            "payment_form":

            payment_form,

            "refund_form":

            refund_form,

            "courier_settlement":

            courier_settlement,

            "courier_form":

            courier_form,

        },

    )

# =========================================================

# CREATE ORDER

# =========================================================

@login_required

def order_create(request):

    business = get_current_business(

        request.user

    )

    order = Order(

        business=business,

        created_by=request.user,

    )

    if request.method == "POST":

        form = OrderForm(

            request.POST,

            instance=order,

            business=business,

        )

        formset = OrderItemFormSet(

            request.POST,

            instance=order,

            form_kwargs={

                "business": business,

            },

        )

        if (

            form.is_valid()

            and formset.is_valid()

        ):

            try:

                with transaction.atomic():

                    order = form.save(

                        commit=False

                    )

                    order.business = business

                    order.created_by = request.user

                    order.subtotal = Decimal(

                        "0.00"

                    )

                    order.total_amount = Decimal(

                        "0.00"

                    )

                    order.save()

                    subtotal = Decimal(

                        "0.00"

                    )

                    items = formset.save(

                        commit=False

                    )

                    valid_items = []

                    for item in items:

                        product = item.product

                        if (

                            product.business_id

                            != business.id

                        ):

                            raise ValueError(

                                "Invalid product selected."

                            )

                        item.order = order

                        item.product_name = (

                            product.name

                        )

                        item.sku = (

                            product.sku

                        )

                        item.unit_price = (

                            product.selling_price

                        )

                        item.unit_cost = (

                            product.cost_price

                        )

                        subtotal += (

                            item.unit_price

                            * item.quantity

                        )

                        valid_items.append(

                            item

                        )

                    if not valid_items:

                        raise ValueError(

                            (

                                "Please add at least "

                                "one valid product."

                            )

                        )

                    discount = (

                        order.discount

                        or Decimal("0.00")

                    )

                    delivery_charge = (

                        order.delivery_charge

                        or Decimal("0.00")

                    )

                    total = (

                        subtotal

                        - discount

                        + delivery_charge

                    )

                    if (

                        total

                        < Decimal("0.00")

                    ):

                        total = Decimal(

                            "0.00"

                        )

                    order.subtotal = subtotal

                    order.total_amount = total

                    if (

                        order.paid_amount

                        > order.total_amount

                    ):

                        raise ValueError(

                            (

                                "Paid amount cannot exceed "

                                "the order total."

                            )

                        )

                    order.payment_status = (

                        calculate_payment_status(

                            order

                        )

                    )

                    order.save(

                        update_fields=[

                            "subtotal",

                            "total_amount",

                            "payment_status",

                            "updated_at",

                        ]

                    )

                    for item in valid_items:

                        item.save()

                    sync_order_inventory(
                        order,
                        adjusted_by=request.user,
                    )

                    # Initial payment history

                    if (

                        order.paid_amount

                        > Decimal("0.00")

                    ):

                        OrderPayment.objects.create(

                            order=order,

                            business=business,

                            amount=order.paid_amount,

                            payment_method=(

                                order.payment_method

                            ),

                            note="Initial payment.",

                            received_by=request.user,

                        )

                    OrderStatusHistory.objects.create(

                        order=order,

                        from_status="",

                        to_status=order.status,

                        changed_by=request.user,

                        note="Order created.",

                    )


                    # =============================================
                    # NEW ORDER NOTIFICATION
                    # =============================================

                    create_notification(
                        business=business,
                        title="New order created",
                        message=(
                            f"{order.order_number} "
                            f"was created for "
                            f"{order.customer.full_name}."
                        ),
                        notification_type=(
                            Notification.TYPE_INFO
                        ),
                        url=(
                            f"/orders/{order.pk}/"
                        ),
                        event_key=(
                            f"order-created-{order.pk}"
                        ),
                    )

            except (

                InsufficientStockError,

                ValueError,

            ) as error:

                form.add_error(

                    None,

                    str(error),

                )

            else:

                messages.success(

                    request,

                    (

                        f"{order.order_number} "

                        "was created successfully."

                    ),

                )

                return redirect(

                    "orders:detail",

                    pk=order.pk,

                )

    else:

        form = OrderForm(

            instance=order,

            business=business,

        )

        formset = OrderItemFormSet(

            instance=order,

            form_kwargs={

                "business": business,

            },

        )

    return render(

        request,

        "orders/order_form.html",

        {

            "form": form,

            "formset": formset,

            "business": business,

            "page_title": "Create Order",

        },

    )


# =========================================================
# EDIT ORDER
# =========================================================

@login_required
def order_edit(
    request,
    pk,
):

    business = get_current_business(
        request.user
    )

    # =====================================================
    # LOAD ORDER
    # =====================================================

    order = get_object_or_404(
        Order.objects
        .select_related(
            "customer",
        )
        .prefetch_related(
            "items",
        ),
        pk=pk,
        business=business,
    )

    # =====================================================
    # EDIT RULES
    # =====================================================

    editable_order_statuses = {
        Order.STATUS_PENDING,
        Order.STATUS_CONFIRMED,
        Order.STATUS_PROCESSING,
    }

    financial_editable = (
        order.status
        in editable_order_statuses
    )

    can_edit_items = (
        order.status
        in editable_order_statuses
    )

    form = None
    formset = None

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        try:

            with transaction.atomic():

                # -------------------------------------------------
                # Lock order against concurrent edits / payments /
                # refunds / status transitions.
                # -------------------------------------------------

                order = get_object_or_404(
                    Order.objects
                    .select_for_update()
                    .select_related(
                        "customer",
                    )
                    .prefetch_related(
                        "items",
                    ),
                    pk=pk,
                    business=business,
                )

                financial_editable = (
                    order.status
                    in editable_order_statuses
                )

                can_edit_items = (
                    order.status
                    in editable_order_statuses
                )

                form = OrderForm(
                    request.POST,
                    instance=order,
                    business=business,
                    edit_mode=True,
                    financial_editable=(
                        financial_editable
                    ),
                )

                if can_edit_items:

                    formset = OrderItemFormSet(
                        request.POST,
                        instance=order,
                        form_kwargs={
                            "business":
                                business,
                        },
                    )

                form_valid = (
                    form.is_valid()
                )

                formset_valid = True

                if can_edit_items:

                    formset_valid = (
                        formset.is_valid()
                    )

                if (
                    form_valid
                    and formset_valid
                ):

                    # =================================================
                    # SAFE OPERATIONAL FIELDS
                    # =================================================

                    order.courier_name = (
                        form.cleaned_data[
                            "courier_name"
                        ]
                    )

                    order.tracking_number = (
                        form.cleaned_data[
                            "tracking_number"
                        ]
                    )

                    order.delivery_address = (
                        form.cleaned_data[
                            "delivery_address"
                        ]
                    )

                    order.notes = (
                        form.cleaned_data[
                            "notes"
                        ]
                    )

                    # =================================================
                    # FINANCIAL + PRODUCT CORRECTIONS
                    # =================================================

                    if financial_editable:

                        order.customer = (
                            form.cleaned_data[
                                "customer"
                            ]
                        )

                        order.payment_method = (
                            form.cleaned_data[
                                "payment_method"
                            ]
                        )

                        order.discount = (
                            form.cleaned_data[
                                "discount"
                            ]
                            or Decimal(
                                "0.00"
                            )
                        )

                        order.delivery_charge = (
                            form.cleaned_data[
                                "delivery_charge"
                            ]
                            or Decimal(
                                "0.00"
                            )
                        )

                        # ---------------------------------------------
                        # Keep original item snapshots so quantity-only
                        # changes do not silently adopt today's product
                        # price/cost.
                        # ---------------------------------------------

                        existing_items = {
                            item.pk: item
                            for item
                            in order.items.all()
                        }

                        # ---------------------------------------------
                        # If stock was already committed, restore the
                        # OLD quantities before changing items.
                        # Everything is inside one transaction, so any
                        # later failure rolls this restoration back.
                        # ---------------------------------------------

                        if order.stock_deducted:

                            restore_order_stock(
                                order,
                                adjusted_by=request.user,
                            )

                        # ---------------------------------------------
                        # Save changed / new / deleted items.
                        # ---------------------------------------------

                        changed_items = (
                            formset.save(
                                commit=False
                            )
                        )

                        for deleted_item in (
                            formset.deleted_objects
                        ):

                            deleted_item.delete()

                        for item in changed_items:

                            product = (
                                item.product
                            )

                            if (
                                product.business_id
                                != business.id
                            ):

                                raise ValueError(
                                    (
                                        "Invalid product "
                                        "selected."
                                    )
                                )

                            old_item = (
                                existing_items.get(
                                    item.pk
                                )
                            )

                            # New item or changed product:
                            # take a fresh snapshot.
                            if (
                                old_item is None
                                or old_item.product_id
                                != product.id
                            ):

                                item.product_name = (
                                    product.name
                                )

                                item.sku = (
                                    product.sku
                                )

                                item.unit_price = (
                                    product.selling_price
                                )

                                item.unit_cost = (
                                    product.cost_price
                                )

                            # Existing same product:
                            # quantity may change, but historical
                            # price/cost snapshot stays untouched.

                            item.order = order

                            item.save()

                        # ---------------------------------------------
                        # Recalculate using the final item set.
                        # ---------------------------------------------

                        final_items = list(
                            OrderItem.objects.filter(
                                order=order
                            ).select_related(
                                "product"
                            )
                        )

                        if not final_items:

                            raise ValueError(
                                (
                                    "Please add at least "
                                    "one valid product."
                                )
                            )

                        subtotal = sum(
                            (
                                item.unit_price
                                * item.quantity
                                for item
                                in final_items
                            ),
                            Decimal(
                                "0.00"
                            ),
                        )

                        total = (
                            subtotal
                            - order.discount
                            + order.delivery_charge
                        )

                        if (
                            total
                            < Decimal("0.00")
                        ):

                            total = Decimal(
                                "0.00"
                            )

                        # ---------------------------------------------
                        # Financial history protection.
                        #
                        # Existing net collected money or refund history
                        # must never become impossible because an order
                        # total was edited downward.
                        # ---------------------------------------------

                        if (
                            total
                            < order.net_paid_amount
                        ):

                            raise ValueError(
                                (
                                    "Order total cannot be "
                                    "lower than the current "
                                    "net paid amount of "
                                    f"৳{order.net_paid_amount}."
                                )
                            )

                        if (
                            total
                            < order.refunded_amount
                        ):

                            raise ValueError(
                                (
                                    "Order total cannot be "
                                    "lower than the already "
                                    "refunded amount of "
                                    f"৳{order.refunded_amount}."
                                )
                            )

                        order.subtotal = (
                            subtotal
                        )

                        order.total_amount = (
                            total
                        )

                        order.payment_status = (
                            calculate_payment_status(
                                order
                            )
                        )

                    # =================================================
                    # SAVE ORDER
                    # =================================================

                    update_fields = [
                        "courier_name",
                        "tracking_number",
                        "delivery_address",
                        "notes",
                        "updated_at",
                    ]

                    if financial_editable:

                        update_fields.extend(
                            [
                                "customer",
                                "payment_method",
                                "discount",
                                "delivery_charge",
                                "subtotal",
                                "total_amount",
                                "payment_status",
                            ]
                        )

                    order.save(
                        update_fields=(
                            update_fields
                        )
                    )

                    # =================================================
                    # RE-COMMIT INVENTORY
                    # =================================================

                    if can_edit_items:

                        # Clear stale prefetched order items after
                        # formset updates/deletes so inventory sync
                        # always reads the latest database state.
                        if hasattr(
                            order,
                            "_prefetched_objects_cache",
                        ):
                            order._prefetched_objects_cache.pop(
                                "items",
                                None,
                            )

                        sync_order_inventory(
                            order,
                            adjusted_by=request.user,
                        )

                else:

                    # Normal form validation errors.
                    # No DB mutation has happened.
                    pass

        except (
            InsufficientStockError,
            ValueError,
        ) as error:

            if form is None:

                order = get_object_or_404(
                    Order,
                    pk=pk,
                    business=business,
                )

                financial_editable = (
                    order.status
                    in editable_order_statuses
                )

                can_edit_items = (
                    order.status
                    in editable_order_statuses
                )

                form = OrderForm(
                    request.POST,
                    instance=order,
                    business=business,
                    edit_mode=True,
                    financial_editable=(
                        financial_editable
                    ),
                )

                if can_edit_items:

                    formset = (
                        OrderItemFormSet(
                            request.POST,
                            instance=order,
                            form_kwargs={
                                "business":
                                    business,
                            },
                        )
                    )

            form.add_error(
                None,
                str(error),
            )

        else:

            if (
                form is not None
                and form.is_valid()
                and (
                    not can_edit_items
                    or (
                        formset is not None
                        and formset.is_valid()
                    )
                )
            ):

                messages.success(
                    request,
                    (
                        f"{order.order_number} "
                        "was updated successfully."
                    ),
                )

                return redirect(
                    "orders:detail",
                    pk=order.pk,
                )

    # =====================================================
    # GET
    # =====================================================

    else:

        form = OrderForm(
            instance=order,
            business=business,
            edit_mode=True,
            financial_editable=(
                financial_editable
            ),
        )

        if can_edit_items:

            formset = OrderItemFormSet(
                instance=order,
                form_kwargs={
                    "business":
                        business,
                },
            )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "orders/order_form.html",
        {
            "form":
                form,

            "formset":
                formset,

            "business":
                business,

            "order":
                order,

            "page_title":
                f"Edit {order.order_number}",

            "is_edit":
                True,

            "can_edit_items":
                can_edit_items,

            "financial_editable":
                financial_editable,
        },
    )


# =========================================================

# UPDATE ORDER STATUS

# =========================================================

@login_required

@require_POST

def order_status_update(

    request,

    pk,

):

    business = get_current_business(

        request.user

    )

    try:

        with transaction.atomic():

            order = get_object_or_404(

                Order.objects

                .select_for_update()

                .prefetch_related(

                    "items",

                ),

                pk=pk,

                business=business,

            )

            new_status = (

                request.POST

                .get(

                    "status",

                    "",

                )

                .strip()

            )

            note = (

                request.POST

                .get(

                    "note",

                    "",

                )

                .strip()

            )

            valid_statuses = {

                value

                for value, label

                in Order.STATUS_CHOICES

            }

            if (

                new_status

                not in valid_statuses

            ):

                messages.error(

                    request,

                    "Invalid order status.",

                )

                return redirect(

                    "orders:detail",

                    pk=order.pk,

                )

            current_status = (

                order.status

            )

            if (

                new_status

                == current_status

            ):

                messages.info(

                    request,

                    (

                        "Order is already "

                        "in this status."

                    ),

                )

                return redirect(

                    "orders:detail",

                    pk=order.pk,

                )

            allowed_statuses = (

                ALLOWED_STATUS_TRANSITIONS.get(

                    current_status,

                    set(),

                )

            )

            if (

                new_status

                not in allowed_statuses

            ):

                status_labels = dict(

                    Order.STATUS_CHOICES

                )

                messages.error(

                    request,

                    (

                        "Cannot change order status "

                        f"from "

                        f"{order.get_status_display()} "

                        "to "

                        f"{status_labels.get(new_status)}."

                    ),

                )

                return redirect(

                    "orders:detail",

                    pk=order.pk,

                )

            order.status = new_status

            order.save(

                update_fields=[

                    "status",

                    "updated_at",

                ]

            )

            sync_order_inventory(
                order,
                adjusted_by=request.user,
            )

            OrderStatusHistory.objects.create(

                order=order,

                from_status=current_status,

                to_status=new_status,

                changed_by=request.user,

                note=note,

            )


            # =============================================
            # ORDER STATUS NOTIFICATIONS
            # =============================================

            if (
                new_status
                == Order.STATUS_DELIVERED
            ):

                create_notification(
                    business=business,
                    title="Order delivered",
                    message=(
                        f"{order.order_number} "
                        "was marked as delivered."
                    ),
                    notification_type=(
                        Notification.TYPE_SUCCESS
                    ),
                    url=(
                        f"/orders/{order.pk}/"
                    ),
                    event_key=(
                        f"order-delivered-{order.pk}"
                    ),
                )

                if (
                    order.due_amount
                    > Decimal("0.00")
                ):

                    create_notification(
                        business=business,
                        title="Payment still due",
                        message=(
                            f"{order.order_number} "
                            f"has ৳{order.due_amount} "
                            "outstanding."
                        ),
                        notification_type=(
                            Notification.TYPE_WARNING
                        ),
                        url=(
                            f"/orders/{order.pk}/"
                        ),
                        event_key=(
                            f"order-due-{order.pk}"
                        ),
                    )

    except InsufficientStockError as error:

        messages.error(

            request,

            str(error),

        )

        return redirect(

            "orders:detail",

            pk=pk,

        )

    messages.success(

        request,

        (

            f"{order.order_number} "

            "status updated to "

            f"{order.get_status_display()}."

        ),

    )

    return redirect(

        "orders:detail",

        pk=order.pk,

    )

@login_required

def order_invoice(request, pk):

    business = get_current_business(

        request.user

    )

    order = get_object_or_404(

        Order.objects

        .select_related(

            "business",

            "customer",

            "created_by",

        )

        .prefetch_related(

            "items",

            "payments",

        ),

        pk=pk,

        business=business,

    )

    return render(

        request,

        "orders/order_invoice.html",

        {

            "order": order,

            "business": business,

        },

    )

# =========================================================
# REPORTLAB CONTAINED LOGO
# =========================================================

def build_contained_logo(
    image_file,
    max_width=18 * mm,
    max_height=18 * mm,
):
    """
    Create a ReportLab image that behaves like CSS object-fit: contain.

    This version works with both:
    - local Django FileSystemStorage
    - remote Django storage backends such as Cloudinary

    It reads the image through Django's storage API instead of using
    FieldFile.path, which may not exist for remote storage.
    """

    if not image_file:
        raise ValueError("Logo image is missing.")

    image_file.open("rb")

    try:
        image_bytes = image_file.read()
    finally:
        image_file.close()

    if not image_bytes:
        raise ValueError("Logo image is empty.")

    image_buffer = BytesIO(
        image_bytes
    )

    logo = Image(
        image_buffer
    )

    image_width = float(
        logo.imageWidth or 0
    )

    image_height = float(
        logo.imageHeight or 0
    )

    if (
        image_width <= 0
        or image_height <= 0
    ):
        logo.drawWidth = max_width
        logo.drawHeight = max_height
        return logo

    scale_ratio = min(
        max_width / image_width,
        max_height / image_height,
    )

    logo.drawWidth = (
        image_width
        * scale_ratio
    )

    logo.drawHeight = (
        image_height
        * scale_ratio
    )

    return logo


@login_required

def order_invoice_pdf(request, pk):

    business = get_current_business(

        request.user

    )

    order = get_object_or_404(

        Order.objects

        .select_related(

            "business",

            "customer",

            "created_by",

        )

        .prefetch_related(

            "items",

            "payments",

        ),

        pk=pk,

        business=business,

    )

    buffer = BytesIO()

    document = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=15 * mm,

        leftMargin=15 * mm,

        topMargin=15 * mm,

        bottomMargin=15 * mm,

    )

    styles = getSampleStyleSheet()

    styles.add(

        ParagraphStyle(

            name="InvoiceTitle",

            parent=styles["Heading1"],

            fontSize=22,

            leading=26,

            alignment=TA_RIGHT,

            spaceAfter=4,

        )

    )

    styles.add(

        ParagraphStyle(

            name="BusinessName",

            parent=styles["Heading2"],

            fontSize=16,

            leading=20,

            spaceAfter=4,

        )

    )

    styles.add(

        ParagraphStyle(

            name="SectionLabel",

            parent=styles["Normal"],

            fontSize=8,

            textColor=colors.HexColor("#8B95A5"),

            spaceAfter=5,

        )

    )

    styles.add(

        ParagraphStyle(

            name="SmallText",

            parent=styles["Normal"],

            fontSize=9,

            leading=13,

            textColor=colors.HexColor("#5F6875"),

        )

    )

    styles.add(

        ParagraphStyle(

            name="SmallBold",

            parent=styles["Normal"],

            fontSize=9,

            leading=13,

            fontName="Helvetica-Bold",

        )

    )

    styles.add(

        ParagraphStyle(

            name="RightSmall",

            parent=styles["Normal"],

            fontSize=9,

            leading=13,

            alignment=TA_RIGHT,

        )

    )

    styles.add(

        ParagraphStyle(

            name="RightBold",

            parent=styles["Normal"],

            fontSize=9,

            leading=13,

            fontName="Helvetica-Bold",

            alignment=TA_RIGHT,

        )

    )

    styles.add(

        ParagraphStyle(

            name="FooterNote",

            parent=styles["Normal"],

            fontSize=8,

            leading=12,

            alignment=TA_CENTER,

            textColor=colors.HexColor("#6B7280"),

        )

    )

    story = []

    # =====================================================

    # HEADER

    # =====================================================

    business_left = []

    if business.logo:

        try:

            logo = build_contained_logo(
                business.logo,
            )

            business_left.append(

                [

                    logo,

                    Paragraph(

                        f"<b>{business.name}</b><br/>"

                        f"{business.address or ''}<br/>"

                        f"{business.phone or ''}"

                        f"{' · ' if business.phone and business.email else ''}"

                        f"{business.email or ''}",

                        styles["SmallText"],

                    ),

                ]

            )

        except Exception:

            business_left.append(

                [

                    Paragraph(

                        business.name[:1].upper(),

                        styles["BusinessName"],

                    ),

                    Paragraph(

                        f"<b>{business.name}</b><br/>"

                        f"{business.address or ''}<br/>"

                        f"{business.phone or ''}"

                        f"{' · ' if business.phone and business.email else ''}"

                        f"{business.email or ''}",

                        styles["SmallText"],

                    ),

                ]

            )

    else:

        business_left.append(

            [

                Paragraph(

                    business.name[:1].upper(),

                    styles["BusinessName"],

                ),

                Paragraph(

                    f"<b>{business.name}</b><br/>"

                    f"{business.address or ''}<br/>"

                    f"{business.phone or ''}"

                    f"{' · ' if business.phone and business.email else ''}"

                    f"{business.email or ''}",

                    styles["SmallText"],

                ),

            ]

        )

    business_table = Table(

        business_left,

        colWidths=[

            20 * mm,

            85 * mm,

        ],

    )

    business_table.setStyle(

        TableStyle(

            [

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "MIDDLE",

                ),

                (

                    "LEFTPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

                (

                    "RIGHTPADDING",

                    (0, 0),

                    (-1, -1),

                    6,

                ),

                (

                    "TOPPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

                (

                    "BOTTOMPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

            ]

        )

    )

    invoice_title = Paragraph(

        (

            "INVOICE"

            f"<br/><font size='10' color='#0F766E'>"

            f"{order.order_number}"

            "</font>"

        ),

        styles["InvoiceTitle"],

    )

    header_table = Table(

        [

            [

                business_table,

                invoice_title,

            ]

        ],

        colWidths=[

            120 * mm,

            55 * mm,

        ],

    )

    header_table.setStyle(

        TableStyle(

            [

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "TOP",

                ),

                (

                    "BOTTOMPADDING",

                    (0, 0),

                    (-1, -1),

                    10,

                ),

                (

                    "LINEBELOW",

                    (0, 0),

                    (-1, -1),

                    0.6,

                    colors.HexColor("#E5E7EB"),

                ),

            ]

        )

    )

    story.append(

        header_table

    )

    story.append(

        Spacer(

            1,

            8 * mm,

        )

    )

    # =====================================================

    # CUSTOMER + ORDER DETAILS

    # =====================================================

    customer_address = (

        order.delivery_address

        or "No delivery address provided."

    )

    customer_block = [

        Paragraph(

            "BILL TO",

            styles["SectionLabel"],

        ),

        Paragraph(

            f"<b>{order.customer.full_name}</b>",

            styles["SmallBold"],

        ),

        Paragraph(

            (

                f"{order.customer.phone or ''}<br/>"

                f"{customer_address}"

            ),

            styles["SmallText"],

        ),

    ]

    details_data = [

        [

            Paragraph(

                "Date",

                styles["SmallText"],

            ),

            Paragraph(

                order.created_at.strftime(

                    "%d %b %Y"

                ),

                styles["RightBold"],

            ),

        ],

        [

            Paragraph(

                "Order Status",

                styles["SmallText"],

            ),

            Paragraph(

                order.get_status_display(),

                styles["RightBold"],

            ),

        ],

        [

            Paragraph(

                "Payment Method",

                styles["SmallText"],

            ),

            Paragraph(

                order.get_payment_method_display(),

                styles["RightBold"],

            ),

        ],

        [

            Paragraph(

                "Payment Status",

                styles["SmallText"],

            ),

            Paragraph(

                order.get_payment_status_display(),

                styles["RightBold"],

            ),

        ],

    ]

    details_table = Table(

        details_data,

        colWidths=[

            35 * mm,

            35 * mm,

        ],

    )

    details_table.setStyle(

        TableStyle(

            [

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "MIDDLE",

                ),

                (

                    "LEFTPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

                (

                    "RIGHTPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

                (

                    "TOPPADDING",

                    (0, 0),

                    (-1, -1),

                    2,

                ),

                (

                    "BOTTOMPADDING",

                    (0, 0),

                    (-1, -1),

                    2,

                ),

            ]

        )

    )

    info_table = Table(

        [

            [

                customer_block,

                [

                    Paragraph(

                        "INVOICE DETAILS",

                        styles["SectionLabel"],

                    ),

                    details_table,

                ],

            ]

        ],

        colWidths=[

            90 * mm,

            85 * mm,

        ],

    )

    info_table.setStyle(

        TableStyle(

            [

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "TOP",

                ),

                (

                    "LEFTPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

                (

                    "RIGHTPADDING",

                    (0, 0),

                    (-1, -1),

                    0,

                ),

            ]

        )

    )

    story.append(

        info_table

    )

    story.append(

        Spacer(

            1,

            8 * mm,

        )

    )

    # =====================================================

    # ITEMS

    # =====================================================

    story.append(

        Paragraph(

            "ORDER ITEMS",

            styles["SectionLabel"],

        )

    )

    item_rows = [

        [

            "PRODUCT",

            "SKU",

            "QTY",

            "UNIT PRICE",

            "TOTAL",

        ]

    ]

    for item in order.items.all():

        item_rows.append(

            [

                item.product_name,

                item.sku or "—",

                str(item.quantity),

                f"BDT {item.unit_price:.2f}",

                f"BDT {item.line_total:.2f}",

            ]

        )

    items_table = Table(

        item_rows,

        colWidths=[

            65 * mm,

            32 * mm,

            16 * mm,

            30 * mm,

            32 * mm,

        ],

        repeatRows=1,

    )

    items_table.setStyle(

        TableStyle(

            [

                (

                    "BACKGROUND",

                    (0, 0),

                    (-1, 0),

                    colors.HexColor("#F8FAFB"),

                ),

                (

                    "TEXTCOLOR",

                    (0, 0),

                    (-1, 0),

                    colors.HexColor("#6B7280"),

                ),

                (

                    "FONTNAME",

                    (0, 0),

                    (-1, 0),

                    "Helvetica-Bold",

                ),

                (

                    "FONTSIZE",

                    (0, 0),

                    (-1, 0),

                    8,

                ),

                (

                    "FONTSIZE",

                    (0, 1),

                    (-1, -1),

                    9,

                ),

                (

                    "ALIGN",

                    (2, 1),

                    (2, -1),

                    "CENTER",

                ),

                (

                    "ALIGN",

                    (3, 0),

                    (-1, -1),

                    "RIGHT",

                ),

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "MIDDLE",

                ),

                (

                    "GRID",

                    (0, 0),

                    (-1, -1),

                    0.5,

                    colors.HexColor("#E5E7EB"),

                ),

                (

                    "TOPPADDING",

                    (0, 0),

                    (-1, -1),

                    8,

                ),

                (

                    "BOTTOMPADDING",

                    (0, 0),

                    (-1, -1),

                    8,

                ),

                (

                    "LEFTPADDING",

                    (0, 0),

                    (-1, -1),

                    7,

                ),

                (

                    "RIGHTPADDING",

                    (0, 0),

                    (-1, -1),

                    7,

                ),

            ]

        )

    )

    story.append(

        items_table

    )

    story.append(

        Spacer(

            1,

            7 * mm,

        )

    )

    # =====================================================

    # SUMMARY

    # =====================================================

    summary_data = [

        [

            "Subtotal",

            f"BDT {order.subtotal:.2f}",

        ],

        [

            "Discount",

            f"- BDT {order.discount:.2f}",

        ],

        [

            "Delivery Charge",

            f"BDT {order.delivery_charge:.2f}",

        ],

        [

            "Total",

            f"BDT {order.total_amount:.2f}",

        ],

        [

            "Paid",

            f"BDT {order.paid_amount:.2f}",

        ],

        [

            "Amount Due",

            f"BDT {order.due_amount:.2f}",

        ],

    ]

    summary_table = Table(

        summary_data,

        colWidths=[

            42 * mm,

            38 * mm,

        ],

    )

    summary_table.setStyle(

        TableStyle(

            [

                (

                    "TEXTCOLOR",

                    (0, 0),

                    (0, -1),

                    colors.HexColor("#6B7280"),

                ),

                (

                    "FONTNAME",

                    (1, 0),

                    (1, -1),

                    "Helvetica-Bold",

                ),

                (

                    "ALIGN",

                    (1, 0),

                    (1, -1),

                    "RIGHT",

                ),

                (

                    "BOTTOMPADDING",

                    (0, 0),

                    (-1, -1),

                    6,

                ),

                (

                    "TOPPADDING",

                    (0, 0),

                    (-1, -1),

                    6,

                ),

                (

                    "LINEBELOW",

                    (0, 0),

                    (-1, -1),

                    0.4,

                    colors.HexColor("#EEF0F2"),

                ),

                # Total

                (

                    "FONTNAME",

                    (0, 3),

                    (-1, 3),

                    "Helvetica-Bold",

                ),

                (

                    "FONTSIZE",

                    (0, 3),

                    (-1, 3),

                    11,

                ),

                (

                    "TEXTCOLOR",

                    (1, 3),

                    (1, 3),

                    colors.HexColor("#0F766E"),

                ),

                # Paid

                (

                    "TEXTCOLOR",

                    (1, 4),

                    (1, 4),

                    colors.HexColor("#16A34A"),

                ),

                # Due

                (

                    "TEXTCOLOR",

                    (1, 5),

                    (1, 5),

                    colors.HexColor("#DC2626"),

                ),

            ]

        )

    )

    summary_outer = Table(

        [

            [

                "",

                summary_table,

            ]

        ],

        colWidths=[

            95 * mm,

            80 * mm,

        ],

    )

    summary_outer.setStyle(

        TableStyle(

            [

                (

                    "VALIGN",

                    (0, 0),

                    (-1, -1),

                    "TOP",

                ),

            ]

        )

    )

    story.append(

        summary_outer

    )

    # =====================================================

    # COURIER

    # =====================================================

    if (

        order.courier_name

        or order.tracking_number

    ):

        story.append(

            Spacer(

                1,

                7 * mm,

            )

        )

        courier_table = Table(

            [

                [

                    Paragraph(

                        "COURIER",

                        styles["SectionLabel"],

                    ),

                    Paragraph(

                        "TRACKING NUMBER",

                        styles["SectionLabel"],

                    ),

                ],

                [

                    Paragraph(

                        order.courier_name or "—",

                        styles["SmallBold"],

                    ),

                    Paragraph(

                        order.tracking_number or "—",

                        styles["SmallBold"],

                    ),

                ],

            ],

            colWidths=[

                87.5 * mm,

                87.5 * mm,

            ],

        )

        courier_table.setStyle(

            TableStyle(

                [

                    (

                        "BACKGROUND",

                        (0, 0),

                        (-1, -1),

                        colors.HexColor("#FAFBFC"),

                    ),

                    (

                        "BOX",

                        (0, 0),

                        (-1, -1),

                        0.5,

                        colors.HexColor("#E5E7EB"),

                    ),

                    (

                        "LEFTPADDING",

                        (0, 0),

                        (-1, -1),

                        10,

                    ),

                    (

                        "RIGHTPADDING",

                        (0, 0),

                        (-1, -1),

                        10,

                    ),

                    (

                        "TOPPADDING",

                        (0, 0),

                        (-1, -1),

                        7,

                    ),

                    (

                        "BOTTOMPADDING",

                        (0, 0),

                        (-1, -1),

                        7,

                    ),

                ]

            )

        )

        story.append(

            courier_table

        )

    # =====================================================

    # FOOTER

    # =====================================================

    story.append(

        Spacer(

            1,

            9 * mm,

        )

    )

    footer_note = (

        business.invoice_note

        or "Thank you for your order."

    )

    story.append(

        Paragraph(

            footer_note,

            styles["FooterNote"],

        )

    )

    story.append(

        Spacer(

            1,

            3 * mm,

        )

    )

    story.append(

        Paragraph(

            "Generated with OrderPilot",

            ParagraphStyle(

                name="Powered",

                parent=styles["FooterNote"],

                fontSize=7,

                textColor=colors.HexColor(

                    "#B0B5BD"

                ),

            ),

        )

    )

    document.build(

        story

    )

    pdf = buffer.getvalue()

    buffer.close()

    filename = (

        f"Invoice-{order.order_number}.pdf"

    )

    response = HttpResponse(

        pdf,

        content_type="application/pdf",

    )

    response[

        "Content-Disposition"

    ] = (

        f'attachment; filename="{filename}"'

    )

    return response

# =========================================================

# RECORD PAYMENT

# =========================================================

@login_required

@require_POST

def order_payment_create(

    request,

    pk,

):

    business = get_current_business(

        request.user

    )

    with transaction.atomic():

        order = get_object_or_404(

            Order.objects

            .select_for_update(),

            pk=pk,

            business=business,

        )

        payment_form = OrderPaymentForm(

            request.POST,

            order=order,

        )

        if not payment_form.is_valid():

            for field_errors in (

                payment_form.errors.values()

            ):

                for error in field_errors:

                    messages.error(

                        request,

                        error,

                    )

            return redirect(

                "orders:detail",

                pk=order.pk,

            )

        if (

            order.due_amount

            <= Decimal("0.00")

        ):

            messages.info(

                request,

                (

                    "This order has already "

                    "been fully paid."

                ),

            )

            return redirect(

                "orders:detail",

                pk=order.pk,

            )

        payment = (

            payment_form.save(

                commit=False

            )

        )

        payment.order = order

        payment.business = business

        payment.received_by = (

            request.user

        )

        payment.save()

        order.paid_amount += (

            payment.amount

        )

        order.payment_status = (

            calculate_payment_status(

                order

            )

        )

        order.save(

            update_fields=[

                "paid_amount",

                "payment_status",

                "updated_at",

            ]

        )

    messages.success(

        request,

        (

            f"Payment of ৳{payment.amount} "

            f"recorded successfully."

        ),

    )

    return redirect(

        "orders:detail",

        pk=order.pk,

    )


# =========================================================

# RECORD REFUND

# =========================================================

@login_required

@require_POST

def order_refund_create(

    request,

    pk,

):

    business = get_current_business(

        request.user

    )

    with transaction.atomic():

        order = get_object_or_404(

            Order.objects

            .select_for_update(),

            pk=pk,

            business=business,

        )

        refund_form = OrderRefundForm(

            request.POST,

            order=order,

        )

        if not refund_form.is_valid():

            for field_errors in (

                refund_form.errors.values()

            ):

                for error in field_errors:

                    messages.error(

                        request,

                        error,

                    )

            return redirect(

                "orders:detail",

                pk=order.pk,

            )

        refund = (

            refund_form.save(

                commit=False

            )

        )

        refund.order = order

        refund.business = business

        refund.refunded_by = (

            request.user

        )

        refund.save()

        order.refunded_amount += (

            refund.amount

        )

        order.payment_status = (

            calculate_payment_status(

                order

            )

        )

        order.save(

            update_fields=[

                "refunded_amount",

                "payment_status",

                "updated_at",

            ]

        )

    messages.success(

        request,

        (

            f"Refund of ৳{refund.amount} "

            f"recorded successfully."

        ),

    )

    return redirect(

        "orders:detail",

        pk=order.pk,

    )


# =========================================================

# COURIER + COD SETTLEMENT

# =========================================================

@login_required

@require_POST

def order_courier_settlement(

    request,

    pk,

):

    business = get_current_business(

        request.user

    )

    with transaction.atomic():

        order = get_object_or_404(

            Order.objects

            .select_for_update(),

            pk=pk,

            business=business,

        )

        try:

            settlement = (

                CourierSettlement.objects

                .select_for_update()

                .get(

                    order=order,

                    business=business,

                )

            )

        except CourierSettlement.DoesNotExist:

            settlement = CourierSettlement(

                order=order,

                business=business,

            )

        form = CourierSettlementForm(

            request.POST,

            order=order,

            instance=settlement,

        )

        if not form.is_valid():

            for field_errors in (

                form.errors.values()

            ):

                for error in field_errors:

                    messages.error(

                        request,

                        error,

                    )

            return redirect(

                "orders:detail",

                pk=order.pk,

            )

        settlement = form.save(

            commit=False

        )

        settlement.order = order

        settlement.business = business

        cod_expected = (

            settlement.cod_expected

            or Decimal("0.00")

        )

        cod_received = (

            settlement.cod_received

            or Decimal("0.00")

        )

        # =============================================

        # AUTO SETTLEMENT STATUS

        # =============================================

        if cod_expected <= Decimal(

            "0.00"

        ):

            settlement.settlement_status = (

                CourierSettlement

                .STATUS_SETTLED

            )

            settlement.settled_at = (

                timezone.now()

            )


            create_notification(
                business=business,
                title="Courier settlement complete",
                message=(
                    f"{order.order_number} "
                    "COD settlement is complete."
                ),
                notification_type=(
                    Notification.TYPE_SUCCESS
                ),
                url=(
                    f"/orders/{order.pk}/"
                ),
                event_key=(
                    f"courier-settled-{order.pk}"
                ),
            )

        elif cod_received <= Decimal(

            "0.00"

        ):

            settlement.settlement_status = (

                CourierSettlement

                .STATUS_PENDING

            )

            settlement.settled_at = None

        elif cod_received < cod_expected:

            settlement.settlement_status = (

                CourierSettlement

                .STATUS_PARTIAL

            )

            settlement.settled_at = None


            create_notification(
                business=business,
                title="Courier settlement partial",
                message=(
                    f"{order.order_number} "
                    f"still has ৳"
                    f"{cod_expected - cod_received} "
                    "COD outstanding."
                ),
                notification_type=(
                    Notification.TYPE_WARNING
                ),
                url=(
                    f"/orders/{order.pk}/"
                ),
                event_key=(
                    f"courier-partial-{order.pk}"
                ),
            )

        else:

            settlement.settlement_status = (

                CourierSettlement

                .STATUS_SETTLED

            )

            if not settlement.settled_at:

                settlement.settled_at = (

                    timezone.now()

                )


            create_notification(
                business=business,
                title="Courier settlement complete",
                message=(
                    f"{order.order_number} "
                    "COD settlement is complete."
                ),
                notification_type=(
                    Notification.TYPE_SUCCESS
                ),
                url=(
                    f"/orders/{order.pk}/"
                ),
                event_key=(
                    f"courier-settled-{order.pk}"
                ),
            )

        settlement.save()

        # =============================================

        # UPDATE ORDER COURIER INFO

        # =============================================

        courier_name = (

            form.cleaned_data

            .get(

                "courier_name",

                "",

            )

            .strip()

        )

        tracking_number = (

            form.cleaned_data

            .get(

                "tracking_number",

                "",

            )

            .strip()

        )

        changed_fields = []

        if (

            order.courier_name

            != courier_name

        ):

            order.courier_name = (

                courier_name

            )

            changed_fields.append(

                "courier_name"

            )

        if (

            order.tracking_number

            != tracking_number

        ):

            order.tracking_number = (

                tracking_number

            )

            changed_fields.append(

                "tracking_number"

            )

        if changed_fields:

            changed_fields.append(

                "updated_at"

            )

            order.save(

                update_fields=changed_fields

            )

    messages.success(

        request,

        (

            "Courier and COD settlement "

            "updated successfully."

        ),

    )

    return redirect(

        "orders:detail",

        pk=order.pk,

    )