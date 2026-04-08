import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from io import BytesIO
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from smtplib import SMTPException
import random
import time
import tensorflow as tf
import numpy as np
from PIL import Image
from datetime import datetime, timedelta
import secrets
import re
import requests
import json
import urllib.parse
import urllib.request
import logging
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from flask_dance.contrib.google import make_google_blueprint, google
import os
import tensorflow as tf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "eye_disease_final_model.h5"
)

print("Model path:", MODEL_PATH)

model = tf.keras.models.load_model(MODEL_PATH)
app = Flask(__name__)


print("✅ Model loaded successfully")
app.secret_key = "super-secret-key"  # replace with a secure key for production
app.permanent_session_lifetime = timedelta(days=7)

# Flask-Mail configuration (replace with your Gmail credentials)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_TIMEOUT'] = 10
app.config['MAIL_DEBUG'] = True
app.config['MAIL_USERNAME'] = 'visionai.support@gmail.com'  # Replace with your Gmail
app.config['MAIL_PASSWORD'] = 'nhis qobc zrus cdwc'  # Replace with your app password
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
app.config['RECAPTCHA_SITE_KEY'] = "6LdUpqwsAAAAAOUupHoCIr-xVhrVL_6w0_l1GTDI"
app.config['RECAPTCHA_SECRET_KEY'] = "6LdUpqwsAAAAAFfbEZS4OpFoUlqsu9dWFOf6-6Fm"
app.config['GOOGLE_OAUTH_CLIENT_ID'] = '267279160765-h6rprgtrmuv6s0ak2d4km77sfbdl4lbb.apps.googleusercontent.com'  # Replace with actual client ID
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = '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'  # Replace with actual client secret

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
mail = Mail(app)
from flask_dance.contrib.google import make_google_blueprint

google_bp = make_google_blueprint(
    client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
    client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
    scope=[
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid"
    ],
    redirect_to="google_login"
)
app.register_blueprint(google_bp, url_prefix='/login')

app.config['DATABASE'] = os.path.join(app.root_path, 'app.db')

def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            fullname TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            verified INTEGER DEFAULT 0
        )''')
        cols = [row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'verified' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
        if 'name' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN name TEXT")
        if 'fullname' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN fullname TEXT")

        conn.execute('''CREATE TABLE IF NOT EXISTS remember_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expiry REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email):
    return bool(email and EMAIL_REGEX.match(email))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

CLASS_LABELS = [
    'Cataract',
    'Diabetic Retinopathy',
    'Glaucoma',
    'Normal'
]

DISEASE_DESCRIPTIONS = {
    'Cataract': 'Cataract causes clouding of the eye lens leading to blurry or faded vision.',
    'Glaucoma': 'Glaucoma damages the optic nerve and can gradually reduce peripheral vision.',
    'Diabetic Retinopathy': 'Diabetic retinopathy causes blood vessel damage in the retina due to diabetes.',
    'Normal': 'No signs of disease were detected. Maintain regular eye care and follow-up for continued health.'
}

MODEL_PATH = os.path.join(app.root_path, 'eye_disease_final_model.h5')

def custom_input_layer(*args, **kwargs):
    # Handle compatibility issues with InputLayer
    if 'batch_shape' in kwargs:
        batch_shape = kwargs.pop('batch_shape')
        if 'shape' not in kwargs:
            # Infer shape from batch_shape (assuming batch_size is None or first dim)
            if isinstance(batch_shape, (list, tuple)) and len(batch_shape) > 1:
                kwargs['shape'] = batch_shape[1:]  # Exclude batch dimension
    kwargs.pop('optional', None)
    return tf.keras.layers.InputLayer(*args, **kwargs)

# Custom objects for compatibility
custom_objects = {
    'InputLayer': custom_input_layer,
    'DTypePolicy': tf.keras.mixed_precision.Policy,  # Handle dtype policy issues
}

try:
    # Try loading with custom objects and compile=False
    model = tf.keras.models.load_model(MODEL_PATH, custom_objects=custom_objects, compile=False, safe_mode=False)
    logger.info('Eye disease model loaded successfully with custom objects.')
