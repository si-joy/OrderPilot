from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth import (
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.businesses.models import (
    Business,
    BusinessMember,
)
from apps.businesses.utils import get_current_business
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.products.models import Product

from .forms import (
    OrderPilotAuthenticationForm,
    OrderPilotSignupForm,
    ProfileUpdateForm,
)
from .models import UserProfile


# =========================================================
# HELPERS
# =========================================================

def generate_business_slug(name):
    base_slug = slugify(name)

    if not base_slug:
        base_slug = "business"

    candidate = base_slug

    if not Business.objects.filter(
        slug=candidate
    ).exists():
        return candidate

    while True:
        suffix = uuid4().hex[:6]

        candidate = (
            f"{base_slug}-{suffix}"
        )

        if not Business.objects.filter(
            slug=candidate
        ).exists():
            return candidate


# =========================================================
# LOGIN
# =========================================================

class OrderPilotLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = OrderPilotAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return "/"


# =========================================================
# SIGNUP / ONBOARDING
# =========================================================

def signup(request):
    if request.user.is_authenticated:
        return redirect(
            "core:dashboard"
        )

    if request.method == "POST":

        form = OrderPilotSignupForm(
            request.POST
        )

        if form.is_valid():

            with transaction.atomic():

                user = form.save()

                business_name = (
                    form.cleaned_data[
                        "business_name"
                    ]
                )

                business_phone = (
                    form.cleaned_data[
                        "business_phone"
                    ]
                    .strip()
                )

                business = (
                    Business.objects.create(
                        name=business_name,
                        slug=generate_business_slug(
                            business_name
                        ),
                        phone=business_phone,
                        email=user.email,
                    )
                )

                BusinessMember.objects.create(
                    business=business,
                    user=user,
                    role=BusinessMember.ROLE_OWNER,
                    is_active=True,
                )

                UserProfile.objects.get_or_create(
                    user=user
                )

            login(
                request,
                user,
            )

            messages.success(
                request,
                (
                    "Welcome to OrderPilot! "
                    "Your workspace has been created."
                ),
            )

            return redirect(
                "core:dashboard"
            )

    else:
        form = OrderPilotSignupForm()

    return render(
        request,
        "auth/signup.html",
        {
            "form": form,
        },
    )


# =========================================================
# LOGOUT
# =========================================================

@login_required
@require_POST
def logout_view(request):
    logout(request)

    return redirect(
        "core:login"
    )


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile(request):
    user_profile, _ = (
        UserProfile.objects
        .get_or_create(
            user=request.user
        )
    )

    if request.method == "POST":

        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            user=request.user,
            profile=user_profile,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Your profile was updated successfully.",
            )

            return redirect(
                "core:profile"
            )

    else:

        form = ProfileUpdateForm(
            user=request.user,
            profile=user_profile,
        )

    return render(
        request,
        "auth/profile.html",
        {
            "form": form,
            "profile": user_profile,
        },
    )


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):
    business = get_current_business(
        request.user
    )

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

    total_orders = orders.count()

    delivered_orders = (
        orders.filter(
            status=Order.STATUS_DELIVERED
        )
        .count()
    )

    pending_orders = (
        orders.filter(
            status=Order.STATUS_PENDING
        )
        .count()
    )

    returned_orders = (
        orders.filter(
            status=Order.STATUS_RETURNED
        )
        .count()
    )

    total_customers = (
        Customer.objects
        .filter(
            business=business,
            is_active=True,
        )
        .count()
    )

    products = (
        Product.objects
        .filter(
            business=business,
            is_active=True,
        )
    )

    total_products = products.count()

    low_stock_count = sum(
        1
        for product in products
        if product.is_low_stock
    )

    cod_orders = (
        orders
        .filter(
            payment_method=Order.PAYMENT_COD,
        )
        .exclude(
            status__in=[
                Order.STATUS_CANCELLED,
                Order.STATUS_RETURNED,
            ]
        )
    )

    cod_pending = sum(
        (
            order.due_amount
            for order in cod_orders
        ),
        Decimal("0.00"),
    )

    delivered_queryset = (
        orders.filter(
            status=Order.STATUS_DELIVERED
        )
    )

    total_sales = sum(
        (
            order.total_amount
            for order in delivered_queryset
        ),
        Decimal("0.00"),
    )

    total_collected = sum(
        (
            order.paid_amount
            for order in orders
        ),
        Decimal("0.00"),
    )

    recent_orders = orders[:5]

    context = {
        "business": business,

        "total_orders": total_orders,
        "delivered_orders": delivered_orders,
        "pending_orders": pending_orders,
        "returned_orders": returned_orders,

        "total_customers": total_customers,
        "total_products": total_products,
        "low_stock_count": low_stock_count,

        "cod_pending": cod_pending,
        "total_sales": total_sales,
        "total_collected": total_collected,

        "recent_orders": recent_orders,
    }

    return render(
        request,
        "core/dashboard.html",
        context,
    )


# =========================================================
# COMPONENT DEMO
# =========================================================

def components_demo(request):
    return render(
        request,
        "core/components_demo.html",
    )