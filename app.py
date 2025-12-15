from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import smtplib
from email.message import EmailMessage
from datetime import datetime
import functools
import os
import threading
import time
from collections import defaultdict
from openai import OpenAI


# ---------------- OpenAI Client ----------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------- Flask App ----------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")


# ---------------- Rate limiting storage ----------------
RATE_LIMIT = defaultdict(list)


# ---------------- Email config ----------------
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")


# ---------------- Multi-admin setup ----------------
ADMINS = {
    "admin": generate_password_hash(os.getenv("ADMIN_ADMIN_PASSWORD")),
    "john": generate_password_hash(os.getenv("ADMIN_JOHN_PASSWORD")),
    "alice": generate_password_hash(os.getenv("ADMIN_ALICE_PASSWORD"))
}


# ---------------- CSV file for messages ----------------
MESSAGES_FILE = "data/messages.csv"
os.makedirs("data", exist_ok=True)

if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Email", "Phone", "Message", "Date"])

CONSULT_FILE = "data/consultations.csv"

if not os.path.exists(CONSULT_FILE):
    with open(CONSULT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "User Message", "Intent", "Stage"])

# ---------------- Helpers ----------------

def is_rate_limited_ip(ip, per_minute=1, per_hour=5):
    now = time.time()

    # Clean old entries (older than 1 hour)
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < 3600]

    # Count messages
    last_minute = [t for t in RATE_LIMIT[ip] if now - t < 60]
    last_hour = RATE_LIMIT[ip]

    if len(last_minute) >= per_minute:
        wait = int(60 - (now - last_minute[0]))
        return True, f"Too fast. Wait {wait} seconds."

    if len(last_hour) >= per_hour:
        wait = int(3600 - (now - last_hour[0]))
        return True, f"Hourly limit reached. Try again in {wait//60} minutes."

    RATE_LIMIT[ip].append(now)
    return False, None


def login_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            flash("You must log in first!", "warning")
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper


def send_email(subject, body, to_email):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


def send_email_async(subject, body, to_email):
    def task():
        try:
            send_email(subject, body, to_email)
        except Exception as e:
            print("Async email failed:", e)

    threading.Thread(target=task, daemon=True).start()

# ---------------- Routes ----------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/contact", methods=["POST"])
def contact():

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    limited, message = is_rate_limited_ip(ip)
    if limited:
        return jsonify({
            "status": "error",
            "message": message
        }), 429
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    message = request.form.get("message")
    date_sent = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1️⃣ Save instantly
    with open(MESSAGES_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([name, email, phone, message, date_sent])

    # 2️⃣ Prepare emails
    admin_body = f"""
New contact form submission

Name: {name}
Email: {email}
Phone: {phone}

Message:
{message}

Date: {date_sent}
"""

    user_body = f"""
Hi {name},

Thank you for contacting Founderz.zw 👋

We’ve received your message and will get back to you shortly.

📩 Your message:
"{message}"

— Founderz Team
"""

    # 3️⃣ Send emails ASYNC (non-blocking)
    send_email_async(
        "📩 New Website Contact Message",
        admin_body,
        RECEIVER_EMAIL
    )

    send_email_async(
        "We received your message – Founderz",
        user_body,
        email
    )

    # 4️⃣ Instant response (no delay)
    return jsonify({
        "status": "success",
        "message": "Message sent successfully! We’ll get back to you shortly."
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in ADMINS and check_password_hash(ADMINS[username], password):
            session["logged_in"] = True
            session["username"] = username
            flash(f"Welcome, {username}!", "success")
            return redirect("/admin")
        else:
            flash("Invalid username or password", "danger")

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
    messages = []
    with open(MESSAGES_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)
        for idx, row in enumerate(reader):
            messages.append({
                "id": idx,
                "name": row[0],
                "email": row[1],
                "phone": row[2],
                "message": row[3],
                "date": row[4]
            })
    return render_template("admin.html", messages=messages)


@app.route("/delete-message/<int:msg_id>")
@login_required
def delete_message(msg_id):
    with open(MESSAGES_FILE, "r") as f:
        reader = list(csv.reader(f))
        header, rows = reader[0], reader[1:]

    if 0 <= msg_id < len(rows):
        rows.pop(msg_id)
        with open(MESSAGES_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
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

    # ---- Simple intent detection (VERY IMPORTANT) ----
    consultation_keywords = [
        "book", "consultation", "schedule", "call", "meeting", "proceed"
    ]
    affirmative_words = ["yes", "yeah", "yep", "sure", "okay", "alright"]

    consultation_intent = (
        any(word in msg for word in consultation_keywords)
        or msg in affirmative_words
    )

    stage = "conversation"

    if consultation_intent:
        stage = "consultation_confirmed"

        # Save consultation intent
        with open(CONSULT_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                msg,
                "consultation",
                stage
            ])

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are Founderz Assistant for Founderz.zw.\n"

                        "Founderz.zw provides digital solutinos including:\n"
                        "- Web development (mini to full stack webss).\n"
                        "- School and business systems.\n"
                        "- AI and automation solutions.\n"
                        "- Deployment and maintenance services.\n\n"


                        "You are already in an ongoing conversation.\n"
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
                        "- Always give a realistic  PRICE RANGE in USD.\n"
                        "- Never give exact pricing.\n"
                        "- Keep it simple and confidence-building.\n"
                        "  Always clarify that prices vary based on project scope and requirements.\n"
                        "- Examples:\n"
                        "  * Mini website: $150–$400\n"
                        "  * Business website: $400–$1,500+\n"
                        "  * School systems: $800–$3,000+\n"
                        "  *Full-stack systems: $800+\n"
                        "  * AI solutions: $500–$5,000+\n\n"
                        
                        "if user replies with short answers like 'yes', 'sure', 'okay', 'yeah', 'sure','ok':\n"
                        "- Treat as agreement and MOVE FORWARD.\n"
                        "- Do not as what they want again.\n"
                        "- Continue the conversation naturally from last message.\n\n"

                        "Consultation handling:\n"
                        "- If consultation intent is detected:\n"
                        "  1. Confirm booking intent\n"
                        "  2. Provide contact form link: /contacts\n"
                        "  3. Explain what happens next\n\n"

                        "Tone:\n"
                        "Your tone shoud feel like a helpful business consultant:\n"
                        "- Confident\n"
                        "- Human\n"
                        "- Professional\n"
                        "- Clear\n"
                        "- Not overly long\n"
                        "- Not robotic\n\n"

                        "When appropriate, encourage action using soft language such as:\n"
                        "- The best next step would be...\n"
                        "- To give you an accurate quote...\n"
                        "- A quick consultation will help us...\n\n"

                        "Remember, your goal is to assist users in understanding Founderz.zw's services and guide them toward booking a consultation."

                        "Services:\n"
                        "- AI & automation\n"
                        "- School & business systems\n"
                        "- Full-stack & mini web development\n"
                        "- Deployment & maintenance"
                    )
                },
                {
                    "role": "user",
                    "content": msg
                }
            ]
        )

        reply = response.output_text.strip()

        # ---- Post-process reply if consultation intent ----
        if consultation_intent:
            reply += (
                "\n\n👉 To proceed, please fill in our contact form:\n"
                "You can do that by pressing the BOOK NOW button on the home page or by clicking the HIRE US button on the top right header \n\n"
                "Once submitted, our team will reach out to schedule your consultation."
            )

    except Exception as e:
        print("OpenAI API error:", e)
        reply = "Sorry, I couldn't process your request. Please try again later."

    return jsonify({"reply": reply})

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}


# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
