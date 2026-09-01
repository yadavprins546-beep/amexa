import re
from datetime import date

from django import forms

from .models import (
    Address,
    DeliveryPartnerProfile,
    Shop,
    ShopkeeperProfile,
)


# =========================================================
# SHARED DELIVERY ONBOARDING VALIDATION
# =========================================================

ALLOWED_DOCUMENT_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024


def validate_onboarding_file(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise forms.ValidationError(
            "Only JPG, JPEG, PNG or PDF files are allowed."
        )

    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise forms.ValidationError(
            "File size must be 5 MB or less."
        )

    return uploaded_file


def validate_onboarding_image(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension not in {"jpg", "jpeg", "png"}:
        raise forms.ValidationError(
            "Only JPG, JPEG or PNG images are allowed."
        )

    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise forms.ValidationError(
            "Image size must be 5 MB or less."
        )

    return uploaded_file


def normalize_indian_phone(phone):
    phone = str(phone or "").strip().replace(" ", "").replace("-", "")

    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    if not phone.isdigit() or len(phone) != 10:
        raise forms.ValidationError(
            "Please enter a valid 10 digit mobile number."
        )

    return phone


# =========================================================
# LOGIN FORM
# =========================================================

class LoginForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        required=False,
        label="Your name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Your name",
                "autocomplete": "name",
            }
        ),
    )

    phone = forms.CharField(
        max_length=15,
        label="Mobile number",
        widget=forms.TextInput(
            attrs={
                "placeholder": "10 digit mobile number",
                "inputmode": "numeric",
                "autocomplete": "tel",
            }
        ),
    )

    otp_code = forms.CharField(
        max_length=6,
        required=False,
        label="OTP code",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter OTP",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )

    def clean_phone(self):
        return normalize_indian_phone(self.cleaned_data["phone"])


# =========================================================
# ADDRESS FORM
# =========================================================

class AddressForm(forms.ModelForm):

    class Meta:
        model = Address

        fields = [
            "full_name",
            "mobile",
            "address_line",
            "city",
            "state",
            "pincode",
            "latitude",
            "longitude",
            "address_type",
            "is_default",
        ]

        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "placeholder": "Full name",
                    "autocomplete": "name",
                }
            ),
            "mobile": forms.TextInput(
                attrs={
                    "placeholder": "10 digit mobile number",
                    "inputmode": "numeric",
                    "autocomplete": "tel",
                    "maxlength": "10",
                }
            ),
            "address_line": forms.TextInput(
                attrs={
                    "placeholder": (
                        "House no, building, street, "
                        "area or landmark"
                    ),
                    "autocomplete": "street-address",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "placeholder": "City",
                    "autocomplete": "address-level2",
                }
            ),
            "state": forms.TextInput(
                attrs={
                    "placeholder": "State",
                    "autocomplete": "address-level1",
                }
            ),
            "pincode": forms.TextInput(
                attrs={
                    "placeholder": "6 digit pincode",
                    "inputmode": "numeric",
                    "autocomplete": "postal-code",
                    "maxlength": "6",
                }
            ),
            "latitude": forms.HiddenInput(attrs={"id": "id_latitude"}),
            "longitude": forms.HiddenInput(attrs={"id": "id_longitude"}),
            "address_type": forms.Select(),
            "is_default": forms.CheckboxInput(),
        }

    def clean_mobile(self):
        return normalize_indian_phone(self.cleaned_data["mobile"])

    def clean_pincode(self):
        pincode = self.cleaned_data["pincode"].strip()

        if not pincode.isdigit() or len(pincode) != 6:
            raise forms.ValidationError(
                "Pincode must be 6 digits."
            )

        return pincode

    def clean_latitude(self):
        latitude = self.cleaned_data.get("latitude")
        return 0 if latitude is None else latitude

    def clean_longitude(self):
        longitude = self.cleaned_data.get("longitude")
        return 0 if longitude is None else longitude


# =========================================================
# DELIVERY ONBOARDING — STEP 1: PERSONAL DETAILS
# =========================================================

class DeliveryPersonalDetailsForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        label="Full name",
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    phone = forms.CharField(
        max_length=15,
        label="Mobile number",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "tel",
                "maxlength": "10",
            }
        ),
    )

    class Meta:
        model = DeliveryPartnerProfile
        fields = [
            "profile_photo",
            "date_of_birth",
            "full_address",
            "city",
            "state",
            "pincode",
            "emergency_contact_name",
            "emergency_contact_phone",
            "vehicle_type",
            "vehicle_number",
        ]
        widgets = {
            "profile_photo": forms.FileInput(
                attrs={
                    "accept": "image/jpeg,image/png",
                    "capture": "user",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"}
            ),
            "full_address": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Full residential address and landmark",
                }
            ),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "state": forms.TextInput(attrs={"autocomplete": "address-level1"}),
            "pincode": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "6"}
            ),
            "emergency_contact_phone": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "10"}
            ),
            "vehicle_number": forms.TextInput(
                attrs={"placeholder": "Example: UP33 AB 1234"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and not self.is_bound:
            self.fields["name"].initial = user.name
            self.fields["phone"].initial = user.phone

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_phone(self):
        return normalize_indian_phone(self.cleaned_data["phone"])

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")

        if not dob:
            raise forms.ValidationError("Date of birth is required.")

        today = date.today()
        age = (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )

        if age < 18:
            raise forms.ValidationError(
                "Delivery partner must be at least 18 years old."
            )

        return dob

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")

        if not photo and not getattr(self.instance, "profile_photo", None):
            raise forms.ValidationError("Profile photo is required.")

        return validate_onboarding_image(photo)

    def clean_pincode(self):
        pincode = str(self.cleaned_data.get("pincode") or "").strip()

        if not pincode.isdigit() or len(pincode) != 6:
            raise forms.ValidationError("Pincode must be 6 digits.")

        return pincode

    def clean_emergency_contact_phone(self):
        return normalize_indian_phone(
            self.cleaned_data["emergency_contact_phone"]
        )

    def clean_vehicle_number(self):
        return (
            self.cleaned_data.get("vehicle_number") or ""
        ).strip().upper()

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user:
            self.user.name = self.cleaned_data["name"]
            self.user.phone = self.cleaned_data["phone"]
            self.user.role = "DELIVERY"
            self.user.save(update_fields=["name", "phone", "role"])

        if commit:
            profile.save()

        return profile


# =========================================================
# DELIVERY ONBOARDING — STEP 2: DOCUMENTS
# Raw Aadhaar/PAN numbers are validated here, then views will
# save only a protected hash and last 4 characters.
# =========================================================

class DeliveryDocumentsForm(forms.Form):
    aadhaar_number = forms.CharField(
        max_length=12,
        label="Aadhaar number",
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "maxlength": "12"},
        ),
    )
    aadhaar_front = forms.FileField(
        label="Aadhaar front",
        validators=[validate_onboarding_file],
        widget=forms.FileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )
    aadhaar_back = forms.FileField(
        label="Aadhaar back",
        validators=[validate_onboarding_file],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )
    pan_number = forms.CharField(
        max_length=10,
        label="PAN number",
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "maxlength": "10"}
        ),
    )
    pan_card = forms.FileField(
        label="PAN card",
        validators=[validate_onboarding_file],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )
    driving_licence_number = forms.CharField(
        max_length=20,
        required=False,
        label="Driving licence number",
    )
    driving_licence = forms.FileField(
        required=False,
        validators=[validate_onboarding_file],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )
    vehicle_rc = forms.FileField(
        required=False,
        label="Vehicle RC",
        validators=[validate_onboarding_file],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )
    selfie = forms.FileField(
        label="Verification selfie",
        validators=[validate_onboarding_image],
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png",
                "capture": "user",
            }
        ),
    )

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile

        # Licence and RC are optional during initial onboarding.
        # Admin can request them later when required.
        self.fields["driving_licence_number"].required = False
        self.fields["driving_licence"].required = False
        self.fields["vehicle_rc"].required = False

    def clean_aadhaar_number(self):
        number = re.sub(r"\D", "", self.cleaned_data["aadhaar_number"])

        if not re.fullmatch(r"[2-9][0-9]{11}", number):
            raise forms.ValidationError(
                "Please enter a valid 12 digit Aadhaar number."
            )

        return number

    def clean_pan_number(self):
        number = self.cleaned_data["pan_number"].strip().upper()

        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", number):
            raise forms.ValidationError(
                "Please enter a valid PAN number."
            )

        return number

    def clean_driving_licence_number(self):
        return (
            self.cleaned_data.get("driving_licence_number") or ""
        ).strip().upper()


# =========================================================
# DELIVERY ONBOARDING — STEP 3: BANK DETAILS
# =========================================================

