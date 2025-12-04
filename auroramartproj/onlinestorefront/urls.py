from django.contrib import admin
from django.urls import path
from . import views

app_name = 'onlinestorefront'

urlpatterns = [
    path('', views.index, name='index'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('category/<str:category>/', views.category, name='category'),
    path('category/<str:category>/<str:subcategory>/', views.subcategory, name='subcategory'),
    path('search/', views.search, name='search'),
    path('register/', views.Register.as_view(), name='register'),
    path('storeLogin/', views.StoreLogin.as_view(), name='storeLogin'),
    path('storeLogout/', views.StoreLogout.as_view(), name='storeLogout'),
    path('forbidden/', views.forbidden, name='store_forbidden'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    # Cart
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/<int:product_id>/', views.AddToCartView.as_view(), name='cart_add'),
    path('cart/item/<int:item_id>/update/', views.UpdateCartItemView.as_view(), name='cart_item_update'),
    path('cart/item/<int:item_id>/remove/', views.RemoveCartItemView.as_view(), name='cart_item_remove'),
    path('cart/checkout/', views.CheckoutView.as_view(), name='checkout'),
    # Orders
    path('orders/', views.OrdersListView.as_view(), name='orders'),
    path('orders/<int:pk>/', views.OrdersDetailView.as_view(), name='order_detail'),
]