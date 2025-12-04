from django.shortcuts import render, HttpResponse, redirect
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.views.generic import ListView, UpdateView, CreateView, DeleteView, DetailView
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.urls import reverse
from django.core.paginator import Paginator
from .models import Product
from onlinestorefront.models import Order as StorefrontOrder, OrderItems, Customer
from .forms import ProductForm, UploadCSVForm, CreateAdminForm, UserUpdateForm, CustomerCreateForm, OrderForm
from io import TextIOWrapper
import pandas as pd
import os
import plotly.io as pio
import plotly.graph_objects as go
from datetime import date

# for CBV login 
def staff_or_super(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

# for functions login
def staff_or_super_required(view_func):
    return user_passes_test(staff_or_super, login_url='forbidden')(view_func)

def forbidden(request):
    return render(request, 'adminpanel/forbidden.html', status=403)

@staff_or_super_required
def loadProductData(request):

    Product.objects.all().delete()

    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'b2c_products_500.csv')
    product_data = pd.read_csv(csv_path, encoding='latin-1')
    
    product_data_to_use = product_data

    for index, row in product_data_to_use.iterrows():
        new_product = Product(
            sku_code=row['SKU code'],
            product_name=row['Product name'],
            product_description=row['Product description'],
            product_category=row['Product Category'],
            product_subcategory=row['Product Subcategory'],
            quantity_on_hand=row['Quantity on hand'],
            unit_price=row['Unit price']
        )
        new_product.save()

    return HttpResponse("Data loaded successfully into the database.")

def adminLogin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'You do not have admin privileges.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'adminpanel/login.html')

@staff_or_super_required
def adminLogout(request):
    logout(request)

    return redirect('admin_login')

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'adminpanel/product.html'
    context_object_name = 'products'
    paginate_by = 10
    ordering = ['product_name']
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        ids = request.POST.getlist('selected')
        if not ids:
            messages.warning(request, "No products selected.")
            return redirect(request.path)

        qs = Product.objects.filter(pk__in=ids)
        active_qs = qs.filter(status__iexact='Active')
        inactive_count = qs.filter(status__iexact='Inactive').count()
        updated = active_qs.update(status='Inactive')

        if updated:
            messages.success(request, f"Marked {updated} product(s) inactive.")
        if inactive_count:
            messages.info(request, f"{inactive_count} product(s) were already inactive.")
        if not updated and not inactive_count:
            messages.info(request, "No matching products found.")

        return redirect(request.path)

    def get_paginate_by(self, queryset):
        page_size = self.request.GET.get('page_size', self.paginate_by)
        try:
            return int(page_size)
        except ValueError:
            return self.paginate_by

    def get_queryset(self):
        queryset = super().get_queryset()

        status = (self.kwargs.get('status') or 'all').lower()
        if status == 'active':
            queryset = queryset.filter(status__iexact='Active')
        elif status == 'inactive':
            queryset = queryset.filter(status__iexact='Inactive')

        search_query = self.request.GET.get('search', '')
        category = self.request.GET.get('category', '')
        subcategory = self.request.GET.get('subcategory', '')
        min_price = self.request.GET.get('min_price', '')
        max_price = self.request.GET.get('max_price', '')
        min_quantity = self.request.GET.get('min_quantity', '')
        max_quantity = self.request.GET.get('max_quantity', '')
        
        if search_query:
            queryset = queryset.filter(product_name__icontains=search_query)

        if category:
            queryset = queryset.filter(product_category=category)

        if subcategory:
            queryset = queryset.filter(product_subcategory=subcategory)

        if min_price:
            queryset = queryset.filter(unit_price__gte=min_price)

        if max_price:   
            queryset = queryset.filter(unit_price__lte=max_price)

        if min_quantity:
            queryset = queryset.filter(quantity_on_hand__gte=min_quantity)

        if max_quantity:   
            queryset = queryset.filter(quantity_on_hand__lte=max_quantity)

        order_by = self.request.GET.get('sort', None)
        direction = self.request.GET.get('dir', 'asc')

        if order_by in ['product_name', 'product_category', 'product_subcategory', 'quantity_on_hand', 'unit_price']:
            if direction == 'desc':
                order_by = f'-{order_by}'
            queryset = queryset.order_by(order_by)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['categories'] = Product.objects.values_list('product_category', flat=True).distinct().order_by('product_category')
        context['subcategories'] = Product.objects.values_list('product_subcategory', flat=True).distinct().order_by('product_subcategory')
        context['selected_status'] = (self.kwargs.get('status') or 'all').lower()
        if context.get("is_paginated"):
            context["total_products"] = context["page_obj"].paginator.count
        else:
            context["total_products"] = len(context["products"])

        ProductModel = self.model
        context['counts'] = {
            'all': ProductModel.objects.count(),
            'active': ProductModel.objects.filter(status__iexact='Active').count(),
            'inactive': ProductModel.objects.filter(status__iexact='Inactive').count(),
        }

        page_obj = context.get('page_obj')
        if page_obj:
            total = page_obj.paginator.num_pages
            current = page_obj.number
            window = 2  
            pages = []

            def add(num): 
                if num not in pages and 1 <= num <= total: 
                    pages.append(num)

            add(1)
            for n in range(current - window, current + window + 1):
                add(n)
            add(total)

            pages = sorted(pages)
            compact = []
            for i, num in enumerate(pages):
                if i == 0:
                    compact.append(num)
                    continue
                prev = pages[i - 1]
                if num - prev == 1:
                    compact.append(num)
                else:
                    compact.append('...')
                    compact.append(num)
            context['compact_page_range'] = compact

        return context

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'adminpanel/product_add.html'
    success_url = '/adminpanel/product/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Product created successfully.")
        return response

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'adminpanel/product_update.html'
    success_url = '/adminpanel/product/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Product updated successfully.")
        return response

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    success_url = '/adminpanel/product/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        product = self.get_object()
        previous_status = product.status
        product.status = 'Inactive' if product.status == 'Active' else 'Active'
        product.save(update_fields=['status'])
        if product.status == 'Inactive' and previous_status == 'Active':
            messages.success(request, f"Product '{product.product_name}' marked inactive.")
        elif product.status == 'Active' and previous_status == 'Inactive':
            messages.success(request, f"Product '{product.product_name}' reactivated.")
        return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        product = self.get_object()
        if product.status == 'Active':
            product.status = 'Inactive'
            product.save(update_fields=['status'])
            messages.success(request, f"Product '{product.product_name}' marked inactive.")
        else:
            messages.info(request, f"Product '{product.product_name}' is already inactive.")
        return redirect(self.success_url)

