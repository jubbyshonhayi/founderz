from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime
import functools
import os
import threading
import time
from collections import defaultdict
from openai import OpenAI
import psycopg2
import psycopg2.extras


# ---------------- OpenAI Client ----------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------- Flask App ----------------
app = Flask(__name__)

# ---------------- Keep-alive Ping Setup ----------------
KEEP_ALIVE_INTERVAL = 10 * 60  # 10 minutes
APP_URL = os.getenv("APP_URL")  

def keep_alive():
    while True:
        try:
            requests.get(APP_URL, timeout=5)
            print("Keep-alive ping sent")
        except Exception as e:
            print("Keep-alive failed:", e)
        time.sleep(KEEP_ALIVE_INTERVAL)

threading.Thread(target=keep_alive, daemon=True).start()

# ---------------- Flask Config ----------------
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# ---------------- Rate limiting storage ----------------
RATE_LIMIT = defaultdict(list)

# ---------------- Email config ----------------
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")


# ---------------- Supabase / PostgreSQL setup ----------------
DATABASE_URL = os.getenv("DATABASE_URL")  

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Ensure SSL (Supabase requirement)
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def ensure_sslmode(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query.setdefault("sslmode", ["require"])
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

DATABASE_URL = ensure_sslmode(os.getenv("DATABASE_URL"))


def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=3
    )



# ---------------- DB Init (cold-start optimized) ----------------
_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    message TEXT,
                    date TEXT
                );
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS consultations (
                    id SERIAL PRIMARY KEY,
                    date TEXT,
                    user_message TEXT,
                    intent TEXT,
                    stage TEXT
                );
                """)
            conn.commit()
        _db_initialized = True
    except Exception as e:
        print("DB init failed (will retry on next request):", e)



# ---------------- Helpers ----------------
def is_rate_limited_ip(ip, per_minute=3, per_hour=10):
    now = time.time()
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < 3600]
    last_minute = [t for t in RATE_LIMIT[ip] if now - t < 60]

    if len(last_minute) >= per_minute:
        wait = int(60 - (now - last_minute[0]))
        return True, f"Too fast. Wait {wait} seconds."

    if len(RATE_LIMIT[ip]) >= per_hour:
        wait = int(3600 - (now - RATE_LIMIT[ip][0]))
        return True, f"Hourly limit reached. Try again in {wait//60} minutes."

    RATE_LIMIT[ip].append(now)
    return False, None

# ---------------- Helper to require environment variables ----------------
def _require_env(key: str) -> str:
    """Get environment variable or raise an error if missing."""
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def login_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            flash("You must log in first!", "warning")
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper

import requests

def send_email(subject, body, to_email):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": os.getenv("BREVO_API_KEY"),
        "Content-Type": "application/json"
    }

    data = {
        "sender": {"name": "Founderz", "email": EMAIL_ADDRESS},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body
    }

    r = requests.post(url, json=data, headers=headers)
    if r.status_code >= 400:
        print("Email API error:", r.text)

def send_email_async(subject, body, to_email):
    threading.Thread(
        target=send_email,
        args=(subject, body, to_email),
        daemon=True
    ).start()


# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/contact", methods=["POST"])
def contact():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    limited, message = is_rate_limited_ip(ip)
    if limited:
        return jsonify({"status": "error", "message": message}), 429

    data = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "phone": request.form.get("phone"),
        "message": request.form.get("message"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    data["admin_body"] = f"""
New contact form submission

Name: {data['name']}
Email: {data['email']}
Phone: {data['phone']}

Message:
{data['message']}

Date: {data['date']}
"""

    data["user_body"] = f"""
Hi {data['name']},

Thank you for contacting Founderz.zw 👋
We’ve received your message and will get back to you shortly.

