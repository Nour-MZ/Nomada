"""
Payment Gateway Module - Handles Stripe payment processing
Provides secure, PCI-compliant credit card payment handling
"""

import os
import logging
from typing import Dict, Any, Optional
import stripe
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize Stripe with API key from environment
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')


def create_payment_intent(
    amount: str,
    currency: str,
    offer_id: str,
    customer_email: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a Stripe PaymentIntent for collecting payment.

    Args:
        amount: Amount to charge (e.g., "150.00")
        currency: Currency code (e.g., "USD", "EUR", "GBP")
        offer_id: Duffel offer ID for tracking
        customer_email: Customer email for receipt
        metadata: Additional metadata to store

    Returns:
        Dict with client_secret, payment_intent_id, and amount_cents

    Raises:
        Exception: If Stripe API call fails
    """
    if not stripe.api_key:
        raise Exception("STRIPE_SECRET_KEY not configured in environment variables")

    try:
        # Convert amount to cents (Stripe uses smallest currency unit)
        amount_float = float(amount)
        amount_cents = int(amount_float * 100)

        # Prepare metadata
        intent_metadata = {
            'offer_id': offer_id,
            'product': 'flight_booking',
        }
        if metadata:
            intent_metadata.update(metadata)

        # Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata=intent_metadata,
            receipt_email=customer_email,
            automatic_payment_methods={'enabled': True},
        )

        logger.info(f"Created PaymentIntent {intent.id} for {amount} {currency}")

        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'amount_cents': amount_cents,
            'currency': currency,
            'status': intent.status,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent: {str(e)}")
        raise Exception(f"Payment processing error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating payment intent: {str(e)}")
        raise Exception(f"Payment system error: {str(e)}")


def confirm_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
    """
    Retrieve and verify a PaymentIntent status.

    Args:
        payment_intent_id: The Stripe PaymentIntent ID

    Returns:
        Dict with payment details including status, amount, card info

    Raises:
        Exception: If payment not successful or API call fails
    """
    if not stripe.api_key:
        raise Exception("STRIPE_SECRET_KEY not configured")

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Check if payment succeeded
        if intent.status != 'succeeded':
            raise Exception(f"Payment not completed. Status: {intent.status}")

        # Extract payment details
        result = {
            'payment_intent_id': intent.id,
            'status': intent.status,
            'amount': intent.amount / 100,  # Convert back to dollars
            'currency': intent.currency.upper(),
            'created': intent.created,
            'metadata': intent.metadata,
        }

        # Add card details if available
        if intent.charges and len(intent.charges.data) > 0:
            charge = intent.charges.data[0]
            if charge.payment_method_details and charge.payment_method_details.card:
                card = charge.payment_method_details.card
                result['card'] = {
                    'brand': card.brand,
                    'last4': card.last4,
                    'exp_month': card.exp_month,
                    'exp_year': card.exp_year,
                    'country': card.country,
                }

        logger.info(f"Confirmed payment {payment_intent_id}: {result['amount']} {result['currency']}")

        return result

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error confirming payment: {str(e)}")
        raise Exception(f"Payment verification error: {str(e)}")
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        raise


def retrieve_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
    """
    Retrieve PaymentIntent details without requiring success status.

    Args:
        payment_intent_id: The Stripe PaymentIntent ID

    Returns:
        Dict with current payment intent details
    """
    if not stripe.api_key:
        raise Exception("STRIPE_SECRET_KEY not configured")

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        return {
            'payment_intent_id': intent.id,
            'status': intent.status,
            'amount': intent.amount / 100,
            'currency': intent.currency.upper(),
            'created': intent.created,
            'metadata': intent.metadata,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving payment: {str(e)}")
        raise Exception(f"Payment retrieval error: {str(e)}")


def create_refund(payment_intent_id: str, amount: Optional[float] = None) -> Dict[str, Any]:
    """
    Create a refund for a PaymentIntent.

    Args:
        payment_intent_id: The Stripe PaymentIntent ID to refund
        amount: Optional partial refund amount (full refund if not specified)

    Returns:
        Dict with refund details

    Raises:
        Exception: If refund fails
    """
    if not stripe.api_key:
        raise Exception("STRIPE_SECRET_KEY not configured")

    try:
        refund_params = {'payment_intent': payment_intent_id}

        if amount is not None:
            refund_params['amount'] = int(amount * 100)

        refund = stripe.Refund.create(**refund_params)

        logger.info(f"Created refund {refund.id} for payment {payment_intent_id}")

        return {
            'refund_id': refund.id,
            'status': refund.status,
            'amount': refund.amount / 100,
            'currency': refund.currency.upper(),
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating refund: {str(e)}")
        raise Exception(f"Refund error: {str(e)}")