@staff_or_super_required
def bulkInsertProducts(request):

    REQUIRED_HEADERS = ['sku code', 'product name', 'product description', 'product category', 'product subcategory', 'quantity on hand', 'unit price']
    message = ''

    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            if not csv_file.name.endswith('.csv'):
                message = "Please upload a valid CSV file."
                return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message })

            try:
                csv_text = TextIOWrapper(csv_file.file, encoding='utf-8')
                df = pd.read_csv(csv_text)
                df.columns = df.columns.str.strip().str.lower()

                missing = [h for h in REQUIRED_HEADERS if h not in df.columns]
                if missing:
                    message = "Missing/Wrongly Spelled Header(s): " + ", ".join(missing)
                    return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message})

                str_cols = ['sku code', 'product name', 'product description', 'product category', 'product subcategory']
                for col in str_cols:
                    df[col] = df[col].astype(str).str.strip()

                if df[REQUIRED_HEADERS].isnull().any().any():
                    message = "There are null values in the CSV."
                    return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message})

                df['quantity on hand'] = pd.to_numeric(df['quantity on hand'], errors='raise').astype(int)
                df['unit price'] = pd.to_numeric(df['unit price'], errors='raise').astype(float)

                if (df['quantity on hand'] < 0).any() or (df['unit price'] < 0).any():
                    message = "Negative values found in quantity or price."
                    return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message})

                products = []
                for _, row in df.iterrows():
                    products.append(Product(
                        sku_code=row['sku code'],
                        product_name=row['product name'],
                        product_description=row['product description'],
                        product_category=row['product category'],
                        product_subcategory=row['product subcategory'],
                        quantity_on_hand=int(row['quantity on hand']),
                        unit_price=float(row['unit price']),
                        status='Active'
                    ))

                Product.objects.bulk_create(products)
                message = "Products uploaded successfully."
                return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message })

            except Exception as e:
                message = f"Error reading CSV file: {str(e)}"
                return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message })
    else:
        form = UploadCSVForm()

    return render(request, 'adminpanel/product_bulk_insert.html', {'form': form, 'message': message })

