from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Customer(models.Model):
	GENDER_CHOICES = [
		("Male", "Male"),
		("Female", "Female"),
	]
	EMPLOYMENT_CHOICES = [
		("Full-time", "Full-time"),
		("Part-time", "Part-time"),
		("Retired", "Retired"),
		("Self-employed", "Self-employed"),
		("Student", "Student"),
	]
	OCCUPATION_CHOICES = [
		("Admin", "Admin"),
		("Education", "Education"),
		("Sales", "Sales"),
		("Service", "Service"),
		("Skilled Trades", "Skilled Trades"),
		("Tech", "Tech"),
	]
	EDUCATION_CHOICES = [
		("Secondary", "Secondary"),
		("Diploma", "Diploma"),
		("Bachelor", "Bachelor"),
		("Master", "Master"),
		("Doctorate", "Doctorate"),
	]

	user = models.OneToOneField(User, on_delete=models.RESTRICT, related_name="profile")
	age = models.PositiveIntegerField(null=True, blank=True)
	gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
	employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, blank=True)
	occupation = models.CharField(max_length=20, choices=OCCUPATION_CHOICES, blank=True)
	education = models.CharField(max_length=20, choices=EDUCATION_CHOICES, blank=True)
	household_size = models.PositiveIntegerField(null=True, blank=True)
	has_children = models.BooleanField(default=False)
	monthly_income_sgd = models.FloatField(null=True, blank=True)
	preferred_category = models.CharField(max_length=100, blank=True)  # predicted value stored


class Cart(models.Model):
	user = models.OneToOneField(User, on_delete=models.RESTRICT, related_name="cart")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
	cart = models.ForeignKey(Cart, on_delete=models.RESTRICT, related_name="items")
	product = models.ForeignKey("adminpanel.Product", on_delete=models.RESTRICT, related_name="cart_items")
	quantity = models.PositiveIntegerField(default=1)


class Order(models.Model):
	STATUS = [
		("pending", "Pending"),
		("shipped", "Shipped"),
		("delivered", "Delivered"),
		("cancelled", "Cancelled"),
	]
	
	total_amount = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS, default='pending')
	created_at = models.DateTimeField(auto_now_add=True)
	customer = models.ForeignKey('onlinestorefront.Customer', on_delete=models.PROTECT, related_name='orders')

	# Payment snapshot (immutable copy captured at order creation)
	card_last4 = models.CharField(max_length=4, blank=True)
	card_brand = models.CharField(max_length=50, blank=True)
	expiry_month = models.PositiveIntegerField(null=True, blank=True)
	expiry_year = models.PositiveIntegerField(null=True, blank=True)
	cardholder_name = models.CharField(max_length=100, blank=True)
	billing_address = models.TextField(blank=True)

	# Shipping snapshot (immutable copy captured at order creation)
	shipping_address_line1 = models.CharField(max_length=255, blank=True)
	shipping_address_line2 = models.CharField(max_length=255, blank=True)
	shipping_city = models.CharField(max_length=100, blank=True)
	shipping_state = models.CharField(max_length=100, blank=True)
	shipping_postal_code = models.CharField(max_length=20, blank=True)
	shipping_country = models.CharField(max_length=100, blank=True)
	shipping_contact_number = models.CharField(max_length=20, blank=True)


class OrderItems(models.Model):
    order = models.ForeignKey(Order, on_delete=models.RESTRICT, related_name="order_items")
    product = models.ForeignKey("adminpanel.Product", on_delete=models.RESTRICT)
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)


class PaymentInformation(models.Model):
	card_last4 = models.CharField(max_length=4)
	card_brand = models.CharField(max_length=50)
	expiry_month = models.CharField(max_length=2)
	expiry_year = models.CharField(max_length=4)
	cardholder_name = models.CharField(max_length=100)
	billing_address = models.TextField()
	customer = models.ForeignKey("onlinestorefront.Customer", on_delete=models.RESTRICT, related_name="payments", default=None)


class ShippingInformation(models.Model):
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=6)
    country = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=8)
    customer = models.ForeignKey("onlinestorefront.Customer", on_delete=models.RESTRICT, related_name="shippings", default=None)