except Exception as exc:
    logger.error('Failed to load eye disease model with custom objects: %s', exc)
    try:
        # Fallback: try without custom objects
        model = tf.keras.models.load_model(MODEL_PATH, compile=False, safe_mode=False)
        logger.info('Eye disease model loaded with fallback (no custom objects).')
    except Exception as exc2:
        logger.error('Fallback load also failed: %s', exc2)
        try:
            # Try with keras if available (for Keras 3 models)
            import keras
            model = keras.models.load_model(MODEL_PATH, compile=False)
            logger.info('Eye disease model loaded with keras.models.load_model.')
        except ImportError:
            logger.warning('keras not available for loading.')
            model = None
        except Exception as exc3:
            logger.error('keras load also failed: %s', exc3)
            model = None


def preprocess_image(image_path, target_size=(224, 224)):
    image = Image.open(image_path).convert('RGB')
    image = image.resize(target_size)
    array = tf.keras.preprocessing.image.img_to_array(image)
    array = array / 255.0
    array = tf.expand_dims(array, 0)
    return array


def predict_eye_disease(image_path, model):
    if model is None:
        return {"prediction": "Error", "confidence": 0, "description": "Model is not available.", "severity": "N/A"}

    try:
        img_tensor = preprocess_image(image_path)
        preds = model.predict(img_tensor)
        print("Raw prediction:", preds)
        if preds is None or len(preds) == 0:
            return {"prediction": "Error", "confidence": 0, "description": "Invalid prediction output.", "severity": "N/A"}
        
        prediction = preds[0] if isinstance(preds, list) else preds
        prediction = np.array(prediction).flatten()
        print("Flattened prediction:", prediction)
        prediction = np.nan_to_num(prediction, nan=0.0)
        
        if len(prediction) == 0 or np.all(prediction == 0):
            return {"prediction": "Error", "confidence": 0, "description": "No valid prediction found.", "severity": "N/A"}
        
        confidence = float(np.max(prediction) * 100)
        top_index = int(np.argmax(prediction))
        print("Top index:", top_index)
        print("Predicted label:", CLASS_LABELS[top_index])
        disease = CLASS_LABELS[top_index] if top_index < len(CLASS_LABELS) else 'Unknown'
        
        if confidence > 80:
            severity = 'High'
        elif confidence > 50:
            severity = 'Medium'
        else:
            severity = 'Low'
        
        return {
            "prediction": disease,
            "confidence": confidence,
            "description": DISEASE_DESCRIPTIONS.get(disease, 'Prediction completed successfully.'),
            "severity": severity
        }
    except Exception as exc:
        logger.error('Prediction failed: %s', exc)
        return {"prediction": "Error", "confidence": 0, "description": "Prediction failed due to an internal error.", "severity": "N/A"}