class OrderListView(LoginRequiredMixin, ListView):
    model = StorefrontOrder
    template_name = 'adminpanel/order.html'
    context_object_name = 'orders'
    paginate_by = 10 
    ordering = ['created_at'] 
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)
       
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = (self.request.GET.get('search') or '').strip()
        status = (self.kwargs.get('status') or 'all').lower()
        min_total = (self.request.GET.get('min_total') or '').strip()
        max_total = (self.request.GET.get('max_total') or '').strip()
        created_from = (self.request.GET.get('created_from') or '').strip()
        created_to = (self.request.GET.get('created_to') or '').strip()

        # Status filter
        if status == 'delivered':
            queryset = queryset.filter(status__iexact='delivered')
        elif status == 'shipped':
            queryset = queryset.filter(status__iexact='shipped')
        elif status == 'pending':
            queryset = queryset.filter(status__iexact='pending')
        elif status == 'cancelled':
            queryset = queryset.filter(status__iexact='cancelled')

        if search_query:
            q = (
                Q(customer__user__username__icontains=search_query) |
                Q(status__icontains=search_query)
            )
            if search_query.isdigit():
                q |= Q(id=int(search_query))
            queryset = queryset.filter(q)

        if min_total:
            try:
                queryset = queryset.filter(total_amount__gte=float(min_total))
            except ValueError:
                pass
        if max_total:
            try:
                queryset = queryset.filter(total_amount__lte=float(max_total))
            except ValueError:
                pass

        if created_from:
            cf = parse_date(created_from)
            if cf:
                queryset = queryset.filter(created_at__date__gte=cf)
        if created_to:
            ct = parse_date(created_to)
            if ct:
                queryset = queryset.filter(created_at__date__lte=ct)

        order_by = self.request.GET.get('sort', None)
        direction = self.request.GET.get('dir', 'asc')

        if order_by in ['id', 'customer', 'status', 'total_amount', 'created_at']:
            if direction == 'desc':
                order_by = f'-{order_by}'
            queryset = queryset.order_by(order_by)

        return queryset

    def get_paginate_by(self, queryset):
        page_size = self.request.GET.get('page_size', self.paginate_by)
        try:
            return int(page_size)
        except ValueError:
            return self.paginate_by
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['selected_status'] = (self.kwargs.get('status') or 'all').lower()
        context['min_total'] = self.request.GET.get('min_total', '')
        context['max_total'] = self.request.GET.get('max_total', '')
        context['created_from'] = self.request.GET.get('created_from', '')
        context['created_to'] = self.request.GET.get('created_to', '')
        
        OrderModel = self.model
        context['counts'] = {
            'all': OrderModel.objects.count(),
            'delivered': OrderModel.objects.filter(status__iexact='Delivered').count(),
            'pending': OrderModel.objects.filter(status__iexact='Pending').count(),
            'shipped': OrderModel.objects.filter(status__iexact='Shipped').count(),
            'cancelled': OrderModel.objects.filter(status__iexact='Cancelled').count(),
        }

        page_obj = context.get('page_obj')
        if page_obj:
            total = page_obj.paginator.num_pages
            current = page_obj.number
            window = 2  
            pages = []

            def add(num): 
                if num not in pages and 1 <= num <= total: 
                    pages.append(num)

            add(1)
            for n in range(current - window, current + window + 1):
                add(n)
            add(total)

            pages = sorted(pages)
            compact = []
            for i, num in enumerate(pages):
                if i == 0:
                    compact.append(num)
                    continue
                prev = pages[i - 1]
                if num - prev == 1:
                    compact.append(num)
                else:
                    compact.append('...')
                    compact.append(num)
            context['compact_page_range'] = compact

        return context
    