— Founderz Team
"""

    # 🔥 FIRE AND FORGET
    threading.Thread(
        target=contact_background_task,
        args=(data,),
        daemon=True
    ).start()

    # 🚀 RETURN IMMEDIATELY
    return jsonify({
        "status": "success",
        "message": "Message sent successfully! We’ll get back to you shortly."
    })

def contact_background_task(data):
    # --------- DB (non-critical) ---------
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO messages (name, email, phone, message, date)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    data["name"],
                    data["email"],
                    data["phone"],
                    data["message"],
                    data["date"]
                ))
            conn.commit()
    except Exception as e:
        print("⚠️ DB insert failed (email will still send):", e)

    # --------- EMAILS (critical) ---------
    try:
        send_email(
            "📩 New Website Contact Message",
            data["admin_body"],
            RECEIVER_EMAIL
        )

        send_email(
            "We received your message – Founderz",
            data["user_body"],
            data["email"]
        )
    except Exception as e:
        print("❌ Email sending failed:", e)


# ---------------- Multi-admin setup ----------------
ADMINS_PLAIN = {
    "admin": _require_env("ADMIN_ADMIN_PASSWORD"),
    "john": _require_env("ADMIN_JOHN_PASSWORD"),
    "alice": _require_env("ADMIN_ALICE_PASSWORD")
}

# Pre-hash once at startup
ADMINS = {user: generate_password_hash(pw) for user, pw in ADMINS_PLAIN.items()}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Missing username or password", "danger")
            return redirect("/login")

        hashed_pw = ADMINS.get(username)
        if hashed_pw and check_password_hash(hashed_pw, password):
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            flash(f"Welcome, {username}!", "success")
            return redirect("/admin")

        flash("Invalid username or password", "danger")
        return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    username = session.get("username", "")
    session.clear()
    flash(f"{username} logged out successfully!", "success")
    return redirect("/login")

@app.route("/admin")
@login_required
def admin_dashboard():

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM messages ORDER BY id DESC")
            messages = cur.fetchall()

    return render_template("admin.html", messages=messages)

@app.route("/delete-message/<int:msg_id>")
@login_required
def delete_message(msg_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE id=%s", (msg_id,))
        conn.commit()

    flash("Message deleted successfully!", "success")
    return redirect("/admin")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/services")
def services():
    return render_template("services.html")

@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")

@app.route("/contacts")
def contacts():
    return render_template("contact.html")

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    msg = data.get("message", "").strip().lower()

    if not msg:
        return jsonify({"reply": "Please type something to start the conversation."})

    consultation_keywords = ["book", "consultation", "schedule", "call", "meeting", "proceed"]
    affirmative_words = ["yes", "yeah", "yep", "sure", "okay", "alright"]

    consultation_intent = any(word in msg for word in consultation_keywords) or msg in affirmative_words
    stage = "conversation"
    
    try:
        if consultation_intent:
            stage = "consultation_confirmed"
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                       INSERT INTO consultations (date, user_message, intent, stage)
                       VALUES (%s, %s, %s, %s)
                    """, (
                       datetime.now().strftime("%Y-%m-%d %H:%M"),
                       msg,
                      "consultation",
                      stage
                ))
                conn.commit()
    except Exception as db_err:
        print("⚠️ Consultation DB insert failed:", db_err)
       # DO NOT block chatbot


    
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": (
                    "You are Founderz Assistant for Founderz.zw.\n"
                    "Founderz.zw provides digital solutinos including:\n"
                    "- Web development (mini to full stack webss).\n"
                    "- School and business systems.\n"
                    "- AI and automation solutions.\n"
                    "- Deployment and maintenance services.\n\n"
                    "You are already in an ongoing conversation.\n"
                    "You DO NOT assist with coding, programming or technical advice.\n"
                    "You ONLY discuss Founderz.zw services and NO assitance on PERSONAL NEEDS of USERS.\n\n"
                    "You are professional, friendly, concise and sales-oriented"
                    "You guide users naturally toward a consultation without being pushy.\n"
                    "You NEVER restart the conversation or repeat greetings once chatting has started.\n"
                    "You ALWAYS continue from the user's last message.\n\n"
                    "Behavior rules:\n"
                    "- Treat one-word replies like 'yes' or 'okay' as CONTINUATION.\n"
                    "- Maintain context at all times.\n"
                    "- Ask ONE question at a time.\n"
                    "- Give detailed answers and examples where necessary\n"
                    "- Avoid use of jargon or heavy technical terms\n"
                    "- Avoid Giving code snippets or programming advice.\n"
                    "- Avoid Giving generic AI responses.\n"
                    "- Avoid discussing topics outside a Digital Solutions business context.\n"
                    "- Always focus on technological solutions for businesses, companies and schools.\n"
                    "- Do not ask questions that have already been answered.\n"
                    "- If user says 'thanks' or 'thank you', reply with a polite closing.\n\n"
                    "Pricing rules:\n"
                    "- Always give a realistic PRICE RANGE in USD.\n"
                    "- Never give exact pricing.\n"
                    "- Keep it simple and confidence-building.\n"
                    " - In case the price is not mentioned in the examples below try to give realistic pricess Range starting from the very minimum.\n"
                    "- Examples:\n"
                    "  * simple informational sites: $20-$100\n"
                    "  * Mini website: $150–$400\n"
                    "  * Business website: $400–$1,500+\n"
                    "  * School systems: $800–$3,000+\n"
                    "  * Full-stack systems: $800+\n"
                    "  * chatbots and automation: $100-$800"
                    "  * AI solutions: $500–$1,500+\n\n"
                    "Consultation handling:\n"
                    "- If consultation intent is detected:\n"
                    " - Acknowledge and confirm the user's intent to book a consultation.\n"
                    "  1. Confirm booking intent\n"
                    "  2. Provide contact form link: /contacts\n"
                    "  3. Explain what happens next\n"
                    "  4. make your reply short\n\n"
                    "Tone:\n"
                    "- Confident\n"
                    "- Human\n"
                    "- Professional\n"
                    "- Clear\n"
                    "- Not robotic\n\n"
                    "Services:\n"
                    "- AI & automation\n"
                    "- School & business systems\n"
                    "- Full-stack & mini web development\n"
                    "- Deployment & maintenance"
                )},
                {"role": "user", "content": msg}
            ]
        )
         
        reply = response.output_text.strip()
        if not reply:
            raise ValueError("Empty AI response")


        if consultation_intent:
            reply += (
                "\n\n👉 To proceed, please fill in our contact form:\n"
                "Use the BOOK NOW button on the home page or the HIRE US button in the header.\n\n"
                "Once submitted, our team will reach out to schedule your consultation."
            )

    except Exception as e:
        print("OpenAI API error:", e)
        reply = "Sorry, I couldn't process your request. Please try again later."

    return jsonify({"reply": reply})

@app.route("/health")
def health():
    return "OK", 200


@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}


@app.before_request
def startup():
    init_db()



# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)