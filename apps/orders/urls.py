from django.urls import path

from . import views


app_name = "orders"


urlpatterns = [

    path(
        "",
        views.order_list,
        name="list",
    ),

    path(
        "new/",
        views.order_create,
        name="create",
    ),

    path(
        "<int:pk>/",
        views.order_detail,
        name="detail",
    ),

    path(
        "<int:pk>/status/",
        views.order_status_update,
        name="status_update",
    ),

    path(
        "<int:pk>/payments/new/",
        views.order_payment_create,
        name="payment_create",
    ),

    path(
        "<int:pk>/refunds/new/",
        views.order_refund_create,
        name="refund_create",
    ),

    path(
        "<int:pk>/courier-settlement/",
        views.order_courier_settlement,
        name="courier_settlement",
    ),

    path(
        "<int:pk>/invoice/",
        views.order_invoice,
        name="invoice",
    ),

    path(
        "<int:pk>/invoice/pdf/",
        views.order_invoice_pdf,
        name="invoice_pdf",
    ),

]