class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'adminpanel/user.html'
    context_object_name = 'users'
    paginate_by = 10 
    login_url = 'admin_login'
    ordering = ['id']

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)
       
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '').lower().strip()
        role = self.kwargs.get('role') 

        if role == 'admin':
            queryset = queryset.filter(is_staff=True)
        elif role == 'customer':
            queryset = queryset.filter(is_staff=False)

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query)
            )

        joined_from = parse_date(self.request.GET.get('joined_from') or '')
        joined_to   = parse_date(self.request.GET.get('joined_to') or '')
        login_from  = parse_date(self.request.GET.get('login_from') or '')
        login_to    = parse_date(self.request.GET.get('login_to') or '')

        if joined_from:
            queryset = queryset.filter(date_joined__date__gte=joined_from)
        if joined_to:
            queryset = queryset.filter(date_joined__date__lte=joined_to)

        if login_from:
            queryset = queryset.filter(last_login__date__gte=login_from)
        if login_to:
            queryset = queryset.filter(last_login__date__lte=login_to)

        order_by = self.request.GET.get('sort', None)
        direction = self.request.GET.get('dir', 'asc')

        if order_by == 'status':
            queryset = queryset.order_by('-is_active' if direction != 'desc' else 'is_active')
        elif order_by in ['username', 'first_name', 'last_name', 'email', 'date_joined']:
            if direction == 'desc':
                order_by = f'-{order_by}'
            queryset = queryset.order_by(order_by)

        return queryset

    def get_paginate_by(self, queryset):
        page_size = self.request.GET.get('page_size', self.paginate_by)
        try:
            return int(page_size)
        except ValueError:
            return self.paginate_by
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['joined_from'] = self.request.GET.get('joined_from', '')
        context['joined_to'] = self.request.GET.get('joined_to', '')
        context['login_from'] = self.request.GET.get('login_from', '')
        context['login_to'] = self.request.GET.get('login_to', '')

        role = self.kwargs.get('role')  
        if role == 'admin':
            selected = 'admin'
        elif role == 'customer':
            selected = 'customer'
        else:
            selected = 'all'
        context['selected_tab'] = selected
        
        UserModel = self.model
        context['counts'] = {
            'all': UserModel.objects.count(),
            'admin': UserModel.objects.filter(is_staff=True).count(),
            'customer': UserModel.objects.filter(is_staff=False).count(),
        }

        context['users'] = context['object_list']

        page_obj = context.get('page_obj')
        if page_obj:
            total = page_obj.paginator.num_pages
            current = page_obj.number
            window = 2
            pages = []

            def add(num): 
                if num not in pages and 1 <= num <= total: 
                    pages.append(num)

            add(1)
            for n in range(current - window, current + window + 1):
                add(n)
            add(total)

            pages = sorted(pages)
            compact = []
            for i, num in enumerate(pages):
                if i == 0:
                    compact.append(num)
                    continue
                prev = pages[i - 1]
                if num - prev == 1:
                    compact.append(num)
                else:
                    compact.append('...')
                    compact.append(num)
            context['compact_page_range'] = compact

        return context

class AdminCreateView(LoginRequiredMixin, CreateView):
    model = User
    form_class = CreateAdminForm
    template_name = 'adminpanel/user_admin_add.html'
    success_url = '/adminpanel/user/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        
        if not request.user.is_authenticated:
            return redirect(self.login_url)
        
        if not request.user.is_superuser and request.user.is_authenticated:
            return redirect('user')
    
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Admin user created successfully.")
        return response

class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = User
    form_class = CustomerCreateForm
    template_name = 'adminpanel/user_customer_add.html'
    success_url = '/adminpanel/user/customer'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Customer created successfully.")
        return super().form_valid(form)

class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    success_url = '/adminpanel/user/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        target = self.get_object()
        actor = request.user

        if target.pk == actor.pk:
            messages.error(request, "You cannot delete your own account.")
            return redirect(self.success_url)

        if actor.is_superuser:
            target.delete()
            messages.success(request, f"Deleted user '{target.username}'.")
            return redirect(self.success_url)

        if actor.is_staff and not actor.is_superuser:
            if target.is_staff or target.is_superuser:
                messages.error(request, "Admins can only delete customer accounts.")
                return redirect(self.success_url)
            target.delete()
            messages.success(request, f"Deleted customer '{target.username}'.")
            return redirect(self.success_url)

        messages.error(request, "You do not have permission to delete this user.")
        return redirect(self.success_url)

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
    
