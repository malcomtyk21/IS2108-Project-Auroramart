from django.shortcuts import render, redirect
from django.views import View
from .forms import (
    BasicRegisterForm,
    CustomerProfileForm,
    PaymentInformationForm,
    ShippingInformationForm,
    AccountParticularsForm,
)
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from adminpanel.models import Product
from django.db.models import Q
from .models import Customer, Cart, CartItem, PaymentInformation, ShippingInformation, Order
from . import ml
from functools import wraps
from django.http import HttpRequest, HttpResponse

from django.contrib import messages
from decimal import Decimal
from django.db import transaction


# -----------------------------
# Customer-only helpers
# -----------------------------
def block_staff_superuser(view_func):
    """Decorator for function views: if an authenticated staff/superuser
    accesses a storefront view, render the storefront forbidden page.
    Anonymous users are unaffected (they continue to the view or login_required will redirect).
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return render(request, "onlinestorefront/forbidden.html", status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


class CustomerOnlyMixin:
    """CBV mixin: allow access only to non-staff, non-superuser customers.

    - If user is staff/superuser (and authenticated): render forbidden page.
    - If user is anonymous: redirect to `login_url` (expected on view via LoginRequiredMixin).
    """
    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return render(request, "onlinestorefront/forbidden.html", status=403)

        if not (user and user.is_authenticated):
            # rely on LoginRequiredMixin's login behavior if present
            login_url = getattr(self, "login_url", reverse_lazy("onlinestorefront:storeLogin"))
            return redirect(login_url)

        return super().dispatch(request, *args, **kwargs)



# Create your views here.
@block_staff_superuser
def index(request):
    """Home page.

    Behaviour:
    - Anonymous or user with no preferred_category: show random selection of all products.
    - User with preferred_category populated: show random selection drawn from that category.
    """
    preferred_category = ""
    if request.user.is_authenticated:
        try:
            preferred_category = request.user.profile.preferred_category or ""
        except Exception:
            preferred_category = ""  # profile absent

    # Only consider active products for storefront visibility
    base_qs = Product.objects.filter(status='Active')
    if preferred_category:
        # Filter by preferred category; if no products match, fall back to global random sample.
        category_qs = Product.objects.filter(product_category=preferred_category, status='Active')
        if category_qs.exists():
            sample_qs = category_qs.order_by("?")[:20]
        else:
            sample_qs = base_qs.order_by("?")[:20]
    else:
        sample_qs = base_qs.order_by("?")[:20]

    products = list(sample_qs)
    context = {
        "random_products": products,
        "preferred_category": preferred_category,
    }
    return render(request, "onlinestorefront/index.html", context)


@block_staff_superuser
def category(request, category: str):
    cat = (category or "").strip()
    if not cat:
        return render(request, "onlinestorefront/category.html", {"category_name": category, "subcategories": []}, status=404)

    subcategories = []
    sub_names = (
        Product.objects.filter(product_category=cat, status='Active')
        .exclude(product_subcategory__isnull=True)
        .exclude(product_subcategory="")
        .values_list("product_subcategory", flat=True)
        .distinct()
    )
    for sname in sub_names:
        items = list(
            Product.objects.filter(
                product_category=cat,
                product_subcategory=sname,
                status='Active'
            ).order_by("id")[:4]
        )
        subcategories.append({"name": sname, "products": items})

    # Also provide a paginated listing of all products in the category
    qs = Product.objects.filter(product_category=cat, status='Active').order_by("id")
    paginator = Paginator(qs, 20)
    page = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(
        request,
        "onlinestorefront/category.html",
        {"category_name": cat, "subcategories": subcategories, "page_obj": page_obj},
    )


@block_staff_superuser
def subcategory(request, category: str, subcategory: str):
    """Subcategory product listing page with pagination.

    /category/<category>/<subcategory>/?page=<n>
    """
    cat = (category or "").strip()
    sub = (subcategory or "").strip()
    if not (cat and sub):
        return redirect(reverse_lazy("onlinestorefront:index"))

    qs = Product.objects.filter(
        product_category=cat,
        product_subcategory=sub,
        status='Active'
    ).order_by("id")
    paginator = Paginator(qs, 10)
    page = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(
        request,
        "onlinestorefront/subcategory.html",
        {
            "category_name": cat,
            "current_subcategory": sub,
            "page_obj": page_obj,
        },
    )


@block_staff_superuser
def product_detail(request, pk: int):
    """Show details for a single product."""
    # Only serve active products; treat inactive/missing as 404
    product = Product.objects.filter(pk=pk, status='Active').first()
    if not product:
        return render(
            request,
            "onlinestorefront/product_detail.html",
            {"product": None},
            status=404,
        )

    # Compute recommendations (by SKU) using association rules if available
    recommended_products = []
    try:
        sku = getattr(product, 'sku_code', None)
        if sku:
            rec_skus = ml.get_recommendations(ml.loaded_rules, [sku], metric='lift', top_n=5)
            if rec_skus:
                # Fetch matching Product objects; ignore missing SKUs
                recommended_products = list(Product.objects.filter(sku_code__in=rec_skus, status='Active')[:5])
    except Exception:
        recommended_products = []

    return render(
        request,
        "onlinestorefront/product_detail.html",
        {"product": product, "recommended_products": recommended_products},
    )


class Register(View):
    def get(self, request):
        form = BasicRegisterForm()
        return render(request, "onlinestorefront/register.html", {"form": form})

    def post(self, request):
        form = BasicRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/")
        return render(request, "onlinestorefront/register.html", {"form": form})


def forbidden(request):
    return render(request, "onlinestorefront/forbidden.html", status=403)


class StoreLogin(LoginView):
    template_name = "onlinestorefront/storeLogin.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("onlinestorefront:index")
    
    def dispatch(self, request, *args, **kwargs):
        # If an already-authenticated user is staff/superuser, show forbidden.
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return render(request, "onlinestorefront/forbidden.html", status=403)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Prevent staff/superuser accounts from logging into the storefront.
        user = form.get_user()
        if user.is_staff or user.is_superuser:
            return render(self.request, "onlinestorefront/forbidden.html", status=403)
        return super().form_valid(form)
    


class StoreLogout(LogoutView):
    next_page = reverse_lazy("onlinestorefront:index")


class SettingsView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Unified settings page with sub-navigation for Profile, Payments, Shipping.

    Uses a `tab` query (GET) or hidden field (POST) to select the active section.
    Tabs: `profile`, `payments`, `shipping`.
    """

    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def _build_context(self, request, active_tab: str):
        customer_obj, _ = Customer.objects.get_or_create(user=request.user)
        # Build per-item edit forms for inline editing
        payments = list(PaymentInformation.objects.filter(customer=customer_obj).order_by("-id"))
        shippings = list(ShippingInformation.objects.filter(customer=customer_obj).order_by("-id"))
        payment_pairs = [{"obj": p, "form": PaymentInformationForm(instance=p)} for p in payments]
        shipping_pairs = [{"obj": s, "form": ShippingInformationForm(instance=s)} for s in shippings]

        ctx = {
            "active_tab": active_tab,
            "profile_form": CustomerProfileForm(instance=customer_obj),
            "account_form": AccountParticularsForm(instance=request.user),
            "payment_form": PaymentInformationForm(),
            "shipping_form": ShippingInformationForm(),
            "password_form": PasswordChangeForm(user=request.user),
            "payments": payments,
            "shippings": shippings,
            "payment_pairs": payment_pairs,
            "shipping_pairs": shipping_pairs,
            "preferred_category": customer_obj.preferred_category,
        }
        return ctx

    def get(self, request):
        tab = request.GET.get("tab", "account").lower()
        if tab not in {"profile", "account", "password", "payments", "shipping"}:
            tab = "account"
        ctx = self._build_context(request, tab)
        return render(request, "onlinestorefront/settings.html", ctx)

    def post(self, request):
        tab = (request.POST.get("tab") or request.GET.get("tab") or "account").lower()
        if tab not in {"profile", "account", "password", "payments", "shipping"}:
            tab = "account"

        customer_obj, _ = Customer.objects.get_or_create(user=request.user)

        if tab == "profile":
            form = CustomerProfileForm(request.POST, instance=customer_obj)
            if form.is_valid():
                updated = form.save()
                cleaned = form.cleaned_data
                empty_submission = (
                    (cleaned.get("age") in (None, 0))
                    and (cleaned.get("household_size") in (None, 0))
                    and (not cleaned.get("has_children"))
                    and (cleaned.get("monthly_income_sgd") in (None, 0.0))
                    and (not cleaned.get("gender"))
                    and (not cleaned.get("employment_status"))
                    and (not cleaned.get("occupation"))
                    and (not cleaned.get("education"))
                )
                if empty_submission:
                    updated.preferred_category = ""
                    updated.save(update_fields=["preferred_category"])
                else:
                    predicted = ml.predict_preferred_category(updated)
                    if predicted:
                        updated.preferred_category = predicted
                        updated.save(update_fields=["preferred_category"])
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=profile")

            ctx = self._build_context(request, "profile")
            ctx["profile_form"] = form
            return render(request, "onlinestorefront/settings.html", ctx)

        if tab == "account":
            form = AccountParticularsForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=account")
            ctx = self._build_context(request, "account")
            ctx["account_form"] = form
            return render(request, "onlinestorefront/settings.html", ctx)

        if tab == "password":
            # PasswordChangeForm requires the user object as first arg
            form = PasswordChangeForm(user=request.user, data=request.POST)
            if form.is_valid():
                user = form.save()
                # Keep the user logged in after password change
                update_session_auth_hash(request, user)
                # Inform the user of success
                messages.success(request, "Your password has been changed successfully.")
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=password")
            ctx = self._build_context(request, "password")
            # Add an error banner and re-render the settings page with form errors
            messages.error(request, "Unable to change password. Please correct the errors below.")
            ctx["password_form"] = form
            return render(request, "onlinestorefront/settings.html", ctx)

        if tab == "payments":
            action = request.POST.get("action", "add")
            if action == "delete":
                try:
                    pk = int(request.POST.get("payment_id"))
                except (TypeError, ValueError):
                    messages.warning(request, "Invalid payment selection.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=payments")

                deleted, _ = PaymentInformation.objects.filter(pk=pk, customer=customer_obj).delete()
                if deleted:
                    messages.success(request, "Payment method removed.")
                else:
                    messages.warning(request, "Payment method not found.")
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=payments")

            if action == "edit":
                try:
                    pk = int(request.POST.get("payment_id"))
                    instance = PaymentInformation.objects.get(pk=pk, customer=customer_obj)
                except (PaymentInformation.DoesNotExist, TypeError, ValueError):
                    messages.warning(request, "Selected payment method not found.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=payments")
                form = PaymentInformationForm(request.POST, instance=instance)
                if form.is_valid():
                    card_number = form.cleaned_data.get("card_number") or ""
                    payment = form.save(commit=False)
                    if card_number:
                        payment.card_last4 = card_number.replace(" ", "")[-4:]
                    payment.save()
                    messages.success(request, "Payment details updated.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=payments")
                ctx = self._build_context(request, "payments")
                # Replace the edited pair's form with bound one
                for pair in ctx.get("payment_pairs", []):
                    if pair.get("obj").id == getattr(instance, "id", None):
                        pair["form"] = form
                return render(request, "onlinestorefront/settings.html", ctx)

            # default: add new
            form = PaymentInformationForm(request.POST)
            if form.is_valid():
                card_number = form.cleaned_data.get("card_number") or ""
                obj = form.save(commit=False)
                obj.customer = customer_obj
                if card_number:
                    obj.card_last4 = card_number.replace(" ", "")[-4:]
                obj.save()
                messages.success(request, "Payment method saved.")
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=payments")
            ctx = self._build_context(request, "payments")
            ctx["payment_form"] = form
            return render(request, "onlinestorefront/settings.html", ctx)

        if tab == "shipping":
            action = request.POST.get("action", "add")
            if action == "delete":
                try:
                    pk = int(request.POST.get("shipping_id"))
                except (TypeError, ValueError):
                    messages.warning(request, "Invalid shipping selection.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=shipping")

                deleted, _ = ShippingInformation.objects.filter(pk=pk, customer=customer_obj).delete()
                if deleted:
                    messages.success(request, "Shipping address removed.")
                else:
                    messages.warning(request, "Shipping address not found.")
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=shipping")

            if action == "edit":
                try:
                    pk = int(request.POST.get("shipping_id"))
                    instance = ShippingInformation.objects.get(pk=pk, customer=customer_obj)
                except (ShippingInformation.DoesNotExist, TypeError, ValueError):
                    messages.warning(request, "Selected shipping address not found.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=shipping")
                form = ShippingInformationForm(request.POST, instance=instance)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Shipping address updated.")
                    return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=shipping")
                ctx = self._build_context(request, "shipping")
                for pair in ctx.get("shipping_pairs", []):
                    if pair.get("obj").id == getattr(instance, "id", None):
                        pair["form"] = form
                return render(request, "onlinestorefront/settings.html", ctx)

            # default: add new
            form = ShippingInformationForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.customer = customer_obj
                obj.save()
                messages.success(request, "Shipping address saved.")
                return redirect(f"{reverse_lazy('onlinestorefront:settings')}?tab=shipping")
            ctx = self._build_context(request, "shipping")
            ctx["shipping_form"] = form
            return render(request, "onlinestorefront/settings.html", ctx)

        # default fallback
        return redirect(reverse_lazy("onlinestorefront:settings"))


