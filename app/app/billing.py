import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_checkout(price_id):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="subscription",
        success_url="https://yourapp.com/success",
        cancel_url="https://yourapp.com/cancel",
    )
    return session.url