class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'adminpanel/user_update.html'
    success_url = '/adminpanel/user/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)

        actor = request.user
        try:
            target = User.objects.get(pk=kwargs.get('pk'))
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('user')

        if actor.is_superuser:
            allowed = (not target.is_superuser) or (target.pk == actor.pk)
        else:  
            allowed = (target.pk == actor.pk) or (not target.is_staff and not target.is_superuser)

        if not allowed:
            messages.error(request, "You do not have permission to edit this user.")
            return redirect('user')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from_flag = self.request.GET.get('from') or self.request.POST.get('from')
        is_self = (self.request.user.is_authenticated and self.object.pk == self.request.user.pk)
        if is_self or from_flag == 'profile':
            messages.success(self.request, "Profile updated successfully.")
        else:
            messages.success(self.request, "User updated successfully.", extra_tags='user-update-popup')
        return super().form_valid(form)

    def get_success_url(self):
        req = self.request
        from_flag = req.GET.get('from') or req.POST.get('from')
        referer = (req.META.get('HTTP_REFERER') or '')
        is_self = (self.object.pk == req.user.pk)

        try:
            if from_flag == 'profile' or ('/profile' in referer and is_self):
                return reverse('profile')
            return reverse('user')
        except Exception:
            return self.success_url

    def get_template_names(self):
        req = self.request
        from_flag = req.GET.get('from') or req.POST.get('from')
        obj = getattr(self, 'object', None)
        if obj is None:
            try:
                obj = self.get_object()
            except Exception:
                obj = None
        is_self = (obj and req.user.is_authenticated and obj.pk == req.user.pk)
        if from_flag == 'profile' or (is_self and 'profile' in (req.META.get('HTTP_REFERER') or '')):
            return ['adminpanel/profile_update.html']
        return ['adminpanel/user_update.html']
    
@staff_or_super_required
def profile(request):
    return render( request, 'adminpanel/profile.html', {"user_obj": request.user})

class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'adminpanel/user_change_password.html'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)

        target_pk = kwargs.get('pk')
        if target_pk != request.user.pk:
            messages.error(request, "You can only change your own password.")
            return redirect('user' if request.user.is_superuser else 'profile')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Password updated successfully.")
        return response

    def get_success_url(self):
        from_flag = self.request.GET.get('from') or self.request.POST.get('from')
        if from_flag == 'profile':
            return reverse('profile')
        return reverse('user') if self.request.user.is_superuser else reverse('profile')

