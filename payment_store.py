"""
Payment Store - Tracks Stripe payments and links them to bookings
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Database path
_DB_PATH = Path(__file__).parent / "databases" / "payments.sqlite"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_connection():
    """Get database connection and ensure schema exists."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    """Create payments table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_payment_intent_id TEXT UNIQUE NOT NULL,
            offer_id TEXT,
            order_id TEXT,
            amount TEXT NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            customer_email TEXT,
            card_brand TEXT,
            card_last4 TEXT,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def save_payment(
    stripe_payment_intent_id: str,
    amount: str,
    currency: str,
    status: str,
    offer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    customer_email: Optional[str] = None,
    card_brand: Optional[str] = None,
    card_last4: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Save a payment record to the database.

    Args:
        stripe_payment_intent_id: Stripe PaymentIntent ID
        amount: Payment amount
        currency: Currency code
        status: Payment status (e.g., 'succeeded', 'pending')
        offer_id: Duffel offer ID
        order_id: Duffel order ID (if order created)
        customer_email: Customer email
        card_brand: Card brand (e.g., 'visa', 'mastercard')
        card_last4: Last 4 digits of card
        metadata: Additional metadata as dict

    Returns:
        The ID of the inserted/updated payment record
    """
    conn = _get_connection()
    metadata_json = json.dumps(metadata) if metadata else None

    try:
        # Try to update existing record first
        cursor = conn.execute("""
            UPDATE payments
            SET amount = ?, currency = ?, status = ?, offer_id = ?, order_id = ?,
                customer_email = ?, card_brand = ?, card_last4 = ?,
                metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE stripe_payment_intent_id = ?
        """, (amount, currency, status, offer_id, order_id, customer_email,
              card_brand, card_last4, metadata_json, stripe_payment_intent_id))

        if cursor.rowcount == 0:
            # Insert new record
            cursor = conn.execute("""
                INSERT INTO payments (
                    stripe_payment_intent_id, amount, currency, status,
                    offer_id, order_id, customer_email, card_brand,
                    card_last4, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stripe_payment_intent_id, amount, currency, status,
                  offer_id, order_id, customer_email, card_brand,
                  card_last4, metadata_json))

        conn.commit()
        payment_id = cursor.lastrowid
        return payment_id

    finally:
        conn.close()


def get_payment_by_intent_id(stripe_payment_intent_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a payment record by Stripe PaymentIntent ID.

    Args:
        stripe_payment_intent_id: The Stripe PaymentIntent ID

    Returns:
        Payment record as dict or None if not found
    """
    conn = _get_connection()

    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE stripe_payment_intent_id = ?",
            (stripe_payment_intent_id,)
        ).fetchone()

        if row:
            payment = dict(row)
            if payment.get('metadata_json'):
                payment['metadata'] = json.loads(payment['metadata_json'])
            return payment
        return None

    finally:
        conn.close()


def get_payment_by_order_id(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a payment record by Duffel order ID.

    Args:
        order_id: The Duffel order ID

    Returns:
        Payment record as dict or None if not found
    """
    conn = _get_connection()

    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE order_id = ?",
            (order_id,)
        ).fetchone()

        if row:
            payment = dict(row)
            if payment.get('metadata_json'):
                payment['metadata'] = json.loads(payment['metadata_json'])
            return payment
        return None

    finally:
        conn.close()


def update_payment_status(stripe_payment_intent_id: str, status: str):
    """
    Update the status of a payment.

    Args:
        stripe_payment_intent_id: The Stripe PaymentIntent ID
        status: New status
    """
    conn = _get_connection()

    try:
        conn.execute("""
            UPDATE payments
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE stripe_payment_intent_id = ?
        """, (status, stripe_payment_intent_id))
        conn.commit()

    finally:
        conn.close()


def link_payment_to_order(stripe_payment_intent_id: str, order_id: str):
    """
    Link a payment to a Duffel order.

    Args:
        stripe_payment_intent_id: The Stripe PaymentIntent ID
        order_id: The Duffel order ID
    """
    conn = _get_connection()

    try:
        conn.execute("""
            UPDATE payments
            SET order_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE stripe_payment_intent_id = ?
        """, (order_id, stripe_payment_intent_id))
        conn.commit()

    finally:
        conn.close()


def list_payments_by_email(customer_email: str) -> List[Dict[str, Any]]:
    """
    List all payments for a customer email.

    Args:
        customer_email: Customer email address

    Returns:
        List of payment records
    """
    conn = _get_connection()

    try:
        rows = conn.execute(
            "SELECT * FROM payments WHERE customer_email = ? ORDER BY created_at DESC",
            (customer_email,)
        ).fetchall()

        payments = []
        for row in rows:
            payment = dict(row)
            if payment.get('metadata_json'):
                payment['metadata'] = json.loads(payment['metadata_json'])
            payments.append(payment)

        return payments

    finally:
        conn.close()