# -----------------------------
# Cart views
# -----------------------------
def _get_user_cart(user) -> Cart:
    """Return or create the user's cart."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


class CartView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Display the current user's cart with items and totals."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def get(self, request: HttpRequest) -> HttpResponse:
        cart = _get_user_cart(request.user)
        # Prefetch product for efficiency
        items = cart.items.select_related("product").all()
        # Compute totals
        line_items = []
        subtotal = 0
        for it in items:
            price = float(getattr(it.product, "unit_price", 0) or 0)
            qty = int(it.quantity or 0)
            line_total = price * qty
            subtotal += line_total
            # Per-item recommendations (association rules by SKU)
            recs = []
            try:
                sku = getattr(it.product, 'sku_code', None)
                if sku:
                    rec_skus = ml.get_recommendations(ml.loaded_rules, [sku], metric='lift', top_n=5)
                    if rec_skus:
                        recs = list(Product.objects.filter(sku_code__in=rec_skus, status='Active')[:5])
            except Exception:
                recs = []
            line_items.append({
                "item": it,
                "product": it.product,
                "price": price,
                "qty": qty,
                "line_total": line_total,
                "recommendations": recs,
                "is_active": (getattr(it.product, 'status', 'Active') == 'Active'),
            })
        context = {
            "cart": cart,
            "items": line_items,
            "subtotal": subtotal,
        }
        return render(request, "onlinestorefront/cart.html", context)


class AddToCartView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Add a product to the cart. POST only; increments quantity if exists."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def post(self, request: HttpRequest, product_id: int) -> HttpResponse:
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            messages.warning(request, "Product not found.")
            return redirect("onlinestorefront:cart")

        if getattr(product, 'status', 'Active') != 'Active':
            messages.warning(request, "This product is inactive and cannot be added to cart.")
            return redirect("onlinestorefront:cart")

        cart = _get_user_cart(request.user)
        qty = 1
        try:
            qty = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, min(qty, 999))

        if product.quantity_on_hand <= 0:
            messages.warning(request, "This product is out of stock.")
            return redirect("onlinestorefront:cart")

        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": min(qty, product.quantity_on_hand)})
        if not created:
            new_qty = item.quantity + qty
            max_allowed = product.quantity_on_hand
            item.quantity = max(1, min(new_qty, max_allowed))
            item.save(update_fields=["quantity"])

        messages.success(request, "Product added to cart." if created else "Cart updated.")
        return redirect("onlinestorefront:cart")


class UpdateCartItemView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Update a cart item's quantity. POST with 'quantity' or 'op' in {inc, dec}."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        try:
            item = CartItem.objects.select_related("cart").get(pk=item_id, cart__user=request.user)
        except CartItem.DoesNotExist:
            return redirect("onlinestorefront:cart")

        # Prevent modifying quantities for inactive products
        if getattr(item.product, 'status', 'Active') != 'Active':
            messages.warning(request, "Inactive product cannot be modified. Remove it from your cart.")
            return redirect("onlinestorefront:cart")

        op = request.POST.get("op")
        max_allowed = item.product.quantity_on_hand
        if max_allowed <= 0:
            item.delete()
            return redirect("onlinestorefront:cart")

        if op == "inc":
            item.quantity = min(item.quantity + 1, max_allowed)
        elif op == "dec":
            item.quantity = max(item.quantity - 1, 1)
        else:
            try:
                q = int(request.POST.get("quantity", item.quantity))
                item.quantity = max(1, min(q, max_allowed))
            except (TypeError, ValueError):
                pass
        item.save(update_fields=["quantity"])
        messages.success(request, "Item quantity updated.")
        return redirect("onlinestorefront:cart")


class RemoveCartItemView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Remove an item from the cart. POST only."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        deleted, _ = CartItem.objects.filter(pk=item_id, cart__user=request.user).delete()
        if deleted:
            messages.success(request, "Item removed from cart.")
        else:
            messages.warning(request, "Item not found in your cart.")
        return redirect("onlinestorefront:cart")


class CheckoutView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Checkout screen: GET shows all items, POST accepts `selected_items` to filter."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def build_context(self, request, selected_ids=None, selected_payment=None, selected_shipping=None):
        cart = _get_user_cart(request.user)
        items_qs = cart.items.select_related("product")
        if selected_ids:
            items_qs = items_qs.filter(id__in=selected_ids)
        # Exclude inactive products from checkout
        items_qs = items_qs.filter(product__status='Active')

        line_items = []
        subtotal = 0.0
        for it in items_qs:
            price = float(getattr(it.product, "unit_price", 0) or 0)
            qty = int(getattr(it, "quantity", 0) or 0)
            line_total = round(price * qty, 2)
            subtotal += line_total
            line_items.append({
                "item": it,
                "product": it.product,
                "qty": qty,
                "price": price,
                "line_total": line_total,
            })

        if not line_items:
            return None

        customer_obj, _ = Customer.objects.get_or_create(user=request.user)
        payments = list(PaymentInformation.objects.filter(customer=customer_obj).order_by("-id"))
        shippings = list(ShippingInformation.objects.filter(customer=customer_obj).order_by("-id"))

        return {
            "items": line_items,
            "subtotal": round(subtotal, 2),
            "item_count": len(line_items),
            "payments": payments,
            "shippings": shippings,
            "selected_ids": selected_ids or [],
            "selected_payment": selected_payment,
            "selected_shipping": selected_shipping,
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        # Disallow direct GET navigation to the checkout page.
        # The checkout flow must be initiated from the cart with an explicit
        # selection of items (POST). Redirect back to the cart if accessed via GET.
        messages.warning(request, "Please select at least one item to checkout.")
        return redirect("onlinestorefront:cart")

    def post(self, request: HttpRequest) -> HttpResponse:
        raw_ids = request.POST.getlist("selected_items")
        # If no selected_items were submitted, do not fall back to "all items".
        # This prevents the form being submitted with nothing checked and
        # unintentionally checking out the whole cart.
        if not raw_ids:
            messages.warning(request, "Please select at least one item to checkout.")
            return redirect("onlinestorefront:cart")

        selected_ids = []
        for rid in raw_ids:
            try:
                selected_ids.append(int(rid))
            except (TypeError, ValueError):
                continue

        # If all submitted ids were invalid (resulting in an empty list),
        # treat this as no selection and redirect back to cart.
        if not selected_ids:
            messages.warning(request, "Please select at least one item to checkout.")
            return redirect("onlinestorefront:cart")

        payment_id = request.POST.get("payment_id")
        shipping_id = request.POST.get("shipping_id")
        selected_payment = None
        selected_shipping = None
        customer_obj, _ = Customer.objects.get_or_create(user=request.user)
        if payment_id:
            try:
                selected_payment = PaymentInformation.objects.get(pk=int(payment_id), customer=customer_obj)
            except (PaymentInformation.DoesNotExist, ValueError, TypeError):
                selected_payment = None
        if shipping_id:
            try:
                selected_shipping = ShippingInformation.objects.get(pk=int(shipping_id), customer=customer_obj)
            except (ShippingInformation.DoesNotExist, ValueError, TypeError):
                selected_shipping = None

        ctx = self.build_context(
            request,
            selected_ids=selected_ids,
            selected_payment=selected_payment,
            selected_shipping=selected_shipping,
        )
        if not ctx:
            return redirect("onlinestorefront:cart")

        # If the user pressed the Place Order button, create an Order snapshot
        if request.POST.get("place_order"):
            # Validate selections
            if not selected_payment or not selected_shipping:
                ctx["error"] = "Please select both a payment method and a shipping address."
                return render(request, "onlinestorefront/checkout.html", ctx)
            # Prevent placing order if any selected cart items were inactive (already filtered out)
            if not ctx.get("items"):
                messages.warning(request, "Selected items are no longer available.")
                return redirect("onlinestorefront:cart")

            # Create order inside an atomic transaction and lock involved products
            from .models import Order, OrderItems

            cart = _get_user_cart(request.user)
            items_qs = cart.items.select_related("product")
            if selected_ids:
                items_qs = items_qs.filter(id__in=selected_ids)

            product_ids = [it.product.pk for it in items_qs]

            try:
                with transaction.atomic():
                    # Lock product rows to avoid race conditions
                    locked_products = {
                        p.pk: p for p in Product.objects.select_for_update().filter(pk__in=product_ids)
                    }

                    # Validate stock for each item (if the product tracks stock)
                    for it in items_qs:
                        prod = locked_products.get(it.product.pk)
                        if prod is None:
                            # product vanished; abort
                            ctx["error"] = f"Product {it.product} is no longer available."
                            return render(request, "onlinestorefront/checkout.html", ctx)
                        avail = getattr(prod, "quantity_on_hand", None)
                        qty = int(it.quantity or 0)
                        if avail is not None and qty > (avail or 0):
                            ctx["error"] = f"Insufficient stock for {prod.product_name}: {avail} left."
                            return render(request, "onlinestorefront/checkout.html", ctx)

                    # All checks passed; create the Order
                    total_amount = Decimal(str(ctx.get("subtotal", 0)))
                    order = Order.objects.create(
                        total_amount=total_amount,
                        status="pending",
                        customer=customer_obj,
                        card_last4=selected_payment.card_last4,
                        card_brand=selected_payment.card_brand,
                        expiry_month=int(selected_payment.expiry_month) if selected_payment.expiry_month else None,
                        expiry_year=int(selected_payment.expiry_year) if selected_payment.expiry_year else None,
                        cardholder_name=selected_payment.cardholder_name,
                        billing_address=selected_payment.billing_address,
                        shipping_address_line1=selected_shipping.address_line1,
                        shipping_address_line2=selected_shipping.address_line2,
                        shipping_city=selected_shipping.city,
                        shipping_state=selected_shipping.state,
                        shipping_postal_code=str(selected_shipping.postal_code),
                        shipping_country=selected_shipping.country,
                        shipping_contact_number=selected_shipping.contact_number,
                    )

                    # Create order items and deduct stock
                    for it in items_qs:
                        prod = locked_products.get(it.product.pk)
                        qty = int(it.quantity or 0)
                        price = Decimal(str(getattr(prod, "unit_price", 0) or 0))
                        OrderItems.objects.create(order=order, product=prod, quantity=qty, price_at_purchase=price)
                        # Deduct stock if supported
                        if hasattr(prod, "quantity_on_hand"):
                            prod.quantity_on_hand = max(0, (prod.quantity_on_hand or 0) - qty)
                            prod.save(update_fields=["quantity_on_hand"])

                    # Remove purchased items from cart
                    items_qs.delete()

                    return render(request, "onlinestorefront/order_success.html", {"order": order})
            except Exception:
                ctx["error"] = "An error occurred while placing the order. Please try again."
                return render(request, "onlinestorefront/checkout.html", ctx)

        return render(request, "onlinestorefront/checkout.html", ctx)


# -----------------------------
# Product search
# -----------------------------
def search(request: HttpRequest) -> HttpResponse:
    """Basic product search endpoint.

    Query string parameter:
      q: the search term (case-insensitive). We perform an icontains match
         against product name, description, category and subcategory.

    Behaviour:
      - Empty or missing q -> render page with no results and guidance.
      - Non-empty q -> up to 200 matching products ordered by name.
    """
    raw_q = request.GET.get("q", "")
    q = (raw_q or "").strip()
    products = []
    total = 0
    if q:
        # Build a single combined OR filter.
        filter_q = (
            Q(product_name__icontains=q)
            | Q(product_description__icontains=q)
            | Q(product_category__icontains=q)
            | Q(product_subcategory__icontains=q)
        )
        qs = Product.objects.filter(filter_q, status='Active').order_by("product_name")[:200]
        products = list(qs)
        total = len(products)
    context = {
        "query": q,
        "raw_query": raw_q,  # original before strip (for potential UX later)
        "products": products,
        "total": total,
        "limit": 200,
    }
    return render(request, "onlinestorefront/search_results.html", context)


# -----------------------------
# Saved Payment & Shipping
# -----------------------------
# Old standalone views for listing/editing payments & shipping have been removed


# -----------------------------
# Orders
# -----------------------------
class OrdersListView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """List all orders made by the logged-in customer."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def get(self, request):
        customer_obj, _ = Customer.objects.get_or_create(user=request.user)
        orders = (
            Order.objects.filter(customer=customer_obj)
            .prefetch_related("order_items", "order_items__product")
            .order_by("-created_at")
        )

        # Build a lightweight structure for template rendering
        order_list = []
        for o in orders:
            count = getattr(o, "order_items", None).count() if hasattr(o, "order_items") else 0
            preview_items = list(o.order_items.all()[:5])
            order_list.append(
                {
                    "id": o.id,
                    "created_at": o.created_at,
                    "status": o.status,
                    "total_amount": o.total_amount,
                    "item_count": count,
                    "items": preview_items,  # preview up to 5
                    "remaining": max(0, count - len(preview_items)),
                }
            )

        return render(request, "onlinestorefront/orders.html", {"orders": order_list})


class OrdersDetailView(CustomerOnlyMixin, LoginRequiredMixin, View):
    """Show the details of a single order placed by the current customer."""
    login_url = reverse_lazy("onlinestorefront:storeLogin")

    def get_object(self, user, pk):
        customer_obj, _ = Customer.objects.get_or_create(user=user)
        return (
            Order.objects.prefetch_related("order_items", "order_items__product")
            .get(pk=pk, customer=customer_obj)
        )

    def get(self, request, pk):
        try:
            order = self.get_object(request.user, pk)
        except Order.DoesNotExist:
            return redirect("onlinestorefront:orders")

        # Build line items with computed totals for template simplicity
        line_items = []
        subtotal = 0.0
        for it in order.order_items.all():
            price = float(it.price_at_purchase)
            qty = int(it.quantity)
            line_total = round(price * qty, 2)
            subtotal += line_total
            line_items.append({
                "name": getattr(it.product, "product_name", "Item"),
                "qty": qty,
                "price": price,
                "line_total": line_total,
            })

        context = {
            "order": order,
            "items": line_items,
            "subtotal": round(subtotal, 2),
        }
        return render(request, "onlinestorefront/order_detail.html", context)
