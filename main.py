# IMPORTS (ADD THREADING)
import threading

# ASYNC EMAIL FUNCTION
def send_otp_email_async(email, otp, fullname):
    """
    Send OTP email asynchronously in a background thread.
    Prevents blocking the main request/response cycle.
    """
    try:
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
            support_email=Config.SUPPORT_EMAIL
        )
        msg.body = build_email_body(
            title='Email Verification',
            intro='Thank you for using Eye Disease Prediction System. Please use the OTP below to verify your email address.',
            code_label='OTP Code',
            code_value=otp,
            expiry_text='This OTP is valid for 10 minutes.',
            support_email=Config.SUPPORT_EMAIL
        )
        
        with app.app_context():
            mail.send(msg)
            logger.info("OTP email sent successfully to %s", email)
    except SMTPException as e:
        logger.error("SMTP error sending OTP to %s: %s", email, e)
        print(f"[DEBUG] OTP for {email}: {otp}")
    except Exception as e:
        logger.exception("Error sending OTP email to %s: %s", email, e)
        print(f"[DEBUG] OTP for {email}: {otp}")

# UPDATED REGISTER ROUTE
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            fullname = request.form.get("fullname", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            recaptcha_token = request.form.get("g-recaptcha-response", "").strip()
            
            if not all([fullname, email, password, confirm_password]):
                flash("All fields are required.", "error")
                return redirect(url_for("register"))
            
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return redirect(url_for("register"))
            
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return redirect(url_for("register"))
            
            if not is_valid_email(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("register"))
            
            if not recaptcha_token:
                flash("Please complete the reCAPTCHA verification.", "error")
                return redirect(url_for("register"))
            
            if not verify_recaptcha(recaptcha_token):
                logger.warning('reCAPTCHA verification failed for email: %s', email)
                flash("reCAPTCHA verification failed. Please try again.", "error")
                return redirect(url_for("register"))
            
            try:
                with get_db() as conn:
                    existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                    if existing_user:
                        flash("Email already registered. Please login instead.", "error")
                        return redirect(url_for("login"))
            except sqlite3.Error as db_error:
                logger.exception('Database error checking existing user: %s', db_error)
                flash("Database error. Please try again later.", "error")
                return redirect(url_for("register"))
            
            otp = ''.join(random.choices('0123456789', k=6))
            
            hashed_password = generate_password_hash(password)
            session['otp'] = otp
            session['otp_email'] = email
            session['otp_time'] = time.time()
            session['last_resend_time'] = time.time()
            session['resend_count'] = 0
            session['user_data'] = {
                'fullname': fullname,
                'email': email,
                'password': hashed_password
            }
            
            thread = threading.Thread(target=send_otp_email_async, args=(email, otp, fullname), daemon=True)
            thread.start()
            logger.info("OTP email thread started for %s", email)
            
            flash("OTP sent to your email. Please verify.", "success")
            return redirect(url_for("verify_otp"))
        
        except Exception as e:
            logger.exception("Unexpected error during registration: %s", e)
            flash("An unexpected error occurred during registration. Please try again later.", "error")
            return redirect(url_for("register"))
    
    return render_template("register.html", recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY"))import os

if os.environ.get('FLASK_ENV') == 'development' or os.environ.get('DEBUG') == 'true':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from io import BytesIO
from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from smtplib import SMTPException
import random
import time
import threading
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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib import colors
from reportlab.lib.units import inch
from config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "eye_disease_final_model.h5"
)

print("Model path:", MODEL_PATH)

app = Flask(__name__)
app.config.from_object(Config)

print("✅ Model loaded successfully")
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = Config.MAIL_SERVER
app.config['MAIL_PORT'] = Config.MAIL_PORT
app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = Config.MAIL_USE_SSL
app.config['MAIL_TIMEOUT'] = Config.MAIL_TIMEOUT
app.config['MAIL_DEBUG'] = Config.MAIL_DEBUG
app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER
app.config['RECAPTCHA_SITE_KEY'] = Config.RECAPTCHA_SITE_KEY
app.config['RECAPTCHA_SECRET_KEY'] = Config.RECAPTCHA_SECRET_KEY
app.config['GOOGLE_OAUTH_CLIENT_ID'] = Config.GOOGLE_OAUTH_CLIENT_ID
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = Config.GOOGLE_OAUTH_CLIENT_SECRET

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
mail = Mail(app)

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
    client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

app.config['DATABASE'] = os.path.join(BASE_DIR, 'users.db')

def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
        with get_db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT,
                google_id TEXT
            )''')
            cols = [row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
            if 'google_id' not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
            if 'verified' not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
            if 'fullname' not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN fullname TEXT")

            conn.execute('''CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expiry REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                disease TEXT NOT NULL,
                confidence REAL NOT NULL,
                severity TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')
            conn.commit()
        logger.info('Database initialized at %s', app.config['DATABASE'])
    except sqlite3.Error as db_error:
        logger.exception('Database initialization failed: %s', db_error)
        raise

