from django.contrib import admin
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('forbidden/', views.forbidden, name='forbidden'),
    path('', views.adminLogin, name='admin_login'),
    path('logout/', views.adminLogout, name='admin_logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('product/', views.ProductListView.as_view(), name='product'),
    path('product/active/', views.ProductListView.as_view(), {'status': 'active'}, name='product_active'),
    path('product/inactive/', views.ProductListView.as_view(), {'status': 'inactive'}, name='product_inactive'),
    path('product/add/', views.ProductCreateView.as_view(), name='product_add'),
    path('product/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('product/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('loadProductData/', views.loadProductData, name='load_product_data'),
    path('product/bulkInsert/', views.bulkInsertProducts, name='bulk_insert_products'),
    path('order/', views.OrderListView.as_view(), name='order'),
    path('order/delivered/', views.OrderListView.as_view(), {'status': 'Delivered'}, name='order_delivered'),
    path('order/pending/', views.OrderListView.as_view(), {'status': 'Pending'}, name='order_pending'),
    path('order/cancelled/', views.OrderListView.as_view(), {'status': 'Cancelled'}, name='order_cancelled'),
    path('order/shipped/', views.OrderListView.as_view(), {'status': 'Shipped'}, name='order_shipped'),
    path('order/<int:pk>/', views.OrderDetailView.as_view(), name='order_view'),
    path('order/<int:pk>/edit/', views.OrderUpdateView.as_view(), name='order_edit'),
    path('user/', views.UserListView.as_view(), name='user'),
    path('user/admin', views.UserListView.as_view(), {'role': 'admin'}, name='user_admin'),
    path('user/customer', views.UserListView.as_view(), {'role': 'customer'}, name='user_customer'),
    path('user/admin/add/', views.AdminCreateView.as_view(), name='user_admin_add'),
    path('user/customer/add/', views.CustomerCreateView.as_view(), name='user_customer_add'),
    path('user/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('user/<int:pk>/change-password/', views.UserPasswordChangeView.as_view(), name='user_change_password'),
    path('user/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('user/customer/<int:pk>/orders/', views.customer_orders, name='user_customer_orders'),
    path('profile/', views.profile, name='profile'),
]

handler403 = 'adminpanel.views.forbidden'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)