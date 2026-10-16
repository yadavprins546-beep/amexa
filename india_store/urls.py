from django.urls import path
from . import views

app_name = "india_store"

urlpatterns = [
    path("", views.india_home, name="home"),
    path("search/", views.india_search_view, name="search"),
    path(
        "product/<int:product_id>/",
        views.india_product_detail_view,
        name="product_detail",
    ),
    path(
        "reviews/<int:product_id>/add/",
        views.india_review_add_view,
        name="review_add",
    ),
    path("wishlist/", views.india_wishlist_view, name="wishlist"),
    path(
        "wishlist/toggle/<int:product_id>/",
        views.india_wishlist_toggle_view,
        name="wishlist_toggle",
    ),

    path("cart/", views.india_cart_view, name="cart"),
    path(
        "cart/add/<int:product_id>/",
        views.india_cart_add_view,
        name="cart_add",
    ),
    path(
        "cart/update/<int:item_id>/",
        views.india_cart_update_view,
        name="cart_update",
    ),
    path(
        "cart/remove/<int:item_id>/",
        views.india_cart_remove_view,
        name="cart_remove",
    ),
    path("checkout/", views.india_checkout_view, name="checkout"),
    path("notifications/", views.india_notifications_view, name="notifications"),
    path(
        "notifications/<int:notification_id>/read/",
        views.india_notification_read_view,
        name="notification_read",
    ),
    path("orders/", views.india_orders_view, name="orders"),
    path(
        "orders/<str:order_number>/items/<int:item_id>/return/",
        views.india_return_request_view,
        name="return_request",
    ),
    path(
        "orders/<str:order_number>/cancel/",
        views.india_order_cancel_view,
        name="order_cancel",
    ),
    path(
        "payment/razorpay/verify/",
        views.india_razorpay_verify_view,
        name="payment_verify",
    ),
    path(
        "orders/<str:order_number>/",
        views.india_order_detail_view,
        name="order_detail",
    ),
]