def build_email_html(title, intro, code_label, code_value, expiry_text, support_email):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title}</title>
<style>
body {{ margin: 0; padding: 0; background: #f3f5f9; color: #111827; font-family: 'Poppins', Arial, sans-serif; }}
.wrapper {{ width: 100%; padding: 20px 0 32px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 22px; overflow: hidden; border: 1px solid rgba(15, 23, 42, 0.08); box-shadow: 0 24px 80px rgba(15, 23, 42, 0.08); }}
.inner {{ padding: 36px 30px; text-align: center; }}
.logo {{ width: 72px; height: auto; margin: 0 auto 24px; display: block; }}
.title {{ font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px; }}
.message {{ font-size: 16px; color: #475569; line-height: 1.8; margin: 0 auto 26px; max-width: 520px; }}
.code-box {{ display: inline-block; background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(168, 85, 247, 0.12)); padding: 24px 28px; border-radius: 18px; margin: 22px auto; min-width: 260px; }}
.code-label {{ display: block; font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: #6b7280; margin-bottom: 8px; }}
.code-value {{ font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #111827; }}
.expiry, .support, .footer {{ font-size: 14px; color: #6b7280; line-height: 1.7; margin: 20px auto 0; max-width: 520px; }}
.warning {{ margin: 18px auto 0; padding: 18px 20px; background: #f8fafc; border-left: 4px solid #6366f1; color: #111827; text-align: left; border-radius: 14px; max-width: 520px; }}
@media (max-width: 520px) {{ .inner {{ padding: 24px 18px; }} .title {{ font-size: 22px; }} .code-value {{ font-size: 28px; letter-spacing: 6px; }} }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="container">
    <div class="inner">
      <div class="title">{title}</div>
      <p class="message">{intro}</p>
      <div class="code-box">
        <span class="code-label">{code_label}</span>
        <div class="code-value">{code_value}</div>
      </div>
      <p class="expiry">{expiry_text}</p>
      <div class="warning">⚠️ Do not share this {code_label.upper()} with anyone.</div>
      <p class="support">If you did not request this, contact support at <a href="mailto:{support_email}">{support_email}</a>.</p>
      <p class="footer">This email is generated automatically by the system. Please do not reply to this email.</p>
    </div>
  </div>
</div>
</body>
</html>"""


def build_email_body(title, intro, code_label, code_value, expiry_text, support_email):
    return (
        f"{title}\n\n"
        f"{intro}\n\n"
        f"{code_label}: {code_value}\n"
        f"{expiry_text}\n\n"
        f"Do not share this {code_label.lower()} with anyone.\n"
        f"If you did not request this, contact support at {support_email}.\n\n"
        f"This email is generated automatically by the system. Please do not reply to this email."
    )

contact_rate_limit = {}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 3

def allow_contact_submission(ip):
    now = time.time()
    window = [t for t in contact_rate_limit.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
    contact_rate_limit[ip] = window
    if len(window) >= RATE_LIMIT_MAX:
        return False
    window.append(now)
    contact_rate_limit[ip] = window
    return True

def verify_recaptcha(token):
    secret = app.config.get("RECAPTCHA_SECRET_KEY")
    if not secret:
        return True
    payload = urllib.parse.urlencode({"secret": secret, "response": token}).encode()
    try:
        with urllib.request.urlopen("https://www.google.com/recaptcha/api/siteverify", data=payload, timeout=5) as response:
            result = json.loads(response.read().decode())
        return result.get("success", False)
    except Exception:
        return False

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        honeypot = request.form.get("website", "").strip()
        if honeypot:
            flash("Spam detected. Submission blocked.", "error")
            return redirect(url_for("contact"))

        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        if not allow_contact_submission(ip):
            flash("Too many contact requests. Please wait a minute before trying again.", "error")
            return redirect(url_for("contact"))

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        recaptcha_token = request.form.get("g-recaptcha-response", "").strip()

        if not name or not email or not message:
            flash("Please complete all fields before sending.", "error")
        elif len(name) > 100:
            flash("Name must be 100 characters or fewer.", "error")
        elif len(message) > 2000:
            flash("Message must be 2000 characters or fewer.", "error")
        elif not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
        elif app.config.get("RECAPTCHA_SITE_KEY") and not verify_recaptcha(recaptcha_token):
            flash("reCAPTCHA verification failed. Please try again.", "error")
        else:
            subject = f"Contact Form Submission from {name}"
            body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
            msg = Message(
                subject=subject,
                sender=app.config.get("MAIL_DEFAULT_SENDER"),
                recipients=[app.config.get("MAIL_USERNAME")],
                reply_to=email,
                body=body,
            )
            try:
                mail.send(msg)
                flash("Message sent successfully", "success")
            except SMTPException:
                flash("Unable to send message right now. Please try again later.", "error")
            except Exception:
                flash("Unable to send message right now. Please try again later.", "error")
        return redirect(url_for("contact"))
    return render_template("contact.html", recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not all([fullname, email, password, confirm_password]):
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("register"))

        recaptcha_token = request.form.get("g-recaptcha-response")
        if not recaptcha_token or not verify_recaptcha(recaptcha_token):
            flash("Please complete the reCAPTCHA verification.", "error")
            return redirect(url_for("register"))

        # Check if email already exists
        with get_db() as conn:
            existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user:
            flash("Email already registered. Please login instead.", "error")
            return redirect(url_for("login"))

        # Generate OTP
        otp = ''.join(random.choices('0123456789', k=6))

        # Send OTP email
        try:
            logger.debug("Preparing OTP email for %s", email)
            msg = Message(
                subject='Email Verification - Eye Disease Prediction System',
                sender=app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[email]
            )

            msg.html = build_email_html(
                title='Email Verification',
                intro='Thank you for using Eye Disease Prediction System. Please use the OTP below to verify your email address.',
                code_label='OTP Code',
                code_value=otp,
                expiry_text='This OTP is valid for 10 minutes.',
                support_email='visionai.support@gmail.com'
            )
            msg.body = build_email_body(
                title='Email Verification',
                intro='Thank you for using Eye Disease Prediction System. Please use the OTP below to verify your email address.',
                code_label='OTP Code',
                code_value=otp,
                expiry_text='This OTP is valid for 10 minutes.',
                support_email='visionai.support@gmail.com'
            )

            logger.debug("Sending OTP email to %s", email)
            mail.send(msg)
            logger.info("OTP email sent successfully to %s", email)

        except SMTPException as e:
            logger.exception("SMTP error while sending OTP to %s: %s", email, e)
            flash("Failed to send OTP email due to mail server authentication or connection issue. Please verify your SMTP credentials and network.", "error")
            return redirect(url_for("register"))
        except Exception as e:
            logger.exception("Unexpected error while sending OTP to %s: %s", email, e)
            flash("Failed to send OTP email. Please try again later.", "error")
            return redirect(url_for("register"))

        # Store in session
        hashed_password = generate_password_hash(password)
        session['otp'] = otp
        session['otp_email'] = email
        session['otp_time'] = time.time()
        session['user_data'] = {
            'fullname': fullname,
            'email': email,
            'password': hashed_password
        }

        flash("OTP sent to your email. Please verify.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("register.html", recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY"))

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if 'otp' not in session:
        flash("No OTP request found. Please register first.", "error")
        return redirect(url_for("register"))

    if request.method == "POST":
        entered_otp = request.form.get("otp")

        if not entered_otp:
            flash("Please enter the OTP.", "error")
            return redirect(url_for("verify_otp"))

        # Check expiration (10 minutes)
        if time.time() - session['otp_time'] > 600:
            flash("OTP has expired. Please request a new one.", "error")
            session.pop('otp', None)
            session.pop('otp_email', None)
            session.pop('otp_time', None)
            session.pop('user_data', None)
            return redirect(url_for("register"))

        if entered_otp == session['otp']:
            # Save user to database
            user_data = session['user_data']
            try:
                with get_db() as conn:
                    conn.execute("INSERT INTO users (fullname, email, password, verified) VALUES (?, ?, ?, 1)",
                               (user_data['fullname'], user_data['email'], user_data['password']))
                    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            except sqlite3.IntegrityError:
                flash("Email already registered.", "error")
                return redirect(url_for("register"))

            # Clear session
            session.pop('otp', None)
            session.pop('otp_email', None)
            session.pop('otp_time', None)
            session.pop('user_data', None)

            # Auto login
            session['user_id'] = user_id
            session['user_name'] = user_data['fullname']

            flash("Registration successful! Welcome.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid OTP. Please try again.", "error")

    return render_template("otp.html")

@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    if 'otp_email' not in session:
        return jsonify({"success": False, "message": "No OTP request found."}), 400

    otp = ''.join(random.choices('0123456789', k=6))

    try:
        logger.debug("Resending OTP email to %s", session.get('otp_email'))
        msg = Message('OTP Verification - Eye Disease Prediction System',
                     sender=app.config.get('MAIL_DEFAULT_SENDER'),
                     recipients=[session['otp_email']])

        msg.html = build_email_html(
            title='OTP Verification',
            intro='We received a request to resend your verification code. Use the OTP below to continue verifying your account.',
            code_label='OTP Code',
            code_value=otp,
            expiry_text='This OTP is valid for 10 minutes.',
            support_email='visionai.support@gmail.com'
        )
        msg.body = build_email_body(
            title='OTP Verification',
            intro='We received a request to resend your verification code. Use the OTP below to continue verifying your account.',
            code_label='OTP Code',
            code_value=otp,
            expiry_text='This OTP is valid for 10 minutes.',
            support_email='visionai.support@gmail.com'
        )

        mail.send(msg)
        logger.info("Resent OTP email successfully to %s", session.get('otp_email'))
    except SMTPException as e:
        logger.exception("SMTP error while resending OTP to %s: %s", session.get('otp_email'), e)
        return jsonify({"success": False, "message": "Failed to resend OTP email due to a mail server error."}), 500
    except Exception as e:
        logger.exception("Unexpected error while resending OTP to %s: %s", session.get('otp_email'), e)
        return jsonify({"success": False, "message": "Failed to resend OTP email due to an unexpected error."}), 500

    session['otp'] = otp
    session['otp_time'] = time.time()

    return jsonify({"success": True, "message": "OTP resent successfully."})

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        if not email:
            flash("Please enter your email.", "error")
            return redirect(url_for("forgot_password"))

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            flash("Email not registered.", "error")
            return redirect(url_for("forgot_password"))

        reset_otp = ''.join(random.choices('0123456789', k=6))
        try:
            logger.debug("Sending password reset OTP to %s", email)
            msg = Message('Password Reset - Eye Disease Prediction System',
                          sender=app.config.get('MAIL_DEFAULT_SENDER'),
                          recipients=[email])
            msg.html = build_email_html(
                title='Password Reset',
                intro='Use the OTP below to reset your password for your Eye Disease Prediction System account.',
                code_label='Password Reset OTP',
                code_value=reset_otp,
                expiry_text='This OTP is valid for 10 minutes.',
                support_email='visionai.support@gmail.com'
            )
            msg.body = build_email_body(
                title='Password Reset',
                intro='Use the OTP below to reset your password for your Eye Disease Prediction System account.',
                code_label='Password Reset OTP',
                code_value=reset_otp,
                expiry_text='This OTP is valid for 10 minutes.',
                support_email='visionai.support@gmail.com'
            )
            mail.send(msg)
            logger.info("Password reset OTP email sent successfully to %s", email)
        except SMTPException as e:
            logger.exception("SMTP error while sending password reset OTP to %s: %s", email, e)
            flash("Failed to send password reset email due to mail server error. Please try again later.", "error")
            return redirect(url_for("forgot_password"))
        except Exception as e:
            logger.exception("Unexpected error while sending password reset OTP to %s: %s", email, e)
            flash("Failed to send password reset email. Please try again later.", "error")
            return redirect(url_for("forgot_password"))

        session['reset_email'] = email
        session['reset_otp'] = reset_otp
        session['reset_time'] = time.time()

        flash("Password reset OTP sent to your email.", "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")

@app.route("/reset-password")
def reset_password():
    if 'reset_email' not in session:
        flash("No password reset request found. Please submit your email.", "error")
        return redirect(url_for("forgot_password"))

    return render_template("reset_password.html")

@app.route("/verify-reset", methods=["POST"])
def verify_reset():
    if 'reset_email' not in session or 'reset_otp' not in session:
        flash("No reset request found. Please start again.", "error")
        return redirect(url_for("forgot_password"))

    entered_otp = request.form.get("otp")
    new_password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not all([entered_otp, new_password, confirm_password]):
        flash("All fields are required.", "error")
        return redirect(url_for("reset_password"))

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("reset_password"))

    if time.time() - session['reset_time'] > 600:
        flash("OTP has expired. Please request a new one.", "error")
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_time', None)
        return redirect(url_for("forgot_password"))

    if entered_otp != session['reset_otp']:
        flash("Invalid OTP. Please try again.", "error")
        return redirect(url_for("reset_password"))

    hashed_password = generate_password_hash(new_password)
    with get_db() as conn:
        conn.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, session['reset_email']))

    session.pop('reset_email', None)
    session.pop('reset_otp', None)
    session.pop('reset_time', None)

    flash("Password reset successful. Please login.", "success")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return redirect(url_for("login"))

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("login"))

        if not check_password_hash(user['password'], password):
            flash("Invalid password.", "error")
            return redirect(url_for("login"))

        if user['verified'] != 1:
            flash("Please verify OTP first.", "error")
            return redirect(url_for("login"))

        session['user_id'] = user['id']
        session['user_name'] = user['fullname']
        remember = request.form.get("remember")
        if remember:
            # Generate remember token
            token = secrets.token_urlsafe(32)
            expiry = time.time() + (30 * 24 * 60 * 60)  # 30 days
            with get_db() as conn:
                conn.execute("INSERT INTO remember_tokens (user_id, token, expiry) VALUES (?, ?, ?)", 
                           (user['id'], token, expiry))
            session['remember_token'] = token
        flash("Login successful!", "success")
        return redirect(url_for("prediction"))

    return render_template("login.html")

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == 'GET':
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template('prediction.html', user_name=session.get('user_name'))
    
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required.'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400

    if not allowed_file(image_file.filename):
        return jsonify({'error': 'Unsupported file format.'}), 400

    filename = secure_filename(image_file.filename)
    save_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    image_file.save(save_path)

    
    prediction_data = predict_eye_disease(save_path, model)
    prediction_data['image_url'] = url_for('static', filename=f'uploads/{filename}')
    prediction_data['date'] = datetime.utcnow().strftime('%B %d, %Y')
    return render_template('prediction.html', disease=prediction_data['prediction'], confidence=round(prediction_data['confidence'], 2), severity=prediction_data['severity'], description=prediction_data['description'], date=prediction_data['date'], user_name=session.get('user_name'))

@app.route('/download_report')
def download_report():
    disease = request.args.get('disease', 'N/A')
    confidence = request.args.get('confidence', 'N/A')
    severity = request.args.get('severity', 'N/A')
    prediction_date = request.args.get('date', datetime.utcnow().strftime('%B %d, %Y'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    flowables = [
        Paragraph('Eye Disease Prediction Report', styles['Title']),
        Spacer(1, 14),
        Paragraph(f'<b>Disease Name:</b> {disease}', styles['Normal']),
        Spacer(1, 8),
        Paragraph(f'<b>Confidence Score:</b> {confidence}%', styles['Normal']),
        Spacer(1, 8),
        Paragraph(f'<b>Severity Level:</b> {severity}', styles['Normal']),
        Spacer(1, 8),
        Paragraph(f'<b>Prediction Date:</b> {prediction_date}', styles['Normal']),
        Spacer(1, 14),
        Table(
            [['Metric', 'Value'], ['Disease', disease], ['Confidence', f'{confidence}%'], ['Severity', severity], ['Date', prediction_date]],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F7DF3')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E6E9FF')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ])
        ),
        Spacer(1, 12),
        Paragraph('Generated by Eye Disease Prediction System', styles['Italic']),
    ]

    doc.build(flowables)
    buffer.seek(0)

    safe_date = prediction_date.replace(' ', '_').replace(',', '').replace('/', '-')
    return send_file(buffer, as_attachment=True, download_name=f'Eye-Prediction-Report-{safe_date}.pdf', mimetype='application/pdf')

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for("login"))
    return redirect(url_for('prediction'))

@app.route("/auto_login", methods=["POST"])
def auto_login():
    token = request.form.get("token")
    if not token:
        return jsonify({"success": False}), 400
    
    with get_db() as conn:
        row = conn.execute("SELECT user_id, expiry FROM remember_tokens WHERE token = ?", (token,)).fetchone()
        if not row:
            return jsonify({"success": False}), 401
        
        if time.time() > row['expiry']:
            # Expired, delete token
            conn.execute("DELETE FROM remember_tokens WHERE token = ?", (token,))
            return jsonify({"success": False}), 401
        
        # Valid, set session
        user = conn.execute("SELECT fullname FROM users WHERE id = ?", (row['user_id'],)).fetchone()
        if not user:
            return jsonify({"success": False}), 401
        
        session['user_id'] = row['user_id']
        session['user_name'] = user['fullname']
        session['remember_token'] = token  # Store token in session for logout
        return jsonify({"success": True})

@app.route("/login/google")
def login_google():
    if not google.authorized:
        return redirect(url_for('google.login'))
    return redirect(url_for('google_login'))

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for('login'))
    
    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        user_info = resp.json()
        email = user_info['email']
        name = user_info['name']
        
        # Check if user exists
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                # Create new user
                hashed_password = generate_password_hash(secrets.token_urlsafe(16))  # Random password
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (fullname, email, password, verified) VALUES (?, ?, ?, 1)",
                               (name, email, hashed_password))
                conn.commit()
                user_id = cursor.lastrowid
            else:
                user_id = user['id']
        
        session['user_id'] = user_id
        session['user_name'] = name
        flash("Login successful!", "success")
        return redirect(url_for("predict"))
    
    flash("Google login failed.", "error")
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    # If remember token exists, delete from DB
    token = session.get('remember_token')
    if token:
        with get_db() as conn:
            conn.execute("DELETE FROM remember_tokens WHERE token = ?", (token,))
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)