class DeliveryBankDetailsForm(forms.Form):
    account_holder_name = forms.CharField(max_length=150)
    bank_name = forms.CharField(max_length=150)
    account_number = forms.CharField(
        min_length=9,
        max_length=18,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "autocomplete": "off"},
        ),
    )
    confirm_account_number = forms.CharField(
        min_length=9,
        max_length=18,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "autocomplete": "off"},
        ),
    )
    ifsc_code = forms.CharField(
        min_length=11,
        max_length=11,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "maxlength": "11"}
        ),
    )
    cancelled_cheque = forms.FileField(
        required=False,
        validators=[validate_onboarding_file],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.pdf"}
        ),
    )

    def clean_account_holder_name(self):
        name = self.cleaned_data["account_holder_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError(
                "Please enter the account holder name."
            )
        return name

    def clean_account_number(self):
        number = re.sub(r"\D", "", self.cleaned_data["account_number"])

        if not re.fullmatch(r"[0-9]{9,18}", number):
            raise forms.ValidationError(
                "Account number must contain 9 to 18 digits."
            )

        return number

    def clean_confirm_account_number(self):
        return re.sub(
            r"\D",
            "",
            self.cleaned_data["confirm_account_number"],
        )

    def clean_ifsc_code(self):
        ifsc = self.cleaned_data["ifsc_code"].strip().upper()

        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
            raise forms.ValidationError(
                "Please enter a valid IFSC code."
            )

        return ifsc

    def clean(self):
        cleaned_data = super().clean()

        account_number = cleaned_data.get("account_number")
        confirm_account_number = cleaned_data.get("confirm_account_number")

        if (
            account_number
            and confirm_account_number
            and account_number != confirm_account_number
        ):
            self.add_error(
                "confirm_account_number",
                "Account numbers do not match.",
            )

        return cleaned_data


# =========================================================
# DELIVERY ONBOARDING — STEP 4: FINAL SUBMISSION
# =========================================================

class DeliveryFinalVerificationForm(forms.Form):
    confirm_details = forms.BooleanField(
        label=(
            "I confirm that all details and documents are correct."
        )
    )
    accept_terms = forms.BooleanField(
        label=(
            "I accept AMEXA delivery partner terms and verification policy."
        )
    )


# =========================================================
# SHOPKEEPER ONBOARDING
# =========================================================

FOOD_SHOP_TYPES = {
    "GROCERY",
    "FRUITS_VEGETABLES",
    "DAIRY",
    "BAKERY",
    "RESTAURANT",
}


class ShopkeeperPersonalDetailsForm(forms.ModelForm):
    name = forms.CharField(max_length=150, label="Owner full name")
    phone = forms.CharField(
        max_length=15,
        label="Mobile number",
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "maxlength": "10"}
        ),
    )

    class Meta:
        model = ShopkeeperProfile
        fields = [
            "owner_photo",
            "date_of_birth",
            "residential_address",
            "city",
            "state",
            "pincode",
            "emergency_contact_name",
            "emergency_contact_phone",
        ]
        widgets = {
            "owner_photo": forms.FileInput(
                attrs={
                    "accept": "image/jpeg,image/png",
                    "capture": "user",
                }
            ),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "residential_address": forms.Textarea(attrs={"rows": 3}),
            "pincode": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "6"}
            ),
            "emergency_contact_phone": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "10"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user and not self.is_bound:
            self.fields["name"].initial = user.name
            self.fields["phone"].initial = user.phone

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Please enter the owner's full name.")
        return value

    def clean_phone(self):
        return normalize_indian_phone(self.cleaned_data["phone"])

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if not dob:
            raise forms.ValidationError("Date of birth is required.")
        today = date.today()
        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )
        if age < 18:
            raise forms.ValidationError("Shop owner must be at least 18 years old.")
        return dob

    def clean_owner_photo(self):
        photo = self.cleaned_data.get("owner_photo")
        if not photo and not getattr(self.instance, "owner_photo", None):
            raise forms.ValidationError("Live owner photo is required.")
        return validate_onboarding_image(photo)

    def clean_pincode(self):
        value = str(self.cleaned_data.get("pincode") or "").strip()
        if not value.isdigit() or len(value) != 6:
            raise forms.ValidationError("Pincode must be 6 digits.")
        return value

    def clean_emergency_contact_phone(self):
        return normalize_indian_phone(
            self.cleaned_data["emergency_contact_phone"]
        )

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.name = self.cleaned_data["name"]
            self.user.phone = self.cleaned_data["phone"]
            self.user.role = "SHOPKEEPER"
            self.user.save(update_fields=["name", "phone", "role"])
        if commit:
            profile.save()
        return profile


class ShopkeeperBusinessDetailsForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = [
            "name",
            "legal_name",
            "shop_type",
            "address",
            "phone",
            "gstin",
            "fssai_number",
            "latitude",
            "longitude",
            "minimum_order_value",
            "opening_time",
            "closing_time",
            "auto_accept_orders",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "phone": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "10"}
            ),
            "gstin": forms.TextInput(
                attrs={"maxlength": "15", "autocomplete": "off"}
            ),
            "fssai_number": forms.TextInput(
                attrs={"inputmode": "numeric", "maxlength": "14"}
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "minimum_order_value": forms.NumberInput(
                attrs={"min": "0", "step": "1"}
            ),
            "opening_time": forms.TimeInput(attrs={"type": "time"}),
            "closing_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_phone(self):
        return normalize_indian_phone(self.cleaned_data["phone"])

    def clean_gstin(self):
        value = (self.cleaned_data.get("gstin") or "").strip().upper()
        pattern = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
        if not re.fullmatch(pattern, value):
            raise forms.ValidationError("Please enter a valid 15 character GSTIN.")
        return value

    def clean_fssai_number(self):
        value = re.sub(
            r"\D",
            "",
            self.cleaned_data.get("fssai_number") or "",
        )
        shop_type = self.data.get("shop_type") or getattr(
            self.instance,
            "shop_type",
            "",
        )
        if shop_type in FOOD_SHOP_TYPES and len(value) != 14:
            raise forms.ValidationError(
                "14 digit FSSAI number is required for food shops."
            )
        if value and len(value) != 14:
            raise forms.ValidationError("FSSAI number must be 14 digits.")
        return value


class ShopkeeperDocumentsForm(forms.Form):
    aadhaar_number = forms.CharField(
        max_length=12,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "maxlength": "12"},
        ),
    )
    aadhaar_front = forms.FileField(
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    aadhaar_back = forms.FileField(
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    pan_number = forms.CharField(max_length=10)
    pan_card = forms.FileField(
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    gst_certificate = forms.FileField(
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    fssai_certificate = forms.FileField(
        required=False,
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )
    owner_selfie = forms.FileField(
        validators=[validate_onboarding_image],
        widget=forms.FileInput(
            attrs={"accept": "image/jpeg,image/png", "capture": "user"}
        ),
    )
    shop_front = forms.FileField(
        validators=[validate_onboarding_image],
        widget=forms.FileInput(
            attrs={"accept": "image/jpeg,image/png", "capture": "environment"}
        ),
    )

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        if (
            profile
            and profile.shop_id
            and profile.shop.shop_type in FOOD_SHOP_TYPES
        ):
            self.fields["fssai_certificate"].required = True

    def clean_aadhaar_number(self):
        value = re.sub(r"\D", "", self.cleaned_data["aadhaar_number"])
        if not re.fullmatch(r"[2-9][0-9]{11}", value):
            raise forms.ValidationError("Please enter a valid Aadhaar number.")
        return value

    def clean_pan_number(self):
        value = self.cleaned_data["pan_number"].strip().upper()
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value):
            raise forms.ValidationError("Please enter a valid PAN number.")
        return value


class ShopkeeperBankDetailsForm(forms.Form):
    account_holder_name = forms.CharField(max_length=150)
    bank_name = forms.CharField(max_length=150)
    account_number = forms.CharField(
        min_length=9,
        max_length=18,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "autocomplete": "off"},
        ),
    )
    confirm_account_number = forms.CharField(
        min_length=9,
        max_length=18,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={"inputmode": "numeric", "autocomplete": "off"},
        ),
    )
    ifsc_code = forms.CharField(min_length=11, max_length=11)
    upi_id = forms.CharField(max_length=100, required=False)
    cancelled_cheque = forms.FileField(
        required=False,
        validators=[validate_onboarding_file],
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}),
    )

    def clean_account_number(self):
        value = re.sub(r"\D", "", self.cleaned_data["account_number"])
        if not re.fullmatch(r"[0-9]{9,18}", value):
            raise forms.ValidationError("Account number must be 9 to 18 digits.")
        return value

    def clean_confirm_account_number(self):
        return re.sub(
            r"\D",
            "",
            self.cleaned_data["confirm_account_number"],
        )

    def clean_ifsc_code(self):
        value = self.cleaned_data["ifsc_code"].strip().upper()
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value):
            raise forms.ValidationError("Please enter a valid IFSC code.")
        return value

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("account_number")
            and cleaned.get("confirm_account_number")
            and cleaned["account_number"] != cleaned["confirm_account_number"]
        ):
            self.add_error(
                "confirm_account_number",
                "Account numbers do not match.",
            )
        return cleaned


class ShopkeeperFinalVerificationForm(forms.Form):
    confirm_details = forms.BooleanField(
        label="I confirm that all business and bank details are correct."
    )
    accept_terms = forms.BooleanField(
        label="I accept AMEXA shopkeeper terms and verification policy."
    )
