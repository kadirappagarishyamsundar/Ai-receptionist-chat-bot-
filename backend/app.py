from flask import Flask, request, jsonify
from flask_cors import CORS
from database import db
from ai_handler import ai
import json
import re
import calendar
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
from email_service import init_email, send_booking_confirmation
from admin_routes import admin_bp
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

init_email(app)
app.register_blueprint(admin_bp)

conversations = {}
# Tracks (date, time, service) combos already rejected as double-booked,
# per user, so we don't silently re-offer the same taken slot if the
# customer's next message doesn't restate a new date/time.
rejected_slots = {}
# Tracks each user's most recently discussed (date, time), so if they later
# give a DIFFERENT date/time, we require them to restate the service too -
# instead of silently carrying over a service they mentioned for a
# different, earlier date/time.
last_slot = {}

WEEKDAYS = {day.lower(): idx for idx, day in enumerate(calendar.day_name)}
MONTH_NAMES = [m.lower() for m in list(calendar.month_name)[1:] + list(calendar.month_abbr)[1:] if m]


def _next_weekday(base_date, weekday_name):
    """Return the date of the next occurrence of the given weekday (always in the future)."""
    target = WEEKDAYS.get(weekday_name.lower())
    if target is None:
        return None
    days_ahead = (target - base_date.weekday() + 7) % 7
    days_ahead = days_ahead if days_ahead != 0 else 7
    return base_date + timedelta(days=days_ahead)


def extract_email(text):
    """Extract email from text"""
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return email_match.group(0) if email_match else None


NAME_STOPWORDS = {
    'and', 'i', "i'm", 'im', 'my', 'phone', 'email', 'is', 'on', 'at',
    'for', 'the', 'a', 'an', 'need', 'want', 'to', 'with', 'have'
}


def extract_name(text):
    """Extract name from text - handles both single-word and multi-word names"""
    name_patterns = [
        r"my name is\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
        r"name is\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
        r"i'm\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
        r"im\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
        r"i am\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})",
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            words = match.group(1).split()
            clean_words = []
            for w in words:
                if w.lower() in NAME_STOPWORDS:
                    break
                clean_words.append(w)
            if clean_words:
                return ' '.join(clean_words[:2]).title()

    return None


def extract_phone(text):
    """Extract phone number from text"""
    phone_match = re.search(r'(?:\+91|0)?[6-9]\d{9}', text)
    return phone_match.group(0) if phone_match else None


def extract_date(text):
    """Extract date from text - supports exact formats and natural language
    (e.g. 'tomorrow', 'next Friday', 'July 26', 'day after tomorrow')."""
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{2})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{2})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    # Strip email/phone first so digit strings can't be misread as a date
    cleaned = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', ' ', text)
    cleaned = re.sub(r'(?:\+91|0)?[6-9]\d{9}', ' ', cleaned)
    lower = cleaned.lower()
    today = datetime.now()

    # Explicit relative-date keywords (checked before generic parsing so
    # they're never mistaken for something else)
    if 'day after tomorrow' in lower:
        return (today + timedelta(days=2)).strftime('%Y-%m-%d')
    if re.search(r'\btomorrow\b', lower):
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    if re.search(r'\btoday\b', lower):
        return today.strftime('%Y-%m-%d')

    weekday_match = re.search(
        r'\b(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        lower
    )
    if weekday_match:
        result = _next_weekday(today, weekday_match.group(1))
        if result:
            return result.strftime('%Y-%m-%d')

    # Absolute dates written with a month name, e.g. "July 26", "26th July".
    # Only attempt this if a real month name is present as a whole word
    # (not a substring - "doctor" contains "oct" but isn't a date).
    month_pattern = r'\b(' + '|'.join(re.escape(m) for m in MONTH_NAMES) + r')\b'
    if re.search(month_pattern, lower):
        try:
            parsed = dateutil_parser.parse(cleaned, fuzzy=True, default=today)
            return parsed.strftime('%Y-%m-%d')
        except (ValueError, OverflowError) as e:
            print(f"⚠️ Could not parse date from text: {e}")

    return None


def normalize_date(date_str):
    """Convert a date string in various formats into MySQL DATE format 'YYYY-MM-DD'."""
    if not date_str:
        return None
    date_str = date_str.strip()
    formats_to_try = [
        "%Y-%m-%d",   # 2026-07-26
        "%d-%m-%Y",   # 26-07-2026
        "%d-%m-%y",   # 26-07-26
        "%d/%m/%Y",   # 26/07/2026
        "%d/%m/%y",   # 26/07/26
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    print(f"⚠️ Could not parse date value: '{date_str}'")
    return None


def extract_time(text):
    """Extract time from text"""
    time_match = re.search(
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))|(\d{1,2}\s*(?:AM|PM|am|pm))|(\d{1,2}:\d{2})',
        text
    )
    if time_match:
        return time_match.group(0).strip()
    return None


