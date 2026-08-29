from django import forms

from .models import Address


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
        phone = self.cleaned_data["phone"].strip()

        # Spaces / +91 / hyphen ko normalize karne me help
        phone = phone.replace(" ", "").replace("-", "")

        if phone.startswith("+91"):
            phone = phone[3:]
        elif phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]

        if not phone.isdigit():
            raise forms.ValidationError(
                "Please enter a valid mobile number."
            )

        if len(phone) != 10:
            raise forms.ValidationError(
                "Mobile number must be 10 digits."
            )

        return phone


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

            # -------------------------------------------------
            # CUSTOMER NAME
            # -------------------------------------------------

            "full_name": forms.TextInput(
                attrs={
                    "placeholder": "Full name",
                    "autocomplete": "name",
                }
            ),

            # -------------------------------------------------
            # MOBILE
            # -------------------------------------------------

            "mobile": forms.TextInput(
                attrs={
                    "placeholder": "10 digit mobile number",
                    "inputmode": "numeric",
                    "autocomplete": "tel",
                    "maxlength": "10",
                }
            ),

            # -------------------------------------------------
            # ADDRESS
            # -------------------------------------------------

            "address_line": forms.TextInput(
                attrs={
                    "placeholder": (
                        "House no, building, street, "
                        "area or landmark"
                    ),
                    "autocomplete": "street-address",
                }
            ),

            # -------------------------------------------------
            # CITY
            # -------------------------------------------------

            "city": forms.TextInput(
                attrs={
                    "placeholder": "City",
                    "autocomplete": "address-level2",
                }
            ),

            # -------------------------------------------------
            # STATE
            # -------------------------------------------------

            "state": forms.TextInput(
                attrs={
                    "placeholder": "State",
                    "autocomplete": "address-level1",
                }
            ),

            # -------------------------------------------------
            # PINCODE
            # -------------------------------------------------

            "pincode": forms.TextInput(
                attrs={
                    "placeholder": "6 digit pincode",
                    "inputmode": "numeric",
                    "autocomplete": "postal-code",
                    "maxlength": "6",
                }
            ),

            # -------------------------------------------------
            # GPS LOCATION
            # These will be filled automatically from
            # Current Location / map.
            # -------------------------------------------------

            "latitude": forms.HiddenInput(
                attrs={
                    "id": "id_latitude",
                }
            ),

            "longitude": forms.HiddenInput(
                attrs={
                    "id": "id_longitude",
                }
            ),

            # -------------------------------------------------
            # ADDRESS TYPE
            # -------------------------------------------------

            "address_type": forms.Select(),

            # -------------------------------------------------
            # DEFAULT ADDRESS
            # -------------------------------------------------

            "is_default": forms.CheckboxInput(),
        }

    # =====================================================
    # MOBILE VALIDATION
    # =====================================================

    def clean_mobile(self):
        mobile = self.cleaned_data["mobile"].strip()

        mobile = mobile.replace(" ", "").replace("-", "")

        if mobile.startswith("+91"):
            mobile = mobile[3:]
        elif mobile.startswith("91") and len(mobile) == 12:
            mobile = mobile[2:]

        if not mobile.isdigit():
            raise forms.ValidationError(
                "Please enter a valid mobile number."
            )

        if len(mobile) != 10:
            raise forms.ValidationError(
                "Mobile number must be 10 digits."
            )

        return mobile

    # =====================================================
    # PINCODE VALIDATION
    # =====================================================

    def clean_pincode(self):
        pincode = self.cleaned_data["pincode"].strip()

        if not pincode.isdigit():
            raise forms.ValidationError(
                "Please enter a valid pincode."
            )

        if len(pincode) != 6:
            raise forms.ValidationError(
                "Pincode must be 6 digits."
            )

        return pincode

    # =====================================================
    # LATITUDE VALIDATION
    # =====================================================

    def clean_latitude(self):
        latitude = self.cleaned_data.get("latitude")

        if latitude is None:
            return 0

        return latitude

    # =====================================================
    # LONGITUDE VALIDATION
    # =====================================================

    def clean_longitude(self):
        longitude = self.cleaned_data.get("longitude")

        if longitude is None:
            return 0

        return longitude