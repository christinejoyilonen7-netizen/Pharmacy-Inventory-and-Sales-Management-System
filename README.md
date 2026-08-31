# Pharmacy Inventory and Sales Management System

A working Flask web application for managing pharmacy medicines, suppliers, customers, and sales.

## Features
- Login and logout
- Dashboard statistics
- Medicine inventory CRUD (add, view, edit, delete)
- Supplier management
- Customer management
- Sales recording with automatic stock deduction
- Low-stock and expiring-medicine alerts
- SQLite database
- Basic validation and authorization guard

## Run locally

```bash
python -m venv venv
```

Activate it:

**Windows**
```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open `http://127.0.0.1:5000`

### Demo account
- Username: `admin`
- Password: `admin123`

## Project Structure

```text
app.py
requirements.txt
render.yaml
templates/
static/
```

## Deploy on Render
Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app
```

Set a strong `SECRET_KEY` environment variable before production use.
