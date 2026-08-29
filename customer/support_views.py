from django.shortcuts import render

from .models import (
    HelpSupport,
    PrivacyPolicy,
    TermsConditions,
)


# =========================================================
# HELP & SUPPORT
# =========================================================

def help_support_view(request):
    support = (
        HelpSupport.objects
        .filter(is_active=True)
        .order_by("-updated_at")
        .first()
    )

    return render(
        request,
        "customer/help.html",
        {
            "support": support,
        },
    )


# =========================================================
# PRIVACY POLICY
# =========================================================

def privacy_policy_view(request):
    policy = (
        PrivacyPolicy.objects
        .filter(is_active=True)
        .order_by("-updated_at")
        .first()
    )

    return render(
        request,
        "customer/privacy_policy.html",
        {
            "policy": policy,
        },
    )


# =========================================================
# TERMS & CONDITIONS
# =========================================================

def terms_conditions_view(request):
    terms = (
        TermsConditions.objects
        .filter(is_active=True)
        .order_by("-updated_at")
        .first()
    )

    return render(
        request,
        "customer/terms_conditions.html",
        {
            "terms": terms,
        },
    )
def privacy_policy_view(request):
    return render(
        request,
        "customer/privacy_policy.html",
    )
def terms_conditions_view(request):
    return render(
        request,
        "customer/terms_conditions.html",
    )