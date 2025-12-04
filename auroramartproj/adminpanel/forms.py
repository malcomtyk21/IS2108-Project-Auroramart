from django import forms
from.models import Product
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from onlinestorefront.models import Order as StorefrontOrder

class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        fields = ['sku_code', 'product_name', 'product_description', 'product_category', 'product_subcategory', 'quantity_on_hand', 'unit_price', 'status', 'image']
        labels = {
            'sku_code': 'SKU Code',
            'product_name': 'Product Name',
            'product_description': 'Product Description',
            'product_category': 'Product Category',
            'product_subcategory': 'Product Subcategory',
            'quantity_on_hand': 'Quantity on Hand',
            'unit_price': 'Unit Price',
            'image': 'Product Image'
        }
        widgets = {
            'status': forms.Select(attrs={'class': 'select'}),
        }

class UploadCSVForm(forms.Form):
    
    csv_file = forms.FileField(label='Select a CSV file')

class BaseUserCreateForm(UserCreationForm):

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "username",
            "email": "user@example.com",
            "first_name": "First name",
            "last_name": "Last name",
            "password1": "Password",
            "password2": "Confirm password",
        }
        for name, ph in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("placeholder", ph)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email already in use.")
        return email

class CreateAdminForm(BaseUserCreateForm):

    ROLE_CHOICES = (("admin", "Admin"), ("superadmin", "Superadmin"))
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    class Meta(BaseUserCreateForm.Meta):
        fields = ("username", "email", "first_name", "last_name", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].widget.attrs.setdefault("class", "select")
        self.fields["role"].widget.attrs.setdefault("aria-label", "Role")

    def save(self, commit=True):
        user = super().save(commit=False)
        selected_role = self.cleaned_data.get("role")
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_staff = True
        user.is_superuser = (selected_role == "superadmin")
        if commit:
            user.save()
        return user

class CustomerCreateForm(BaseUserCreateForm):

    def save(self, commit=True):
        user = super().save(commit=False)  
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user
    
class UserUpdateForm(forms.ModelForm):

    is_active = forms.TypedChoiceField(
        label="Status",
        choices=((True, "Active"), (False, "Inactive")),
        coerce=lambda x: True if x in [True, "True", "true", "1", 1] else False,
        widget=forms.Select(attrs={"class": "select"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]

class OrderForm(forms.ModelForm):

    class Meta:
        model = StorefrontOrder
        fields = ["status"]
        labels = {"status": "Order Status"}
        widgets = {
            "status": forms.Select(attrs={"class": "select"}),
        }