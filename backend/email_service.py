from flask_mail import Mail, Message
import os
from dotenv import load_dotenv

load_dotenv()

mail = Mail()

def init_email(app):
    """Initialize Flask-Mail"""
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_FROM')
    
    mail.init_app(app)
    print("✅ Email service initialized!")

def send_booking_confirmation(customer_email, customer_name, appointment_data):
    """Send appointment confirmation email"""
    try:
        subject = f"✅ Appointment Confirmation - {appointment_data.get('service', 'Appointment')}"
        
        body = f"""
Hello {customer_name},

Your appointment has been successfully booked! 🎉

📋 Appointment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service: {appointment_data.get('service', 'N/A')}
Date: {appointment_data.get('date', 'N/A')}
Time: {appointment_data.get('time', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Location: Medical Clinic, Downtown
📞 Contact: (555) 123-4567
🌐 Website: www.medicalclinic.com

If you need to reschedule or cancel, please contact us 24 hours before your appointment.

Thank you for choosing our clinic!

Best regards,
AI Receptionist Team
        """
        
        msg = Message(subject=subject, recipients=[customer_email], body=body)
        mail.send(msg)
        print(f"✅ Confirmation email sent to {customer_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

def send_reminder_email(customer_email, customer_name, appointment_data):
    """Send appointment reminder email"""
    try:
        subject = f"📧 Reminder: Your appointment is tomorrow"
        
        body = f"""
Hello {customer_name},

This is a friendly reminder about your appointment tomorrow! 📅

Service: {appointment_data.get('service', 'N/A')}
Time: {appointment_data.get('time', 'N/A')}

Please arrive 10 minutes early. If you cannot make it, please let us know.

See you soon!

Best regards,
Medical Clinic Team
        """
        
        msg = Message(subject=subject, recipients=[customer_email], body=body)
        mail.send(msg)
        print(f"✅ Reminder email sent to {customer_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False