init_db()

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def send_otp_email_async(email, otp, fullname):
    """
    Send OTP email asynchronously in a background thread.
    Prevents blocking the main request/response cycle.
    """
    try:
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
            support_email=Config.SUPPORT_EMAIL
        )
        msg.body = build_email_body(
            title='Email Verification',
            intro='Thank you for using Eye Disease Prediction System. Please use the OTP below to verify your email address.',
            code_label='OTP Code',
            code_value=otp,
            expiry_text='This OTP is valid for 10 minutes.',
            support_email=Config.SUPPORT_EMAIL
        )
        
        with app.app_context():
            mail.send(msg)
            logger.info("OTP email sent successfully to %s", email)
    except SMTPException as e:
        logger.error("SMTP error sending OTP to %s: %s", email, e)
        print(f"[DEBUG] OTP for {email}: {otp}")
    except Exception as e:
        logger.exception("Error sending OTP email to %s: %s", email, e)
        print(f"[DEBUG] OTP for {email}: {otp}")


UPLOAD_FOLDER = Config.UPLOAD_FOLDER
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

MODEL_PATH = Config.MODEL_PATH

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
    try:
        secret = app.config.get("RECAPTCHA_SECRET_KEY")
        if not secret or not token or not isinstance(token, str):
            logger.warning('reCAPTCHA verification skipped: missing secret or token')
            return False
        
        token = token.strip()
        if not token:
            logger.warning('reCAPTCHA token is empty after stripping')
            return False
        
        payload = {'secret': secret, 'response': token}
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data=payload,
            timeout=5
        )
        response.raise_for_status()
        result = response.json()
        success = result.get('success', False)
        
        logger.debug('reCAPTCHA API response: success=%s, error_codes=%s', success, result.get('error-codes', []))
        
        if not success:
            logger.warning('reCAPTCHA verification failed: %s', result.get('error-codes', []))
        
        return success
    except requests.exceptions.Timeout:
        logger.error('reCAPTCHA verification timeout')
        return False
    except requests.exceptions.RequestException as e:
        logger.error('reCAPTCHA API request failed: %s', e)
        return False
    except Exception as e:
        logger.exception('Unexpected error during reCAPTCHA verification: %s', e)
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
        try:
            fullname = request.form.get("fullname", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            recaptcha_token = request.form.get("g-recaptcha-response", "").strip()
            
            if not all([fullname, email, password, confirm_password]):
                flash("All fields are required.", "error")
                return redirect(url_for("register"))
            
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return redirect(url_for("register"))
            
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return redirect(url_for("register"))
            
            if not is_valid_email(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("register"))
            
            if not recaptcha_token:
                flash("Please complete the reCAPTCHA verification.", "error")
                return redirect(url_for("register"))
            
            if not verify_recaptcha(recaptcha_token):
                logger.warning('reCAPTCHA verification failed for email: %s', email)
                flash("reCAPTCHA verification failed. Please try again.", "error")
                return redirect(url_for("register"))
            
            try:
                with get_db() as conn:
                    existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                    if existing_user:
                        flash("Email already registered. Please login instead.", "error")
                        return redirect(url_for("login"))
            except sqlite3.Error as db_error:
                logger.exception('Database error checking existing user: %s', db_error)
                flash("Database error. Please try again later.", "error")
                return redirect(url_for("register"))
            
            otp = ''.join(random.choices('0123456789', k=6))
            
            hashed_password = generate_password_hash(password)
            session['otp'] = otp
            session['otp_email'] = email
            session['otp_time'] = time.time()
            session['last_resend_time'] = time.time()
            session['resend_count'] = 0
            session['user_data'] = {
                'fullname': fullname,
                'email': email,
                'password': hashed_password
            }
            
            thread = threading.Thread(target=send_otp_email_async, args=(email, otp, fullname), daemon=True)
            thread.start()
            logger.info("OTP email thread started for %s", email)
            
            flash("OTP sent to your email. Please verify.", "success")
            return redirect(url_for("verify_otp"))
        
        except Exception as e:
            logger.exception("Unexpected error during registration: %s", e)
            flash("An unexpected error occurred during registration. Please try again later.", "error")
            return redirect(url_for("register"))
    
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

    # Check rate limiting: 60 seconds cooldown
    last_resend = session.get('last_resend_time', 0)
    current_time = time.time()
    if current_time - last_resend < 60:
        remaining_time = int(60 - (current_time - last_resend))
        return jsonify({"success": False, "message": f"Please wait {remaining_time} seconds before requesting a new OTP."}), 429

    # Check maximum attempts: 3 resends allowed
    resend_count = session.get('resend_count', 0)
    if resend_count >= 3:
        return jsonify({"success": False, "message": "Maximum resend attempts exceeded. Please register again."}), 429

    # Generate new OTP
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
            support_email=Config.SUPPORT_EMAIL
        )
        msg.body = build_email_body(
            title='OTP Verification',
            intro='We received a request to resend your verification code. Use the OTP below to continue verifying your account.',
            code_label='OTP Code',
            code_value=otp,
            expiry_text='This OTP is valid for 10 minutes.',
            support_email=Config.SUPPORT_EMAIL
        )

        mail.send(msg)
        logger.info("Resent OTP email successfully to %s", session.get('otp_email'))
    except SMTPException as e:
        logger.exception("SMTP error while resending OTP to %s: %s", session.get('otp_email'), e)
        return jsonify({"success": False, "message": "Failed to resend OTP email due to a mail server error."}), 500
    except Exception as e:
        logger.exception("Unexpected error while resending OTP to %s: %s", session.get('otp_email'), e)
        return jsonify({"success": False, "message": "Failed to resend OTP email due to an unexpected error."}), 500

    # Update session with new OTP and tracking info
    session['otp'] = otp
    session['otp_time'] = time.time()
    session['last_resend_time'] = current_time
    session['resend_count'] = resend_count + 1

    return jsonify({"success": True, "message": "OTP resent successfully."})

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handle forgot password - validate email and send OTP"""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        # Validate email provided
        if not email:
            flash("Please enter your email address.", "error")
            return redirect(url_for("forgot_password"))
        
        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("forgot_password"))

        # Check if email exists in database
        with get_db() as conn:
            user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            flash("Email not registered. Please check or register a new account.", "error")
            logger.warning("Password reset attempt for non-existent email: %s", email)
            return redirect(url_for("forgot_password"))

        # Generate secure OTP
        reset_otp = ''.join(random.choices('0123456789', k=6))
        current_time = time.time()
        
        try:
            logger.debug("Sending password reset OTP to %s", email)
            msg = Message('Password Reset - Eye Disease Prediction System',
                          sender=app.config.get('MAIL_DEFAULT_SENDER'),
                          recipients=[email])
            msg.html = build_email_html(
                title='Password Reset',
                intro='We received a request to reset your password. Use the OTP below to continue. This OTP is valid for only 5 minutes.',
                code_label='Password Reset OTP',
                code_value=reset_otp,
                expiry_text='This code expires in 5 minutes.',
                support_email=Config.SUPPORT_EMAIL
            )
            msg.body = build_email_body(
                title='Password Reset',
                intro='We received a request to reset your password. Use the OTP below to continue. This OTP is valid for only 5 minutes.',
                code_label='Password Reset OTP',
                code_value=reset_otp,
                expiry_text='This code expires in 5 minutes.',
                support_email=Config.SUPPORT_EMAIL
            )
            mail.send(msg)
            logger.info("Password reset OTP sent successfully to %s", email)
        except SMTPException as e:
            logger.exception("SMTP error sending password reset OTP to %s: %s", email, e)
            flash("Failed to send password reset email. Please verify email and try again.", "error")
            return redirect(url_for("forgot_password"))
        except Exception as e:
            logger.exception("Error sending password reset OTP to %s: %s", email, e)
            flash("An unexpected error occurred. Please try again later.", "error")
            return redirect(url_for("forgot_password"))

        # Store reset session data with rate limiting info
        session['reset_email'] = email
        session['reset_otp'] = reset_otp
        session['reset_time'] = current_time
        session['reset_attempts'] = 0
        session['last_resend_time'] = current_time
        session['resend_count'] = 0

        flash("Password reset OTP has been sent to your email.", "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")

@app.route("/reset-password", methods=["GET"])
def reset_password():
    """Display password reset form with OTP verification"""
    if 'reset_email' not in session:
        flash("No password reset request found. Please start over.", "error")
        return redirect(url_for("forgot_password"))
    
    # Check if OTP has expired (5 minutes)
    if time.time() - session.get('reset_time', 0) > 300:
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_time', None)
        flash("OTP has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    return render_template("reset_password.html", reset_email=session.get('reset_email'))

@app.route("/verify-reset", methods=["POST"])
def verify_reset():
    """Verify OTP and reset password"""
    if 'reset_email' not in session or 'reset_otp' not in session:
        flash("No password reset request found. Please start over.", "error")
        return redirect(url_for("forgot_password"))

    entered_otp = request.form.get("otp", "").strip()
    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    # Validate all fields provided
    if not all([entered_otp, new_password, confirm_password]):
        flash("All fields are required.", "error")
        return redirect(url_for("reset_password"))

    # Validate OTP format (6 digits)
    if len(entered_otp) != 6 or not entered_otp.isdigit():
        flash("OTP must be 6 digits.", "error")
        return redirect(url_for("reset_password"))

    # Validate password requirements
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for("reset_password"))

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("reset_password"))

    # Check OTP expiry (5 minutes)
    if time.time() - session.get('reset_time', 0) > 300:
        flash("OTP has expired. Please request a new one.", "error")
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_time', None)
        return redirect(url_for("forgot_password"))

    # Track failed attempts
    session['reset_attempts'] = session.get('reset_attempts', 0) + 1
    
    # Limit verification attempts to 3
    if session['reset_attempts'] > 3:
        flash("Too many failed attempts. Please request a new OTP.", "error")
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_time', None)
        return redirect(url_for("forgot_password"))

    # Verify OTP
    if entered_otp != session['reset_otp']:
        remaining_attempts = 3 - session['reset_attempts']
        flash(f"Invalid OTP. {remaining_attempts} attempts remaining.", "error")
        return redirect(url_for("reset_password"))

    # Hash and update password in database
    hashed_password = generate_password_hash(new_password)
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password = ? WHERE email = ?",
                (hashed_password, session['reset_email'])
            )
            conn.commit()
        logger.info("Password reset successful for email: %s", session['reset_email'])
    except Exception as e:
        logger.exception("Error updating password for email %s: %s", session['reset_email'], e)
        flash("An error occurred while resetting your password. Please try again.", "error")
        return redirect(url_for("reset_password"))

    # Clear session data
    session.pop('reset_email', None)
    session.pop('reset_otp', None)
    session.pop('reset_time', None)
    session.pop('reset_attempts', None)
    session.pop('last_resend_time', None)
    session.pop('resend_count', None)

    flash("Password reset successful! You can now login with your new password.", "success")
    return redirect(url_for("login"))

@app.route("/resend-reset-otp", methods=["POST"])
def resend_reset_otp():
    """Resend OTP during password reset with rate limiting"""
    if 'reset_email' not in session:
        return jsonify({"success": False, "message": "No password reset request found."}), 400

    # Check rate limiting: 60 seconds cooldown
    last_resend = session.get('last_resend_time', 0)
    current_time = time.time()
    if current_time - last_resend < 60:
        remaining_time = int(60 - (current_time - last_resend))
        return jsonify({
            "success": False,
            "message": f"Please wait {remaining_time} seconds before requesting a new OTP."
        }), 429

    # Check maximum resend attempts (3 total resends allowed)
    resend_count = session.get('resend_count', 0)
    if resend_count >= 3:
        return jsonify({
            "success": False,
            "message": "Maximum resend attempts exceeded. Please request a new reset."
        }), 429

    # Generate new OTP
    reset_otp = ''.join(random.choices('0123456789', k=6))
    email = session['reset_email']

    try:
        logger.debug("Resending password reset OTP to %s", email)
        msg = Message('Password Reset - Eye Disease Prediction System',
                      sender=app.config.get('MAIL_DEFAULT_SENDER'),
                      recipients=[email])
        msg.html = build_email_html(
            title='Password Reset (Resend)',
            intro='Here is your new password reset OTP. This code is valid for 5 minutes.',
            code_label='New Password Reset OTP',
            code_value=reset_otp,
            expiry_text='This code expires in 5 minutes.',
            support_email=Config.SUPPORT_EMAIL
        )
        msg.body = build_email_body(
            title='Password Reset (Resend)',
            intro='Here is your new password reset OTP. This code is valid for 5 minutes.',
            code_label='New Password Reset OTP',
            code_value=reset_otp,
            expiry_text='This code expires in 5 minutes.',
            support_email=Config.SUPPORT_EMAIL
        )
        mail.send(msg)
        logger.info("Password reset OTP resent to %s", email)
    except SMTPException as e:
        logger.exception("SMTP error resending password reset OTP: %s", e)
        return jsonify({
            "success": False,
            "message": "Failed to resend OTP. Please try again."
        }), 500
    except Exception as e:
        logger.exception("Error resending password reset OTP: %s", e)
        return jsonify({
            "success": False,
            "message": "An error occurred. Please try again."
        }), 500

    # Update session
    session['reset_otp'] = reset_otp
    session['reset_time'] = current_time
    session['last_resend_time'] = current_time
    session['resend_count'] = resend_count + 1
    session['reset_attempts'] = 0

    return jsonify({
        "success": True,
        "message": "New OTP sent to your email."
    }), 200

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/google/callback')
def google_callback():
    try:
        try:
            token = google.authorize_access_token()
            userinfo = google.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
        except Exception as auth_error:
            logger.exception("OAuth authorization failed: %s", auth_error)
            flash("Failed to authorize with Google. Please try again.", "error")
            return redirect(url_for('login'))
        
        email = userinfo.get('email', '').strip()
        name = (userinfo.get('name') or '').strip()
        google_id = userinfo.get('id', '').strip()

        if not email:
            logger.warning('Google OAuth returned no email')
            flash("Email not provided by Google. Please try again.", "error")
            return redirect(url_for('login'))

        try:
            with get_db() as conn:
                user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if user:
                    if google_id and not user['google_id']:
                        conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user['id']))
                    session['user_id'] = user['id']
                    session['user_name'] = user['name'] or user['fullname'] or email
                    session.permanent = True
                    logger.info("Google OAuth login successful for email: %s", email)
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))

                try:
                    conn.execute(
                        "INSERT INTO users (name, email, password, google_id, verified) VALUES (?, ?, NULL, ?, 1)",
                        (name, email, google_id)
                    )
                    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                except sqlite3.IntegrityError as integrity_error:
                    logger.warning("Integrity error during OAuth registration: %s", integrity_error)
                    existing_user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                    if existing_user:
                        if google_id and not existing_user['google_id']:
                            conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, existing_user['id']))
                        session['user_id'] = existing_user['id']
                        session['user_name'] = existing_user['name'] or existing_user['fullname'] or email
                        session.permanent = True
                        logger.info("Google OAuth login successful (existing) for email: %s", email)
                        flash("Login successful!", "success")
                        return redirect(url_for('dashboard'))
                    raise

                session['user_id'] = user_id
                session['user_name'] = name or email
                session.permanent = True
                logger.info("Google OAuth registration and login successful for email: %s", email)
                flash("Account created and login successful!", "success")
                return redirect(url_for('dashboard'))
        except sqlite3.Error as db_error:
            logger.exception("Database error during Google OAuth callback: %s", db_error)
            flash("Database error. Please try again later.", "error")
            return redirect(url_for('login'))
    except Exception as e:
        logger.exception("Unexpected error during Google OAuth callback: %s", e)
        flash("OAuth login failed. Please try again.", "error")
        return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()

            if not email or not password:
                flash("Please enter both email and password.", "error")
                return redirect(url_for("login"))

            try:
                with get_db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            except sqlite3.Error as db_error:
                logger.exception("Database error during login: %s", db_error)
                flash("Database error. Please try again later.", "error")
                return redirect(url_for("login"))

            if not user:
                flash("User not found. Please register first.", "error")
                return redirect(url_for("login"))

            if user['password'] is None:
                flash("Account created via OAuth. Please login with Google.", "error")
                return redirect(url_for("login"))

            if not check_password_hash(user['password'], password):
                flash("Invalid password.", "error")
                return redirect(url_for("login"))

            if user['verified'] != 1:
                flash("Please verify your email first.", "error")
                return redirect(url_for("login"))

            session['user_id'] = user['id']
            session['user_name'] = user['fullname'] or user['name'] or user['email']
            session.permanent = True
            
            remember = request.form.get("remember")
            if remember:
                try:
                    token = secrets.token_urlsafe(32)
                    expiry = time.time() + (30 * 24 * 60 * 60)
                    with get_db() as conn:
                        conn.execute("INSERT INTO remember_tokens (user_id, token, expiry) VALUES (?, ?, ?)", 
                                   (user['id'], token, expiry))
                    session['remember_token'] = token
                except sqlite3.Error as db_error:
                    logger.exception("Error creating remember token: %s", db_error)
            
            flash("Login successful!", "success")
            return redirect(url_for("predict"))
        
        except Exception as e:
            logger.exception("Unexpected error during login: %s", e)
            flash("An unexpected error occurred. Please try again later.", "error")
            return redirect(url_for("login"))
    
    return render_template("login.html")

    return render_template("login.html")

def check_duplicate_prediction(user_id, image_hash, disease):
    """
    Check if a prediction already exists for this user with the same image and disease.
    Prevents duplicate records within a 30-second window to handle accidental double submissions.
    """
    with get_db() as conn:
        result = conn.execute(
            '''SELECT id, date FROM predictions 
               WHERE user_id = ? AND disease = ? AND image_path LIKE ? 
               AND datetime(date) > datetime('now', '-30 seconds')
               ORDER BY date DESC LIMIT 1''',
            (user_id, disease, f'%{image_hash}%')
        ).fetchone()
    return result is not None

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == 'GET':
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template('prediction.html', user_name=session.get('user_name'))
    
    # POST request - AJAX submission from frontend
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file uploaded.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400

    if not allowed_file(image_file.filename):
        return jsonify({'success': False, 'error': 'Only JPG and PNG retinal images are supported.'}), 400

    # Create filename with timestamp to ensure uniqueness
    timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
    base_filename = os.path.splitext(secure_filename(image_file.filename))[0]
    extension = os.path.splitext(image_file.filename)[1]
    filename = f"{base_filename}_{timestamp}{extension}"
    
    save_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    image_file.save(save_path)

    # Generate prediction
    prediction_data = predict_eye_disease(save_path, model)
    prediction_data['image_url'] = url_for('static', filename=f'uploads/{filename}')
    prediction_data['date'] = datetime.utcnow().strftime('%B %d, %Y')
    prediction_data['filename'] = filename
    
    # Save prediction to database (only if not an error and not a duplicate)
    prediction_id = None
    if prediction_data['prediction'] != 'Error':
        # Check for duplicates before inserting
        if not check_duplicate_prediction(session['user_id'], base_filename, prediction_data['prediction']):
            try:
                with get_db() as conn:
                    conn.execute(
                        '''INSERT INTO predictions (user_id, image_path, disease, confidence, severity, date)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (session['user_id'], f'uploads/{filename}', prediction_data['prediction'],
                         round(prediction_data['confidence'], 2), prediction_data['severity'], 
                         datetime.utcnow())
                    )
                    conn.commit()
                    # Get the inserted prediction ID
                    result = conn.execute(
                        "SELECT last_insert_rowid() as id"
                    ).fetchone()
                    if result:
                        prediction_id = result['id']
                logger.info(f"Prediction saved for user {session['user_id']}: {prediction_data['prediction']} (ID: {prediction_id})")
            except Exception as e:
                logger.exception(f"Error saving prediction: {e}")
                # Continue anyway - we still return the prediction result
        else:
            logger.warning(f"Duplicate prediction detected for user {session['user_id']}. Skipping database insert.")
    
    # Return JSON response for AJAX handler
    return jsonify({
        'success': True,
        'prediction': prediction_data['prediction'],
        'confidence': round(prediction_data['confidence'], 2),
        'severity': prediction_data['severity'],
        'description': prediction_data['description'],
        'date': prediction_data['date'],
        'filename': prediction_data['filename'],
        'prediction_id': prediction_id
    }), 200

@app.route('/download_report')
def download_report():
    disease = request.args.get('disease', 'N/A')
    confidence = request.args.get('confidence', 'N/A')
    severity = request.args.get('severity', 'N/A')
    prediction_date = request.args.get('date', datetime.utcnow().strftime('%B %d, %Y'))
    image_filename = request.args.get('image', '')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=50, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    # Create custom style for title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6,
        alignment=1  # centered
    )
    
    story = []

    # Header with logo and title (in a table for layout)
    try:
        logo_path = os.path.join(BASE_DIR, 'static', 'logo.png')
        if os.path.exists(logo_path):
            # Create header table with logo on left, text on right
            logo_img = RLImage(logo_path, width=0.9*inch, height=0.9*inch)
            header_data = [[logo_img, Paragraph('<b>EyePredict</b><br/><font size=12>Eye Disease Prediction Report</font>', styles['Normal'])]]
            header_table = Table(header_data, colWidths=[1.2*inch, 4.8*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (0, 0), 0),
                ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ]))
            story.append(header_table)
        else:
            story.append(Paragraph('EyePredict - Eye Disease Prediction Report', title_style))
    except Exception as e:
        logger.debug(f"Could not load logo: {e}")
        story.append(Paragraph('EyePredict - Eye Disease Prediction Report', title_style))
    
    # Horizontal line below header
    story.append(Spacer(1, 12))
    line_table = Table([['', '', '']], colWidths=[6*inch + 72/5, 0.02*inch, 0.02*inch])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), 2, colors.HexColor('#D1D5DB')),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 14))
    
    # Generated date
    story.append(Paragraph(f"<font size=9 color='#64748B'><i>Report Generated: {prediction_date}</i></font>", styles['Normal']))
    story.append(Spacer(1, 16))

    # Include image if available
    if image_filename:
        try:
            img_path = os.path.join(UPLOAD_FOLDER, image_filename)
            if os.path.exists(img_path):
                img = Image.open(img_path)
                img_width = 3 * 72  # 3 inches
                img_height = (img.height / img.width) * img_width
                story.append(Paragraph('<b>Uploaded Retinal Image</b>', styles['Heading3']))
                story.append(Spacer(1, 8))
                story.append(RLImage(img_path, width=img_width, height=img_height))
                story.append(Spacer(1, 18))
        except Exception as e:
            logger.debug(f"Could not include image in PDF: {e}")
    
    # Prediction Details
    story.append(Paragraph('<b>PREDICTION RESULTS</b>', styles['Heading2']))
    story.append(Spacer(1, 10))
    
    details_data = [
        ['Metric', 'Result'],
        ['Disease Name', disease],
        ['Confidence Score', f'{confidence}%'],
        ['Severity Level', severity],
        ['Analysis Date', prediction_date]
    ]
    
    details_table = Table(details_data, colWidths=[2*72, 3*72])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F3F4F6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 20))
    
    # Medical Description
    description = DISEASE_DESCRIPTIONS.get(disease, 'N/A')
    story.append(Paragraph('<b>Medical Information</b>', styles['Heading2']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(description, styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Footer
    story.append(Paragraph('<font size=8 color="#94A3B8">―――――――――――――――――――――――――――――――――――――――</font>', styles['Normal']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        '<font size=9 color="#64748B"><i>This report is generated by EyePredict AI system. '
        'For medical concerns, please consult with an ophthalmologist. '
        'This is not a substitute for professional medical advice.</i></font>',
        styles['Normal']
    ))

    doc.build(story)
    buffer.seek(0)

    safe_date = prediction_date.replace(' ', '_').replace(',', '').replace('/', '-')
    return send_file(buffer, as_attachment=True, download_name=f'EyePredict-Report-{safe_date}.pdf', mimetype='application/pdf')

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for("login"))
    return redirect(url_for('predict'))


# DEBUG ROUTE - Remove after fixing duplicate issue
@app.route("/debug_predictions")
def debug_predictions():
    """Debug route to check for duplicate predictions in database."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    
    with get_db() as conn:
        # Get all predictions
        all_predictions = conn.execute(
            'SELECT id, disease, confidence, date FROM predictions WHERE user_id = ? ORDER BY date DESC',
            (user_id,)
        ).fetchall()
        
        # Count by disease to find duplicates
        disease_counts = {}
        for pred in all_predictions:
            disease = pred['disease']
            disease_counts[disease] = disease_counts.get(disease, 0) + 1
    
    return jsonify({
        'total_predictions': len(all_predictions),
        'predictions': [dict(p) for p in all_predictions],
        'disease_counts': disease_counts,
        'duplicates_detected': {d: c for d, c in disease_counts.items() if c > 1}
    }, 200)

@app.route("/my_reports")
def my_reports():
    if 'user_id' not in session:
        flash("Please log in to view your reports.", "error")
        return redirect(url_for("login"))
    
    # Fetch reports for current user, ordered by latest first
    # Using DISTINCT ON id to prevent any duplicate rows in case they exist in database
    with get_db() as conn:
        reports = conn.execute(
            '''SELECT DISTINCT id, image_path, disease, confidence, severity, date 
               FROM predictions 
               WHERE user_id = ? 
               ORDER BY date DESC''',
            (session['user_id'],)
        ).fetchall()
    
    reports_list = [dict(report) for report in reports]
    logger.debug(f"Loaded {len(reports_list)} reports for user {session['user_id']}")
    
    return render_template('my_reports.html', reports=reports_list, user_name=session.get('user_name'))

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
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)