def normalize_time(time_str):
    """Convert a time string like '2:00 PM' or '14:00' into MySQL TIME format 'HH:MM:SS'."""
    if not time_str:
        return None
    time_str = time_str.strip()
    formats_to_try = ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M", "%H:%M:%S"]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(time_str, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    print(f"⚠️ Could not parse time value: '{time_str}'")
    return None


def extract_service(text):
    """Extract service from text"""
    services = ['Doctor Visit', 'Dental Checkup', 'Eye Checkup', 'Health Checkup']
    text_lower = text.lower()
    for service in services:
        if service.lower() in text_lower:
            return service
    return None


def build_appointment_from_conversation(conversation_history, current_message):
    """Build appointment data, always preferring what's in the CURRENT
    message. Only falls back to the conversation history (customer
    messages only, never the bot's replies) if a field isn't present in
    the current message at all. This avoids two problems: (1) the bot's
    own phrasing (e.g. "I'm sorry") being misread as customer input, and
    (2) an older exact-format date elsewhere in history "winning" over a
    natural-language date the customer just gave in this message."""
    user_messages = [msg for msg in conversation_history if msg.get('role') == 'user']
    history_text = " ".join([msg.get('content', '') for msg in reversed(user_messages)])

    def pick(extractor):
        return extractor(current_message) or extractor(history_text)

    appointment = {
        'name': pick(extract_name),
        'email': pick(extract_email),
        'phone': pick(extract_phone),
        'date': pick(extract_date),
        'time': pick(extract_time),
        'service': extract_service(current_message) or extract_service(history_text) or 'General'
    }
    
    return appointment


