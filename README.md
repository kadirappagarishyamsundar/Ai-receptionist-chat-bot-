# AI Receptionist 🏥

An AI-powered receptionist chatbot that handles appointment booking for a clinic through natural conversation. Built with Flask, MySQL, and Google Gemini, with a full admin dashboard for managing bookings.

## 🚀 Live Demo

- **Chat interface:** [ai-receptionist-chat-bot-production.up.railway.app/chat-ui](https://ai-receptionist-chat-bot-production.up.railway.app/chat-ui)
- **Admin dashboard:** [ai-receptionist-chat-bot-production.up.railway.app/admin/dashboard](https://ai-receptionist-chat-bot-production.up.railway.app/admin/dashboard)
- **API health check:** [ai-receptionist-chat-bot-production.up.railway.app/api/health](https://ai-receptionist-chat-bot-production.up.railway.app/api/health)

Deployed on Railway (Flask + MySQL). ⚠️ The admin dashboard has no authentication yet — this is a known limitation noted below, kept as-is for demo purposes. Please don't enter real personal data when testing.

## Features

- **Conversational appointment booking** — customers can book in plain English (e.g. "I'd like a Doctor Visit next Friday at 2pm")
- **Natural language date/time parsing** — understands exact dates (`24-07-2026`), relative dates (`tomorrow`, `day after tomorrow`), weekdays (`next Friday`), and written dates (`July 26th`)
- **Double-booking prevention** — automatically checks the database and rejects a date/time/service combo that's already taken, prompting the customer for an alternative
- **Service reconfirmation safeguard** — if a customer changes their requested date/time mid-conversation, the bot requires them to explicitly reconfirm the service rather than silently carrying over an old value
- **Automatic email confirmations** — sends a booking confirmation email once an appointment is successfully saved
- **Admin dashboard** — view all appointments, see stats (total/pending/completed), update appointment status, and cancel/delete bookings
- **Resilient database connection** — automatically reconnects if the MySQL connection drops due to inactivity

## Tech Stack

- **Backend:** Flask (Python)
- **Database:** MySQL
- **AI:** Google Gemini API
- **Email:** [Resend](https://resend.com) (HTTPS-based transactional email API)
- **Date parsing:** `python-dateutil` + custom natural-language handling
- **Frontend:** see `frontend/` directory

## Project Structure

```
ai-receptionist/
├── backend/
│   ├── app.py              # Main Flask app - chat endpoint, appointment logic
│   ├── admin_routes.py     # Admin dashboard routes and API
│   ├── database.py         # MySQL connection handling (with auto-reconnect)
│   ├── ai_handler.py       # Gemini API integration
│   ├── email_service.py    # Email confirmation logic
│   ├── templates/
│   │   └── admin_dashboard.html
│   ├── structure.sql       # Database schema
│   ├── requirements.txt
│   └── .env                # Environment variables (not committed)
└── frontend/                # Customer-facing chat interface
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/ai-receptionist.git
cd ai-receptionist/backend
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up the database

Run `structure.sql` against your MySQL instance to create the required tables (`appointments`, `users`, `chat_history`).

### 4. Configure environment variables

Create a `.env` file in `backend/` with:

```
DB_HOST=your-mysql-host
DB_USER=your-mysql-user
DB_PASSWORD=your-mysql-password
DB_NAME=your-database-name
GEMINI_API_KEY=your-gemini-api-key
RESEND_API_KEY=your-resend-api-key
MAIL_FROM=AI Receptionist <onboarding@resend.dev>
```

### 5. Run the app

```bash
python app.py
```

The API runs on `http://127.0.0.1:5000` by default.

### 6. Access the admin dashboard

```
http://127.0.0.1:5000/admin/dashboard
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Main chat endpoint for customer conversations |
| `/api/appointments` | GET | List all appointments |
| `/api/appointments/<id>` | DELETE | Cancel an appointment |
| `/admin/dashboard` | GET | Admin dashboard UI |
| `/admin/api/appointments` | GET | List appointments (admin view) |
| `/admin/api/appointments/<id>` | PUT | Update appointment status |
| `/admin/api/appointments/<id>` | DELETE | Delete an appointment |
| `/admin/api/stats` | GET | Dashboard statistics |
| `/api/health` | GET | Health check |

## Deployment Notes

Deployed on [Railway](https://railway.com) with a managed MySQL instance in the same project. A few things worth noting from getting this running in production:

- Railway's Free/Trial tier **blocks outbound SMTP ports** (25, 465, 587) to prevent abuse — a direct SMTP connection (e.g. via Flask-Mail to Gmail) will hang until it hits Gunicorn's worker timeout, silently killing the whole request. Switched to [Resend](https://resend.com), which sends over HTTPS (port 443) and isn't affected.
- Email sending runs on a background thread regardless, so a slow or failing email provider can never block or time out the main request — a booking always saves successfully even if the confirmation email fails.
- Railway's Root Directory setting scopes the entire build to that folder — the frontend had to live inside `backend/` (not as a sibling directory) to be included in the deployed container.

## Notes

- No authentication is currently implemented on the admin routes — before deploying publicly, add access control to `/admin/*`.
- Conversation state is stored in memory per session and is not persisted across server restarts.

## License

This project is for educational/portfolio purposes.