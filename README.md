# Founderz.zw — Digital Solutions Platform

Founderz.zw is a modern digital solutions website built to help businesses and founders design, launch, and scale high-quality digital products. The platform combines a clean marketing website, a contact system, and an AI-assisted chatbot to guide potential clients.

---

## Features

- Responsive, modern marketing website
- Services and portfolio showcase
- “How We Work” process section
- Contact form with:
  - IP-based rate limiting
  - CSV storage
  - Instant email notifications
- Floating AI chatbot guided by website content
- Dark theme UI
- Secure backend practices (hashed admin passwords)

---

## Tech Stack

Frontend:
- HTML5
- CSS3
- JavaScript (Vanilla)
- SVG (Branding)

Backend:
- Python (Flask)
- Async email sending
- Supabase PostgreSQL

Deployment:
- Production-ready Flask setup
- Environment-based configuration
- Compatible with Render, Railway, or VPS

---

## Project Structure

project-root/
│
├── app.py
├── requirements.txt
├── .env.example
├── messages.csv
│
├── templates/
│   ├── index.html
│   ├── services.html
│   ├── portfolio.html
│   ├── about.html
│   └── footer.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   └── images/
│
└── README.md


## Contact Form Flow

1. User submits the contact form
2. Request is rate-limited by IP
3. Message is saved Neon DB
4. Admin notification email is sent
5. User receives an instant auto-reply
6. UI responds immediately (non-blocking)

---

## Chatbot

- Floating chatbot UI
- Guided by website content
- Handles:
  - Services information
  - Pricing ranges
  - Consultation intent


---

## Local Development

Create virtual environment and install dependencies:

python -m venv venv  
source venv/bin/activate   (Windows: venv\Scripts\activate)  
pip install -r requirements.txt  

Run the application:

python app.py  

Access the site at:

http://127.0.0.1:5000

---

## Deployment Checklist

- Environment variables configured
- Email sending tested in production
- Admin passwords hashed
- .env excluded from repository
- Static assets loading correctly
- Contact form verified
- Chatbot responsive

---

## License

This project is proprietary and built for Founderz.zw.  
All rights reserved.

---

Built with care by Founderz.zw  
Smart digital solutions for modern businesses