@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Main endpoint for chat messages"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        user_id = data.get('user_id', 'guest')
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        if user_id not in conversations:
            conversations[user_id] = []
        
        print(f"\n📤 Sending request to Gemini...")
        ai_response = ai.get_ai_response(user_message, conversations[user_id])
        print(f"📥 Received response from Gemini ✅")
        
        ai_response, appointment_data = ai.extract_appointment_data(ai_response)
        intent = ai.detect_intent(user_message)
        
        save_to_chat_history(user_message, ai_response, intent)
        
        print(f"\n🔍 DEBUG INFO:")
        print(f"   User Message: {user_message[:60]}")
        print(f"   Intent: {intent}")
        print(f"   AI Extracted Data: {appointment_data}")
        
        if not appointment_data:
            appointment_data = build_appointment_from_conversation(conversations[user_id], user_message)
            print(f"   Built from Conversation: {appointment_data}")

        # If the date/time we just extracted matches a slot already
        # rejected earlier in this conversation (double-booked), don't
        # silently resubmit it - treat it as missing so we ask again.
        if user_id in rejected_slots and appointment_data.get('date') and appointment_data.get('time'):
            candidate_date = normalize_date(appointment_data.get('date'))
            candidate_time = normalize_time(appointment_data.get('time'))
            candidate_service = appointment_data.get('service')
            if (candidate_date, candidate_time, candidate_service) in rejected_slots[user_id]:
                print(f"   ⚠️ Extracted slot matches a previously rejected one - clearing date/time")
                appointment_data['date'] = None
                appointment_data['time'] = None

        # If date/time is present and DIFFERENT from what this user was
        # last discussing, require the service to be explicitly restated
        # in this exact message - don't silently reuse a service they
        # mentioned for a different date/time earlier in the conversation.
        if appointment_data.get('date') and appointment_data.get('time'):
            current_date = normalize_date(appointment_data.get('date'))
            current_time = normalize_time(appointment_data.get('time'))
            if current_date and current_time:
                previous_slot = last_slot.get(user_id)
                if previous_slot != (current_date, current_time):
                    service_in_this_message = extract_service(user_message)
                    if not service_in_this_message:
                        print(f"   ⚠️ Date/time changed - requiring service reconfirmation")
                        appointment_data['service'] = None
                    last_slot[user_id] = (current_date, current_time)
        
        has_complete_appointment = (
            appointment_data.get('email') and 
            appointment_data.get('name') and 
            appointment_data.get('date') and 
            appointment_data.get('time') and 
            appointment_data.get('service')
        )
        
        print(f"   Complete Appointment: {has_complete_appointment}")
        slot_conflict = False
        if has_complete_appointment:
            normalized_date = normalize_date(appointment_data.get('date'))
            normalized_time = normalize_time(appointment_data.get('time'))
            service = appointment_data.get('service')

            if normalized_date and normalized_time and is_slot_taken(normalized_date, normalized_time, service):
                slot_conflict = True
                rejected_slots.setdefault(user_id, set()).add((normalized_date, normalized_time, service))
                print(f"   ⚠️ Slot already booked: {normalized_date} {normalized_time} for {service}\n")
                ai_response = (
                    f"I'm sorry, but the {service} slot on {appointment_data.get('date')} "
                    f"at {appointment_data.get('time')} is already booked. "
                    f"Could you please choose a different date or time?"
                )
            else:
                saved_id = save_appointment(appointment_data)
                if saved_id is None:
                    print(f"   ❌ Appointment NOT saved (invalid data) — skipping confirmation email\n")
                    ai_response = (
                        "Sorry, I ran into an issue saving that appointment. "
                        "Could you please double-check the date and time and try again?"
                    )
                else:
                    print(f"   ✅ SENDING EMAIL TO: {appointment_data.get('email')}")
                    email_result = send_booking_confirmation(
                        customer_email=appointment_data.get('email'),
                        customer_name=appointment_data.get('name'),
                        appointment_data=appointment_data
                    )
                    print(f"   📧 Email result: {email_result}\n")
                    ai_response = (
                        f"You're all set, {appointment_data.get('name')}! Your {appointment_data.get('service')} "
                        f"is booked for {appointment_data.get('date')} at {appointment_data.get('time')}. "
                        f"A confirmation email has been sent to {appointment_data.get('email')}."
                    )
        else:
            missing = []
            if not appointment_data.get('email'):
                missing.append("Email")
            if not appointment_data.get('name'):
                missing.append("Name")
            if not appointment_data.get('date'):
                missing.append("Date")
            if not appointment_data.get('time'):
                missing.append("Time")
            if not appointment_data.get('service'):
                missing.append("Service")
            print(f"   ❌ Missing: {', '.join(missing)}\n")

        # Save to history AFTER ai_response is finalized (including any
        # slot-conflict or booking-confirmation override) so the next
        # turn's context reflects what the user actually saw.
        conversations[user_id].append({"role": "user", "content": user_message})
        conversations[user_id].append({"role": "assistant", "content": ai_response})
        if len(conversations[user_id]) > 20:
            conversations[user_id] = conversations[user_id][-20:]

        return jsonify({
            'response': ai_response,
            'intent': intent,
            'appointment_booked': has_complete_appointment and not slot_conflict
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Get all appointments from database"""
    try:
        query = """
        SELECT id, customer_name, email, phone, appointment_date,
               TIME_FORMAT(appointment_time, '%H:%i:%s') AS appointment_time,
               service_type, status, created_at
        FROM appointments
        ORDER BY appointment_date DESC
        """
        appointments = db.execute_query(query)
        return jsonify(appointments), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/appointments/<int:apt_id>', methods=['DELETE'])
def cancel_appointment(apt_id):
    """Cancel an appointment"""
    try:
        query = "UPDATE appointments SET status='cancelled' WHERE id=%s"
        db.update_data(query, (apt_id,))
        return jsonify({'success': True, 'message': 'Appointment cancelled'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def save_to_chat_history(user_msg, ai_msg, intent):
    """Save chat to database for learning"""
    try:
        query = """INSERT INTO chat_history 
                   (user_message, ai_response, intent, created_at) 
                   VALUES (%s, %s, %s, NOW())"""
        db.insert_data(query, (user_msg, ai_msg, intent))
        print(f"✅ Chat history saved")
    except Exception as e:
        print(f"❌ Error saving chat history: {e}")


def is_slot_taken(normalized_date, normalized_time, service):
    """Check if another active (non-cancelled) appointment already exists
    for this exact date + time + service combination."""
    query = """SELECT id FROM appointments
               WHERE appointment_date = %s
               AND appointment_time = %s
               AND service_type = %s
               AND status != 'cancelled'
               LIMIT 1"""
    existing = db.execute_query(query, (normalized_date, normalized_time, service))
    return bool(existing)


def save_appointment(apt_data):
    """Save appointment to database"""
    try:
        normalized_time = normalize_time(apt_data.get('time'))
        if normalized_time is None:
            print(f"❌ Could not save appointment: invalid time value '{apt_data.get('time')}'")
            return None

        normalized_date = normalize_date(apt_data.get('date'))
        if normalized_date is None:
            print(f"❌ Could not save appointment: invalid date value '{apt_data.get('date')}'")
            return None

        service = apt_data.get('service', 'General')

        # Safety net: even if the caller already checked availability,
        # re-check right before inserting to avoid a race condition where
        # two people book the same slot at nearly the same moment.
        if is_slot_taken(normalized_date, normalized_time, service):
            print(f"❌ Could not save appointment: slot already booked ({normalized_date} {normalized_time} - {service})")
            return None

        query = """INSERT INTO appointments 
                   (customer_name, email, phone, appointment_date, appointment_time, service_type, status) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        params = (
            apt_data.get('name', 'Unknown'),
            apt_data.get('email', ''),
            apt_data.get('phone', ''),
            normalized_date,
            normalized_time,
            service,
            'pending'
        )
        result = db.insert_data(query, params)
        print(f"✅ Appointment saved to database with ID: {result}")
        return result
    except Exception as e:
        print(f"❌ Error saving appointment: {e}")
        return None


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'Backend is running! ✅',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return jsonify({
        'message': '🏥 AI Receptionist API',
        'version': '1.0.0'
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)