"""
URL configuration for AMEXA project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from customer.support_views import (
    help_support_view,
    privacy_policy_view,
    terms_conditions_view,
)

from customer.views import (

    # ADMIN CONTROL CENTER
    admin_control_center_view,

    # HOME
    home,
    search_results_view,

    # LOGIN / LOGOUT
    login_view,
    logout_view,

    # PROFILE / ABOUT
    profile_view,
    about_view,

    # ADDRESSES
    addresses_view,
    add_address_view,
    edit_address_view,
    delete_address_view,

    # LOCATION
    location_picker_view,
    location_save_view,

    # SHOPS
    nearby_shops_view,
    shop_detail_view,

    # CATEGORIES
    categories_view,
    category_products_view,

    # PRODUCTS
    product_detail_view,

    # CART
    cart_view,
    cart_add_view,
    cart_update_view,
    cart_remove_view,
    cart_clear_view,

    # COUPONS
    apply_coupon_view,
    remove_coupon_view,

    # MONTHLY PACKS
    monthly_packs_view,
    monthly_pack_create_view,
    monthly_pack_detail_view,
    monthly_pack_add_product_view,
    monthly_pack_update_item_view,
    monthly_pack_remove_item_view,
    monthly_pack_delete_view,
    monthly_pack_add_to_cart_view,

    # CHECKOUT
    checkout_view,

    # ORDERS / TRACKING
    orders_view,
    order_detail_view,
    order_tracking_data_view,
    picker_accept_task_view,
    picker_dashboard_view,
    picker_order_detail_view,
    picker_scan_item_view,
    delivery_location_update_view,
    delivery_partner_location_update_view,
    delivery_live_tracking_view,
    delivery_onboarding_view,
    delivery_verification_status_view,
    delivery_dashboard_view,
    delivery_profile_view,
    delivery_assignment_action_view,
    shopkeeper_dashboard_view,
    shopkeeper_bad_stock_view,
    shopkeeper_inventory_update_view,
    shopkeeper_inventory_view,
    shopkeeper_onboarding_view,
    shopkeeper_order_action_view,
    shopkeeper_orders_view,
    shopkeeper_payments_view,
    shopkeeper_product_add_view,
    shopkeeper_profile_view,
    shopkeeper_upc_lookup_view,
    shopkeeper_verification_status_view,
    cancel_order_view,
    order_success_view,
)


urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        home,
        name="home",
    ),

    path(
        "search/",
        search_results_view,
        name="search_results",
    ),


    # =====================================================
    # LOGIN / LOGOUT
    # =====================================================

    path(
        "login/",
        login_view,
        name="login",
    ),

    path(
        "logout/",
        logout_view,
        name="logout",
    ),


    # =====================================================
    # PROFILE
    # =====================================================

    path(
        "profile/",
        profile_view,
        name="profile",
    ),


    # =====================================================
    # ABOUT AMEXA
    # =====================================================

    path(
        "about/",
        about_view,
        name="about",
    ),


    # =====================================================
    # HELP & SUPPORT
    # =====================================================

    path(
        "help/",
        help_support_view,
        name="help_support",
    ),


    # =====================================================
    # PRIVACY POLICY
    # =====================================================

    path(
        "privacy-policy/",
        privacy_policy_view,
        name="privacy_policy",
    ),


    # =====================================================
    # TERMS & CONDITIONS
    # =====================================================

    path(
        "terms-conditions/",
        terms_conditions_view,
        name="terms_conditions",
    ),


    # =====================================================
    # ADDRESSES
    # =====================================================

    path(
        "addresses/",
        addresses_view,
        name="addresses",
    ),

    path(
        "addresses/add/",
        add_address_view,
        name="add_address",
    ),

    path(
        "addresses/edit/<int:pk>/",
        edit_address_view,
        name="edit_address",
    ),

    path(
        "addresses/delete/<int:pk>/",
        delete_address_view,
        name="delete_address",
    ),


    # =====================================================
    # CURRENT LOCATION / MAP PICKER
    # =====================================================

    path(
        "location/",
        location_picker_view,
        name="location_picker",
    ),

    path(
        "location/save/",
        location_save_view,
        name="location_save",
    ),


    # =====================================================
    # SHOPS
    # =====================================================

    path(
        "shops/",
        nearby_shops_view,
        name="nearby_shops",
    ),

    path(
        "shops/<slug:slug>/",
        shop_detail_view,
        name="shop_detail",
    ),


    # =====================================================
    # CATEGORIES
    # =====================================================

    path(
        "categories/",
        categories_view,
        name="categories",
    ),

    path(
        "categories/<slug:slug>/",
        category_products_view,
        name="category_products",
    ),


    # =====================================================
    # PRODUCTS
    # =====================================================

    path(
        "products/<slug:slug>/",
        product_detail_view,
        name="product_detail",
    ),


    # =====================================================
    # CART
    # =====================================================

    path(
        "cart/",
        cart_view,
        name="cart",
    ),

    path(
        "cart/add/<int:product_id>/",
        cart_add_view,
        name="cart_add",
    ),

    path(
        "cart/update/<int:item_id>/",
        cart_update_view,
        name="cart_update",
    ),

    path(
        "cart/remove/<int:item_id>/",
        cart_remove_view,
        name="cart_remove",
    ),

    path(
        "cart/clear/",
        cart_clear_view,
        name="cart_clear",
    ),


    # =====================================================
    # COUPONS
    # =====================================================

    path(
        "cart/coupon/apply/",
        apply_coupon_view,
        name="apply_coupon",
    ),

    path(
        "cart/coupon/remove/",
        remove_coupon_view,
        name="remove_coupon",
    ),


    # =====================================================
    # MONTHLY GROCERY PACKS
    # =====================================================

    path(
        "monthly-packs/",
        monthly_packs_view,
        name="monthly_packs",
    ),

    path(
        "monthly-packs/create/",
        monthly_pack_create_view,
        name="monthly_pack_create",
    ),

    path(
        "monthly-packs/<int:pack_id>/",
        monthly_pack_detail_view,
        name="monthly_pack_detail",
    ),

    path(
        "monthly-packs/<int:pack_id>/add-product/<int:product_id>/",
        monthly_pack_add_product_view,
        name="monthly_pack_add_product",
    ),

    path(
        "monthly-packs/<int:pack_id>/item/<int:item_id>/update/",
        monthly_pack_update_item_view,
        name="monthly_pack_update_item",
    ),

    path(
        "monthly-packs/<int:pack_id>/item/<int:item_id>/remove/",
        monthly_pack_remove_item_view,
        name="monthly_pack_remove_item",
    ),

    path(
        "monthly-packs/<int:pack_id>/delete/",
        monthly_pack_delete_view,
        name="monthly_pack_delete",
    ),

    path(
        "monthly-packs/<int:pack_id>/add-to-cart/",
        monthly_pack_add_to_cart_view,
        name="monthly_pack_add_to_cart",
    ),


    # =====================================================
    # CHECKOUT
    # =====================================================

    path(
        "checkout/",
        checkout_view,
        name="checkout",
    ),


    # =====================================================
    # ORDERS
    # =====================================================

    path(
        "orders/",
        orders_view,
        name="orders",
    ),


    # =====================================================
    # CUSTOMER ORDER LIVE TRACKING JSON
    # =====================================================

    path(
        "orders/<str:order_number>/tracking-data/",
        order_tracking_data_view,
        name="order_tracking_data",
    ),


    # =====================================================
    # RIDER GPS LOCATION UPDATE API
    # =====================================================

    path(
        "orders/<str:order_number>/rider-location/",
        delivery_location_update_view,
        name="delivery_location_update",
    ),


    # =====================================================
    # DELIVERY PARTNER DASHBOARD
    # =====================================================

    path(
        "delivery/onboarding/",
        delivery_onboarding_view,
        name="delivery_onboarding_start",
    ),

    path(
        "delivery/onboarding/<int:step>/",
        delivery_onboarding_view,
        name="delivery_onboarding",
    ),

    path(
        "delivery/verification-status/",
        delivery_verification_status_view,
        name="delivery_verification_status",
    ),

    path(
        "delivery/",
        delivery_dashboard_view,
        name="delivery_dashboard",
    ),

    path(
        "delivery/location/update/",
        delivery_partner_location_update_view,
        name="delivery_partner_location_update",
    ),

    path(
        "delivery/profile/",
        delivery_profile_view,
        name="delivery_profile",
    ),

    path(
        "delivery/assignments/<int:assignment_id>/action/",
        delivery_assignment_action_view,
        name="delivery_assignment_action",
    ),


    # =====================================================
    # DELIVERY PARTNER LIVE GPS PAGE
    # =====================================================

    path(
        "delivery/orders/<str:order_number>/live/",
        delivery_live_tracking_view,
        name="delivery_live_tracking",
    ),


    # =====================================================
    # CANCEL ORDER
    # =====================================================

    path(
        "orders/<int:order_id>/cancel/",
        cancel_order_view,
        name="cancel_order",
    ),


    # =====================================================
    # ORDER SUCCESS
    # =====================================================

    path(
        "orders/<int:order_id>/success/",
        order_success_view,
        name="order_success",
    ),


    # =====================================================
    # ORDER DETAIL / TRACKING PAGE
    # =====================================================

    path(
        "orders/<str:order_number>/",
        order_detail_view,
        name="order_detail",
    ),


    # =====================================================
    # AMEXA ADMIN CONTROL CENTER
    # =====================================================

    path(
        "admin/",
        admin_control_center_view,
        name="admin_control_center",
    ),

    # Old shared link also keeps working.
    path(
        "admin/control-center/",
        admin_control_center_view,
        name="admin_control_center_legacy",
    ),


    # =====================================================
    # SHOPKEEPER APP / ONBOARDING
    # =====================================================

    path(
        "shopkeeper/",
        shopkeeper_dashboard_view,
        name="shopkeeper_dashboard",
    ),

    path(
        "shopkeeper/onboarding/",
        shopkeeper_onboarding_view,
        name="shopkeeper_onboarding_start",
    ),

    path(
        "shopkeeper/onboarding/<int:step>/",
        shopkeeper_onboarding_view,
        name="shopkeeper_onboarding",
    ),

    path(
        "shopkeeper/verification-status/",
        shopkeeper_verification_status_view,
        name="shopkeeper_verification_status",
    ),

    path(
        "shopkeeper/orders/",
        shopkeeper_orders_view,
        name="shopkeeper_orders",
    ),

    path(
        "shopkeeper/orders/<str:order_number>/action/",
        shopkeeper_order_action_view,
        name="shopkeeper_order_action",
    ),

    path(
        "shopkeeper/inventory/",
        shopkeeper_inventory_view,
        name="shopkeeper_inventory",
    ),

    path(
        "shopkeeper/inventory/add/",
        shopkeeper_product_add_view,
        name="shopkeeper_product_add",
    ),

    path(
        "shopkeeper/inventory/upc-lookup/",
        shopkeeper_upc_lookup_view,
        name="shopkeeper_upc_lookup",
    ),

    path(
        "shopkeeper/inventory/<int:product_id>/update/",
        shopkeeper_inventory_update_view,
        name="shopkeeper_inventory_update",
    ),

    path(
        "shopkeeper/inventory/<int:product_id>/bad-stock/",
        shopkeeper_bad_stock_view,
        name="shopkeeper_bad_stock",
    ),

    path(
        "shopkeeper/payments/",
        shopkeeper_payments_view,
        name="shopkeeper_payments",
    ),

    path(
        "shopkeeper/profile/",
        shopkeeper_profile_view,
        name="shopkeeper_profile",
    ),


    # =====================================================
    # PICKER APP / UPC ORDER PICKING
    # =====================================================

    path(
        "picker/",
        picker_dashboard_view,
        name="picker_dashboard",
    ),

    path(
        "picker/orders/<str:order_number>/",
        picker_order_detail_view,
        name="picker_order_detail",
    ),

    path(
        "picker/orders/<str:order_number>/accept/",
        picker_accept_task_view,
        name="picker_accept_task",
    ),

    path(
        "picker/orders/<str:order_number>/scan/",
        picker_scan_item_view,
        name="picker_scan_item",
    ),


    # =====================================================
    # DJANGO ADMIN
    # =====================================================

    path(
        "admin/system/",
        admin.site.urls,
    ),
]


# =========================================================
# MEDIA FILES - DEVELOPMENT MODE
# =========================================================

if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
