"""
Email service using Resend (HTTPS API) instead of raw SMTP.

Railway blocks outbound SMTP ports (25, 465, 587) on Free/Trial/Hobby
plans to prevent abuse, so a direct smtplib/Flask-Mail connection to
Gmail (or any SMTP server) times out and can hang the request. Resend
sends over regular HTTPS (port 443), which isn't blocked, and its free
tier covers this project's needs comfortably.
"""
import os
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_URL = "https://api.resend.com/emails"
_config = {}


def init_email(app):
    """Store the Resend API key and sender address. Kept as a
    function taking `app` for compatibility with the existing
    app.py call site (init_email(app)) - it doesn't touch
    app.config the way Flask-Mail did, since Resend needs no
    Flask-Mail extension."""
    _config['api_key'] = os.getenv('RESEND_API_KEY')
    _config['from_email'] = os.getenv('MAIL_FROM', 'AI Receptionist <onboarding@resend.dev>')

    if _config['api_key']:
        print("✅ Email service initialized (Resend)!")
    else:
        print("⚠️ RESEND_API_KEY not set - emails will not send")


def _send_in_background(payload, log_label, recipient):
    """Fire the HTTPS request on a separate thread so a slow network
    call never blocks the request that triggered it."""
    try:
        headers = {
            "Authorization": f"Bearer {_config.get('api_key')}",
            "Content-Type": "application/json",
        }
        resp = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=8)
        if resp.status_code in (200, 201):
            print(f"✅ {log_label} sent to {recipient}")
        else:
            print(f"❌ {log_label} error (background): {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"❌ {log_label} error (background): {e}")


def send_booking_confirmation(customer_email, customer_name, appointment_data):
    """Queue the appointment confirmation email to send in the
    background via Resend's HTTPS API. Returns True immediately once
    queued - it does not wait for the request to complete, so this
    never blocks or times out the calling request."""
    if not _config.get('api_key'):
        print("❌ Email error: RESEND_API_KEY not configured")
        return False

    try:
        subject = f"✅ Appointment Confirmation - {appointment_data.get('service', 'Appointment')}"

        body = f"""Hello {customer_name},

Your appointment has been successfully booked! 🎉

Appointment Details:
------------------------------
Service: {appointment_data.get('service', 'N/A')}
Date: {appointment_data.get('date', 'N/A')}
Time: {appointment_data.get('time', 'N/A')}
------------------------------

Location: Medical Clinic, Downtown
Contact: (555) 123-4567
Website: www.medicalclinic.com

If you need to reschedule or cancel, please contact us 24 hours before your appointment.

Thank you for choosing our clinic!

Best regards,
AI Receptionist Team
"""

        payload = {
            "from": _config['from_email'],
            "to": [customer_email],
            "subject": subject,
            "text": body,
        }

        threading.Thread(
            target=_send_in_background,
            args=(payload, "Confirmation email", customer_email),
            daemon=True
        ).start()
        print(f"📤 Confirmation email queued for {customer_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False