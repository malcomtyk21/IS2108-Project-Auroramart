from django.db import models

# Create your models here.
class Product(models.Model):
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    sku_code = models.CharField(max_length=100, blank=False)
    product_name = models.CharField(max_length=255, blank=False)
    product_description = models.TextField(blank=False)
    product_category = models.CharField(max_length=255, blank=False)
    product_subcategory = models.CharField(max_length=255, blank=False)
    quantity_on_hand = models.IntegerField(blank=False)
    unit_price = models.FloatField(blank=False)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='Active')
    image = models.ImageField(upload_to='products/', null=True, blank=True)
