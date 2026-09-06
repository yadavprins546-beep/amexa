import random
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import OTPVerification


def normalize_phone(value):
    phone = re.sub(r"\D", "", str(value or ""))

    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]

    if len(phone) != 10:
        return None

    return phone


def next_screen_for_user(user):
    role = getattr(user, "role", "CUSTOMER")

    return {
        "SHOPKEEPER": "SHOPKEEPER_HOME",
        "PICKER": "PICKER_HOME",
        "DELIVERY": "DELIVERY_HOME",
        "ADMIN": "ADMIN_HOME",
        "CUSTOMER": "CUSTOMER_HOME",
    }.get(role, "CUSTOMER_HOME")


def user_payload(user):
    return {
        "id": user.pk,
        "name": getattr(user, "name", "") or "",
        "phone": getattr(user, "phone", "") or "",
        "role": getattr(user, "role", "CUSTOMER"),
        "is_active": user.is_active,
    }


class RequestOTPAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone"))
        name = str(request.data.get("name") or "").strip()

        if not phone:
            return Response(
                {"detail": "Valid 10 digit mobile number required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()

        user = (
            User.objects
            .filter(phone=phone)
            .order_by("pk")
            .first()
        )

        created = False

        if user is None:
            user = User.objects.create(
                phone=phone,
                name=name or "Customer",
                email=f"{phone}@amexa.local",
            )
            created = True
        elif name and not getattr(user, "name", ""):
            user.name = name
            user.save(update_fields=["name"])

        OTPVerification.objects.filter(
            user=user,
            phone=phone,
            is_used=False,
        ).update(is_used=True)

        code = f"{random.randint(0, 999999):06d}"

        otp = OTPVerification.objects.create(
            user=user,
            phone=phone,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        data = {
            "success": True,
            "message": "OTP generated successfully.",
            "phone": phone,
            "expires_in_seconds": 300,
            "new_user": created,
        }

        # Development testing only.
        if settings.DEBUG:
            data["demo_otp"] = otp.code

        return Response(data, status=status.HTTP_200_OK)


class VerifyOTPAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone"))
        otp_code = str(request.data.get("otp") or "").strip()

        if not phone:
            return Response(
                {"detail": "Valid mobile number required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not re.fullmatch(r"\d{6}", otp_code):
            return Response(
                {"detail": "Valid 6 digit OTP required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()

        user = (
            User.objects
            .filter(phone=phone)
            .order_by("pk")
            .first()
        )

        if user is None:
            return Response(
                {"detail": "User not found. Request OTP again."},
                status=status.HTTP_404_NOT_FOUND,
            )

        otp = (
            OTPVerification.objects
            .filter(
                user=user,
                phone=phone,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            return Response(
                {"detail": "Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.is_valid():
            return Response(
                {"detail": "OTP expired. Request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.code != otp_code:
            otp.attempts += 1
            otp.save(update_fields=["attempts"])

            return Response(
                {"detail": "Incorrect OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "token": token.key,
                "user": user_payload(user),
                "next_screen": next_screen_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class MeAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "user": user_payload(request.user),
                "next_screen": next_screen_for_user(request.user),
            }
        )
