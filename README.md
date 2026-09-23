# AI-Powered Train Ticket Booking Assistant

A Flask web application for train search, AI-assisted recommendations, ticket booking, cancellation, booking history, admin management, analytics, and downloadable PDF tickets with QR codes.

## Features

- User registration, login, and protected booking history
- Train search by source, destination, travel date, passenger count, and preference
- AI-style train scoring for balanced, fastest, cheapest, and availability-first choices
- Alternate train suggestions when direct options are unavailable
- Ticket booking, cancellation, payment records, and booking history
- PDF ticket generation with QR code verification token
- PNR status lookup and railway assistance chatbot
- Admin dashboard for bookings, revenue, trains, stations, and availability updates
- SQLite development database by default, with MySQL support through `DATABASE_URL`

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app run.py init-db
python run.py
```

Open `http://127.0.0.1:5000`.

## Demo Accounts

- User: `demo@example.com` / `demo123`
- Admin: `admin@example.com` / `admin123`

## MySQL Configuration

Set `DATABASE_URL` before starting the app:

```powershell
$env:DATABASE_URL="mysql+pymysql://user:password@localhost/train_booking"
python -m flask --app run.py init-db
python run.py
```

## Project Structure

```text
app/
  __init__.py
  ai.py
  config.py
  extensions.py
  models.py
  routes.py
  seed.py
  tickets.py
  static/
  templates/
run.py
requirements.txt
```