@staff_or_super_required
def customer_orders(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('user')

    customer = Customer.objects.select_related('user').filter(user=user).first()

    orders_qs = (
        StorefrontOrder.objects.filter(customer=customer)
        .prefetch_related('order_items', 'order_items__product')
        .order_by('-created_at')
    )

    orders = []
    for o in orders_qs:
        items = []
        for it in o.order_items.all():
            unit = float(it.price_at_purchase)
            qty = int(it.quantity)
            items.append({
                'name': getattr(it.product, 'product_name', 'Item'),
                'qty': qty,
                'unit': unit,
                'total': round(unit * qty, 2),
            })
        orders.append({
            'id': o.id,
            'status': o.status,
            'created_at': o.created_at,
            'total_amount': float(o.total_amount),
            'items': items,
        })

    return render(request, 'adminpanel/user_customer_orders.html', {
        'target_user': user,
        'customer': customer,
        'orders': orders,
    })

class OrderUpdateView(LoginRequiredMixin, UpdateView):
    model = StorefrontOrder
    form_class = OrderForm
    template_name = 'adminpanel/order_update.html'
    success_url = '/adminpanel/order/'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Order updated successfully.")
        return response

    def get_queryset(self):
        return super().get_queryset().prefetch_related("order_items", "order_items__product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = context["object"]
        items = []
        subtotal = 0.0
        for it in order.order_items.all():
            unit = float(it.price_at_purchase)
            qty = int(it.quantity)
            total = round(unit * qty, 2)
            subtotal += total
            items.append({
                "name": getattr(it.product, "product_name", "Item"),
                "qty": qty,
                "unit": unit,
                "total": total,
            })
        context["items"] = items
        context["subtotal"] = round(subtotal, 2)
        return context

class OrderDetailView(LoginRequiredMixin, DetailView):
    model = StorefrontOrder
    template_name = 'adminpanel/order_view.html'
    context_object_name = 'order'
    login_url = 'admin_login'

    def dispatch(self, request, *args, **kwargs):
        if not staff_or_super(request.user):
            if request.user.is_authenticated:
                return redirect('forbidden')
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().prefetch_related("order_items", "order_items__product", "customer__user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = context["object"]
        items = []
        subtotal = 0.0
        for it in order.order_items.all():
            unit = float(it.price_at_purchase)
            qty = int(it.quantity)
            total = round(unit * qty, 2)
            subtotal += total
            items.append({
                "name": getattr(it.product, "product_name", "Item"),
                "qty": qty,
                "unit": unit,
                "total": total,
            })
        context["items"] = items
        context["subtotal"] = round(subtotal, 2)
        return context

@staff_or_super_required
def dashboard(request):
    today = timezone.localdate()
    current_year = today.year
    start_str = (request.GET.get('start') or '').strip()
    end_str   = (request.GET.get('end') or '').strip()

    start_date = parse_date(start_str) if start_str else date(current_year, 1, 1)
    end_date   = parse_date(end_str) if end_str else date(current_year, 12, 31)

    if not start_date:
        start_date = date(current_year, 1, 1)
    if not end_date:
        end_date = date(current_year, 12, 31)
    if end_date < start_date:
        start_date, end_date = end_date, start_date  

    if end_date > today:
        end_date = today

    base_qs = StorefrontOrder.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    total_orders = base_qs.count()
    total_revenue_val = base_qs.aggregate(s=Sum('total_amount'))['s'] or 0
    kpi_total_revenue = f"${total_revenue_val:,.2f}"

    total_customers = Customer.objects.count()  

    monthly_qs = (
        base_qs.annotate(month=TruncMonth('created_at'))
               .values('month')
               .annotate(total_sales=Sum('total_amount'))
               .order_by('month')
    )
    df = pd.DataFrame(monthly_qs)

    def month_iter(start_d: date, end_d: date):
        cursor = date(start_d.year, start_d.month, 1)
        last = date(end_d.year, end_d.month, 1)
        while cursor <= last:
            yield cursor
            y = cursor.year + (cursor.month == 12)
            m = 1 if cursor.month == 12 else cursor.month + 1
            cursor = date(y, m, 1)

    span_months = list(month_iter(start_date, end_date))
    month_labels = []
    single_year = (start_date.year == end_date.year)
    for d in span_months:
        lbl = d.strftime('%b') if single_year else d.strftime('%b %Y')
        month_labels.append(lbl)

    totals = [0.0] * len(span_months)
    if not df.empty:
        for _, r in df.iterrows():
            m_dt = r['month']
            if pd.notna(m_dt):
                key = date(m_dt.year, m_dt.month, 1)
                try:
                    idx = span_months.index(key)
                    totals[idx] += float(r['total_sales'] or 0)
                except ValueError:
                    pass

    months_with_data = [i for i, v in enumerate(totals) if v > 0]
    if months_with_data:
        highlight_idx = max(months_with_data)
    else:
        current_month_key = date(today.year, today.month, 1)
        try:
            highlight_idx = span_months.index(current_month_key)
        except ValueError:
            highlight_idx = len(span_months) - 1 if span_months else 0

    highlight_value = totals[highlight_idx] if totals else 0
    colors = ['#e5e7eb'] * len(totals)
    if colors:
        colors[highlight_idx] = '#2563eb'

    fig = go.Figure(data=[
        go.Bar(
            x=month_labels,
            y=totals,
            marker_color=colors,
            hovertemplate='$%{y:,.0f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hoverlabel=dict(bgcolor='#111827', font_color='#ffffff', bordercolor='#111827'),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, tickfont=dict(color='#6b7280')),
        yaxis=dict(visible=False)
    )

    graph_html = pio.to_html(fig, full_html=False)

    revenue_expr = ExpressionWrapper(
        F('price_at_purchase') * F('quantity'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )
    top_products_qs = (
        OrderItems.objects.filter(
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date
        )
        .annotate(line_revenue=revenue_expr)
        .values('product__id', 'product__product_name')
        .annotate(total_revenue=Sum('line_revenue'), total_quantity=Sum('quantity'))
        .order_by('-total_revenue')[:10]
    )
    top_products = list(top_products_qs)

    return render(request, 'adminpanel/dashboard.html', {
        'graph_html': graph_html,
        'kpi_total_revenue': kpi_total_revenue,
        'kpi_total_orders': total_orders,
        'kpi_total_customers': total_customers,
        'kpi_year': current_year,
        'top_products': top_products,
        'filter_start': start_date.strftime('%Y-%m-%d'),
        'filter_end': end_date.strftime('%Y-%m-%d'),
        'range_active': True if (start_str or end_str) else False,
    })