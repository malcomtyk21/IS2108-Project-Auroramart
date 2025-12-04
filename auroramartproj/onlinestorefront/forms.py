from django import forms
from .models import Customer
from datetime import datetime
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class BasicRegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Required.",
    )
    first_name = forms.CharField(max_length=100, help_text="Required.")
    last_name = forms.CharField(max_length=100, help_text="Required.")

    class Meta(UserCreationForm.Meta):
        model = User
        # add extra fields that exist in the default django User model
        fields = ("username", "email", "first_name", "last_name")

    def save(self, commit=True):
        # the default save method only saves username and hashed pw
        user = super().save(commit=False)  # commit=False to avoid saving yet

        # add the extra fields
        user.email = self.cleaned_data.get("email")
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")

        if commit:
            user.save()
        return user

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "age",
            "gender",
            "employment_status",
            "occupation",
            "education",
            "household_size",
            "has_children",
            "monthly_income_sgd",
        ]  # preferred_category is computed, not user-editable

    def clean(self):
        cleaned = super().clean()

        # Age: if provided, must be positive and reasonable
        age = cleaned.get("age")
        if age is not None:
            try:
                a = int(age)
                if a <= 0:
                    self.add_error("age", "Age must be a positive number.")
                elif a > 120:
                    self.add_error("age", "Age seems too large.")
            except (TypeError, ValueError):
                self.add_error("age", "Age must be a whole number.")

        # Household size: if provided, must be positive
        hs = cleaned.get("household_size")
        if hs is not None:
            try:
                h = int(hs)
                if h <= 0:
                    self.add_error("household_size", "Household size must be a positive number.")
            except (TypeError, ValueError):
                self.add_error("household_size", "Household size must be a whole number.")

        # Monthly income: if provided, must be non-negative
        mi = cleaned.get("monthly_income_sgd")
        if mi is not None:
            try:
                mival = float(mi)
                if mival < 0:
                    self.add_error("monthly_income_sgd", "Monthly income cannot be negative.")
            except (TypeError, ValueError):
                self.add_error("monthly_income_sgd", "Monthly income must be a number.")

        return cleaned


class AccountParticularsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username
        qs = User.objects.exclude(pk=getattr(self.instance, "pk", None)).filter(username=username)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email
        qs = User.objects.exclude(pk=getattr(self.instance, "pk", None)).filter(email=email)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class PaymentInformationForm(forms.ModelForm):
    class Meta:
        from .models import PaymentInformation
        model = PaymentInformation
        # Exclude customer and sensitive/backend-only fields; card_number is collected
        # on the form but not stored directly on the model.
        exclude = ["customer", "card_last4", "payment_token"]
        widgets = {
            "billing_address": forms.Textarea(attrs={"rows": 3}),
        }

    # Accept the full card number from the user, validate it, and only store the last 4 digits.
    card_number = forms.CharField(
        required=True,
        max_length=16,
        label="Card Number",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "1234567890123456", "maxlength": "16"}),
        help_text="Enter 16-digit card number. Only last 4 digits will be saved.",
    )

    def clean_card_number(self):
        val = (self.cleaned_data.get("card_number") or "").replace(" ", "")
        if not val.isdigit():
            raise forms.ValidationError("Card number must contain only digits.")
        if len(val) != 16:
            raise forms.ValidationError("Card number must be 16 digits.")

        # Luhn check
        def luhn_check(number: str) -> bool:
            total = 0
            reverse_digits = number[::-1]
            for i, ch in enumerate(reverse_digits):
                d = int(ch)
                if i % 2 == 1:
                    d *= 2
                    if d > 9:
                        d -= 9
                total += d
            return total % 10 == 0

        if not luhn_check(val):
            raise forms.ValidationError("Card number failed validation. Please check digits.")

        return val

    # Restrict card brand choices to Visa and Mastercard for demo purposes
    CARD_BRAND_CHOICES = [
        ("Visa", "Visa"),
        ("Mastercard", "Mastercard"),
    ]

    card_brand = forms.ChoiceField(
        choices=CARD_BRAND_CHOICES,
        required=True,
        label="Card Brand",
    )

    # Expiry fields and cardholder name (model fields are present via ModelForm but
    # we expose them explicitly for clearer widgets and validation)
    expiry_month = forms.CharField(
        required=True,
        max_length=2,
        label="Expiry Month",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "MM", "maxlength": "2"}),
    )

    expiry_year = forms.CharField(
        required=True,
        max_length=4,
        label="Expiry Year",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "YYYY", "maxlength": "4", "minlength": "4", "pattern": "\\d{4}"}),
    )

    cardholder_name = forms.CharField(required=True, max_length=100, label="Cardholder Name")

    def clean(self):
        cleaned = super().clean()

        # Cardholder name
        name = cleaned.get("cardholder_name")
        if not name:
            self.add_error("cardholder_name", "Cardholder name is required.")
        elif len(name) > 100:
            self.add_error("cardholder_name", "Cardholder name is too long.")

        # Billing address required (model field is required)
        billing = cleaned.get("billing_address")
        if not billing or not str(billing).strip():
            self.add_error("billing_address", "Billing address is required.")

        # Expiry month/year validation
        em = (cleaned.get("expiry_month") or "").strip()
        ey = (cleaned.get("expiry_year") or "").strip()
        if not em or not ey:
            self.add_error("expiry_month", "Expiry month and year are required.")
            self.add_error("expiry_year", "Expiry month and year are required.")
            return cleaned

        # parse month/year
        try:
            m = int(em)
        except (TypeError, ValueError):
            self.add_error("expiry_month", "Expiry month must be a number (1-12).")
            return cleaned
        try:
            y = int(ey)
        except (TypeError, ValueError):
            self.add_error("expiry_year", "Expiry year must be a number (e.g. 2026).")
            return cleaned

        # Enforce 4-digit year (e.g. 2025)
        if len(ey) != 4:
            self.add_error("expiry_year", "Expiry year must be 4 digits, e.g. 2025.")
            return cleaned

        if not (1 <= m <= 12):
            self.add_error("expiry_month", "Expiry month must be between 1 and 12.")
            return cleaned

        now = datetime.utcnow()
        # card is valid through the end of the expiry month; compare (year, month)
        if (y, m) < (now.year, now.month):
            self.add_error("expiry_month", "Card has expired.")

        return cleaned


class ShippingInformationForm(forms.ModelForm):
    class Meta:
        from .models import ShippingInformation
        model = ShippingInformation
        # Exclude customer; it is set from the logged-in user
        exclude = ["customer"]
        widgets = {
            "address_line2": forms.TextInput(attrs={"placeholder": "Apartment, suite, unit (optional)"}),
        }

    def clean(self):
        cleaned = super().clean()

        # Address line1 required
        addr1 = cleaned.get("address_line1")
        if not addr1 or not str(addr1).strip():
            self.add_error("address_line1", "Address line 1 is required.")

        # City/state/country required
        for field in ("city", "state", "country"):
            val = cleaned.get(field)
            if not val or not str(val).strip():
                self.add_error(field, f"{field.replace('_', ' ').title()} is required.")

        # Postal code validation (expect numeric, length 6)
        postal = (cleaned.get("postal_code") or "").strip()
        if not postal:
            self.add_error("postal_code", "Postal code is required.")
        else:
            if not postal.isdigit():
                self.add_error("postal_code", "Postal code must contain only digits.")
            if len(postal) != 6:
                self.add_error("postal_code", "Postal code must be 6 digits.")

        # Contact number validation (numeric, length 8)
        contact = (cleaned.get("contact_number") or "").strip()
        if not contact:
            self.add_error("contact_number", "Contact number is required.")
        else:
            if not contact.isdigit():
                self.add_error("contact_number", "Contact number must contain only digits.")
            if len(contact) != 8:
                self.add_error("contact_number", "Contact number must be 8 digits.")

        return cleaned
