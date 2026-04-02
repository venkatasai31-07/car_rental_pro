try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import random
import hashlib
import hmac
from datetime import datetime
import uuid
import smtplib
from email.message import EmailMessage
import razorpay
import json
import os
import joblib
import numpy as np
from dotenv import load_dotenv

import google.generativeai as genai
import uuid as uuid_lib
import sys, os

# Load environment variables from .env file
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_assistant.rag.retriever import search_knowledge

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "fallback_key_if_needed")
genai.configure(api_key=GEMINI_API_KEY)


app = Flask(__name__)
CORS(app)

bcrypt = Bcrypt(app)


# ============================================
# 📦 LOAD ML MODEL + ENCODERS + METADATA
# ============================================
ML_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ml_model = None
ml_encoders = None
car_metadata = {"companies": [], "models": {}}

try:
    meta_path = os.path.join(ML_BASE_DIR, "car_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            car_metadata = json.load(f)
    print("✅ ML Metadata pre-loaded successfully!")
except Exception as e:
    print(f"⚠️ Metadata loading warning: {e}")

def load_ml_model_lazy():
    """Lazily loads the model and encoders only when needed to save RAM during startup."""
    global ml_model, ml_encoders
    if ml_model is None:
        print("📥 Lazily loading ML Model and Encoders (RAM spike expected)...")
        try:
            model_path = os.path.join(ML_BASE_DIR, "ui_price_model.pkl")
            encoder_path = os.path.join(ML_BASE_DIR, "ui_encoders.pkl")
            if os.path.exists(model_path):
                ml_model = joblib.load(model_path)
            if os.path.exists(encoder_path):
                ml_encoders = joblib.load(encoder_path)
            print("✅ ML Model components loaded successfully!")
        except Exception as e:
            print(f"❌ Lazy ML loading failed: {e}")
    return ml_model, ml_encoders




DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)



# 🔥 SECRETS (Loaded from .env)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "supersecret123")

# ⭐ RAZORPAY KEYS
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
# -----------------------------
# DATABASE CONNECTION
# -----------------------------



# -----------------------------
# CREATE TABLES
# -----------------------------
try:
    with engine.begin() as conn:
        print("✅ Connected to Supabase successfully!")
        
        # 🔥 CREATE TRACKING TABLE IF NOT EXISTS
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS trip_locations (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER UNIQUE NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Tracking table verified/created")

        # 🔥 CREATE AI CHATS TABLE
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS ai_chats (
                id SERIAL PRIMARY KEY,
                email TEXT,
                role TEXT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        '''))
        print("✅ AI Chats table verified/created")

        
        # 🔥 CREATE PARCELS TABLE
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS parcels (
                id SERIAL PRIMARY KEY,
                sender_email VARCHAR(255) NOT NULL,
                pickup_location VARCHAR(255) NOT NULL,
                drop_location VARCHAR(255) NOT NULL,
                parcel_description TEXT,
                parcel_weight VARCHAR(50),
                receiver_name VARCHAR(255) NOT NULL,
                receiver_mobile VARCHAR(20) NOT NULL,
                booking_id INTEGER REFERENCES bookings(id),
                status VARCHAR(50) DEFAULT 'Pending', -- Pending, Accepted, Picked Up, Delivered, Rejected
                pickup_qr_code VARCHAR(255),
                delivery_otp VARCHAR(4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Parcels table verified/created")

        # 🔥 CREATE SELLING TABLE
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS selling (
                id SERIAL PRIMARY KEY,
                owner_email VARCHAR(255) NOT NULL,
                company VARCHAR(100) NOT NULL,
                model VARCHAR(100) NOT NULL,
                reg_number VARCHAR(50) UNIQUE NOT NULL,
                year INTEGER,
                fuel VARCHAR(50),
                transmission VARCHAR(50),
                km INTEGER,
                owner_type VARCHAR(50),
                location VARCHAR(255),
                selling_price BIGINT,
                description TEXT,
                images TEXT,
                status VARCHAR(50) DEFAULT 'Pending', -- Pending, Approved, Rejected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Selling table verified/created")

        # 🔥 CREATE BUY REQUESTS TABLE
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS buy_requests (
                id SERIAL PRIMARY KEY,
                car_id INTEGER REFERENCES selling(id),
                seller_email VARCHAR(255) NOT NULL,
                buyer_email VARCHAR(255) NOT NULL,
                buyer_name VARCHAR(255),
                buyer_mobile VARCHAR(20),
                offered_price BIGINT,
                status VARCHAR(50) DEFAULT 'Pending', -- Pending, Accepted, Rejected, Paid
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Buy Requests table verified/created")

        # 🔥 CREATE DRIVERS TABLE
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS drivers (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                dob DATE,
                gender VARCHAR(50),
                address TEXT,
                mobile VARCHAR(20) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                license_number VARCHAR(100) NOT NULL,
                license_type VARCHAR(50),
                license_expiry DATE,
                vehicle_type VARCHAR(50),
                vehicle_model VARCHAR(100),
                account_number VARCHAR(50),
                ifsc_code VARCHAR(20),
                upi_id VARCHAR(100),
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Drivers table verified/created")
except Exception as e:
    print("❌ DB Init failed:", e)

@app.route("/")
def home():
    return "Backend is running ✅"

# -----------------------------
# EMAIL FUNCTION
# -----------------------------
def send_email(receiver, subject, html_body):

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = receiver

    msg.add_alternative(html_body, subtype='html')

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)


# temporary OTP store
otp_store = {}

def send_booking_email(data):

    receiver = data.get("customer_email")

    # 🔥 SAFETY CHECK (VERY IMPORTANT)
    if not receiver:
        print("No customer email found — skipping email.")
        return

    msg = EmailMessage()
    msg["Subject"] = "🚗 Your Car Booking is Confirmed!"
    msg["From"] = EMAIL_USER
    msg["To"] = receiver

    html = f"""
    <html>
    <body style="font-family:Arial;background:#f2f3f5;padding:20px;">

        <div style="
            max-width:600px;
            background:white;
            padding:30px;
            border-radius:12px;
            box-shadow:0px 3px 10px rgba(0,0,0,0.1);
        ">

            <h2 style="color:#28a745;">✅ Booking Confirmed</h2>

            <p>Hello <b>{data.get("customer_name")}</b>,</p>

            <p>
            Your car booking has been <b>successfully confirmed</b>.  
            Below are your booking details:
            </p>

            <hr>

            <h3 style="color:#333;">🚘 Booking Details</h3>

            <p><b>Car:</b> {data.get("car_name")}</p>
            <p><b>Rental Type:</b> {data.get("rental_type")}</p>
            <p><b>Pickup Location:</b> {data.get("pickup_location")}</p>
            <p><b>Drop Location:</b> {data.get("drop_location")}</p>

            <p><b>Pickup Time:</b> {data.get("pickup_datetime")}</p>
            <p><b>Drop Time:</b> {data.get("drop_datetime")}</p>

            <h2 style="color:#007bff;">
                💰 Total Fare: ₹{data.get("total_cost")}
            </h2>
    """

    # ⭐ SHOW DRIVER DETAILS if present (for With Driver OR assigned Platform Driver)
    if data.get("driver_name") and data.get("driver_mobile"):
        html += f"""
            <hr>

            <h3 style="color:#333;">👨‍✈️ Driver Details</h3>

            <p><b>Name:</b> {data.get("driver_name")}</p>
            <p><b>Mobile:</b> {data.get("driver_mobile")}</p>

            <p style="color:#666;font-size:13px;">
            Please contact the driver for trip coordination.
            </p>
        """

    html += """
            <hr>

            <p style="color:gray;">
            Thank you for choosing our service 🚗  
            Wishing you a safe and comfortable journey!
            </p>

        </div>

    </body>
    </html>
    """

    msg.add_alternative(html, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)

        print("✅ Booking email sent successfully!")

    except Exception as e:
        # 🔥 NEVER CRASH BOOKING BECAUSE OF EMAIL
        print("❌ Email failed but booking is saved:", e)


def send_parcel_accepted_email(receiver, parcel_data):
    """
    Sends a detailed email to the sender when a parcel is accepted.
    Includes the 12-digit pickup code and an embedded QR code.
    """
    msg = EmailMessage()
    msg["Subject"] = "📦 Your Parcel Request is Accepted!"
    msg["From"] = EMAIL_USER
    msg["To"] = receiver

    code = parcel_data.get("pickup_qr_code")
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={code}"

    html = f"""
    <html>
    <body style="font-family:Arial;background:#f2f3f5;padding:20px;">
        <div style="max-width:600px;background:white;padding:30px;border-radius:12px;box-shadow:0px 3px 10px rgba(0,0,0,0.1);">
            <h2 style="color:#00c9a7;">✅ Parcel Request Accepted</h2>
            <p>Great news! A driver has accepted your parcel delivery request.</p>
            
            <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
            
            <h3 style="color:#333;">📦 Pickup Details</h3>
            <p><b>Description:</b> {parcel_data.get("parcel_description")}</p>
            <p><b>Pickup:</b> {parcel_data.get("pickup_location")}</p>
            <p><b>Drop:</b> {parcel_data.get("drop_location")}</p>
            
            <div style="background:#f9f9f9; padding:20px; border-radius:12px; text-align:center; margin:20px 0;">
                <p style="margin-bottom:10px; font-weight:700; color:#666;">Verification Code for Pickup</p>
                <div style="font-size:24px; font-weight:800; letter-spacing:4px; color:#2a2545; margin-bottom:15px;">{code}</div>
                <img src="{qr_url}" alt="QR Code" style="border:10px solid white; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <p style="margin-top:15px; font-size:12px; color:#888;">Show this code/QR to the driver at the time of pickup.</p>
            </div>

            <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">

            <p style="color:gray; font-size:13px;">
                Thank you for using CarRentalPro Parcel Logistics. <br>
                Track your parcel live in the "My Parcels" section.
            </p>
        </div>
    </body>
    </html>
    """

    msg.add_alternative(html, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ Parcel acceptance email sent to {receiver}")
    except Exception as e:
        print("❌ Parcel email failed:", e)


def send_parcel_delivered_email(receiver, parcel_data):
    """
    Sends a confirmation email to the sender when their parcel is successfully delivered.
    """
    msg = EmailMessage()
    msg["Subject"] = "🎁 Your Parcel has been Delivered!"
    msg["From"] = EMAIL_USER
    msg["To"] = receiver

    html = f"""
    <html>
    <body style="font-family:Arial;background:#f2f3f5;padding:20px;">
        <div style="max-width:600px;background:white;padding:30px;border-radius:12px;box-shadow:0px 3px 10px rgba(0,0,0,0.1);">
            <h2 style="color:#28a745;">✨ Parcel Delivered!</h2>
            <p>Hello,</p>
            <p>We are happy to inform you that your parcel has been <b>successfully delivered</b> to the receiver.</p>
            
            <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
            
            <h3 style="color:#333;">📦 Delivery Summary</h3>
            <p><b>Description:</b> {parcel_data.get("parcel_description")}</p>
            <p><b>Receiver Name:</b> {parcel_data.get("receiver_name")}</p>
            <p><b>Pickup:</b> {parcel_data.get("pickup_location")}</p>
            <p><b>Drop:</b> {parcel_data.get("drop_location")}</p>
            
            <div style="background:#e8f5e9; padding:15px; border-radius:10px; text-align:center; margin:20px 0;">
                <p style="color:#2e7d32; font-weight:700; margin:0;">Status: DELIVERED ✅</p>
            </div>

            <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">

            <p style="color:gray; font-size:13px;">
                Thank you for trusting CarRentalPro Parcel Logistics. <br>
                We hope to serve you again soon!
            </p>
        </div>
    </body>
    </html>
    """

    msg.add_alternative(html, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ Parcel delivery confirmation email sent to {receiver}")
    except Exception as e:
        print("❌ Parcel delivery email failed:", e)


def send_parcel_receiver_otp(mobile, otp, receiver_name):
    """
    Simulates sending an SMS to the parcel receiver with the delivery OTP.
    """
    # In a real-world app, you'd use Twilio or similar here.
    # For now, we simulate and log it.
    print(f"📱 SMS SENT TO {mobile} ({receiver_name}): Your OTP for parcel delivery is {otp}. Please provide this to the driver upon delivery.")


# -----------------------------
# DRIVER REGISTRATION
# -----------------------------
@app.route("/register-driver", methods=["POST"])
def register_driver():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid request ❌"}), 400
        
    try:
        with engine.begin() as conn:
            # Check duplicate email or mobile
            result = conn.execute(
                text("SELECT id FROM drivers WHERE email=:email OR mobile=:mobile"),
                {"email": data.get("email"), "mobile": data.get("mobile")}
            )
            if result.fetchone():
                return jsonify({"success": False, "message": "Driver with this email/mobile already exists ❌"}), 400
                
            conn.execute(text("""
                INSERT INTO drivers(
                    full_name, dob, gender, address, mobile, email,
                    license_number, license_type, license_expiry,
                    vehicle_type, vehicle_model,
                    account_number, ifsc_code, upi_id
                ) VALUES (
                    :full_name, :dob, :gender, :address, :mobile, :email,
                    :license_number, :license_type, :license_expiry,
                    :vehicle_type, :vehicle_model,
                    :account_number, :ifsc_code, :upi_id
                )
            """), {
                "full_name": data.get("full_name"),
                "dob": data.get("dob") if data.get("dob") else None,
                "gender": data.get("gender"),
                "address": data.get("address"),
                "mobile": data.get("mobile"),
                "email": data.get("email"),
                "license_number": data.get("license_number"),
                "license_type": data.get("license_type"),
                "license_expiry": data.get("license_expiry") if data.get("license_expiry") else None,
                "vehicle_type": data.get("vehicle_type"),
                "vehicle_model": data.get("vehicle_model"),
                "account_number": data.get("account_number"),
                "ifsc_code": data.get("ifsc_code"),
                "upi_id": data.get("upi_id")
            })
        return jsonify({"success": True, "message": "Driver registration successful! Welcome to the team."})
    except Exception as e:
        print("Driver Registration Error:", e)
        return jsonify({"success": False, "message": "Database error ❌"}), 500

# -----------------------------
# ADMIN DRIVER MANAGEMENT
# -----------------------------
@app.route("/admin/pending-drivers")
def pending_drivers():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT * FROM drivers
            WHERE status='Pending'
        """))
        drivers = [dict(row) for row in result.mappings().all()]
    return jsonify({"success": True, "drivers": drivers})

@app.route("/admin/update-driver-status", methods=["POST"])
def update_driver_status():
    data = request.get_json()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE drivers SET status=:status WHERE id=:driver_id
        """), {
            "status": data.get("status"),
            "driver_id": data.get("driver_id")
        })
    return jsonify({"success": True, "message": "Driver status updated! ✅"})

@app.route("/admin/driver-requests", methods=["GET"])
def get_driver_requests():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT id, car_id, car_name, customer_name, customer_mobile, 
                   pickup_location, drop_location, pickup_datetime, drop_datetime, booking_status
            FROM bookings
            WHERE booking_status='Pending Platform Driver'
            ORDER BY pickup_datetime ASC
        """))
        requests = [dict(row) for row in result.mappings().all()]
        for req in requests:
            # Convert datetime to string for JSON serialization
            req['pickup_datetime'] = str(req['pickup_datetime'])
            req['drop_datetime'] = str(req['drop_datetime'])
            
    return jsonify({"success": True, "requests": requests})

@app.route("/admin/available-drivers", methods=["POST"])
def check_available_drivers():
    data = request.get_json()
    pickup = data.get("pickup_datetime")
    drop = data.get("drop_datetime")
    
    if not pickup or not drop:
        return jsonify({"success": False, "message": "Missing dates ❌"}), 400

    with engine.begin() as conn:
        # Find approved drivers who do NOT have an overlapping Confirmed/Ongoing booking where they are the driver.
        # Note: We track assignments by matching the driver's mobile (which is unique) in the bookings table.
        result = conn.execute(text("""
            SELECT * FROM drivers 
            WHERE status='Approved'
            AND mobile NOT IN (
                SELECT driver_mobile FROM bookings 
                WHERE driver_mobile IS NOT NULL
                AND booking_status IN ('Confirmed', 'Ongoing')
                AND pickup_datetime < :drop
                AND drop_datetime > :pickup
            )
        """), {
            "pickup": pickup,
            "drop": drop
        })
        available = [dict(row) for row in result.mappings().all()]
    return jsonify({"success": True, "drivers": available})

@app.route("/admin/assign-driver", methods=["POST"])
def assign_driver():
    data = request.get_json()
    booking_id = data.get("booking_id")
    driver_id = data.get("driver_id")

    if not booking_id or not driver_id:
        return jsonify({"success": False, "message": "Missing fields ❌"}), 400

    try:
        with engine.begin() as conn:
            driver = conn.execute(text("SELECT full_name, mobile FROM drivers WHERE id=:driver_id AND status='Approved'"), 
                                  {"driver_id": driver_id}).mappings().first()
            if not driver:
                return jsonify({"success": False, "message": "Driver not approved or not found ❌"}), 400

            # Assign to booking
            conn.execute(text("""
                UPDATE bookings 
                SET driver_name=:driver_name,
                    driver_mobile=:driver_mobile,
                    booking_status='Confirmed'
                WHERE id=:booking_id AND booking_status='Pending Platform Driver'
            """), {
                "driver_name": driver["full_name"],
                "driver_mobile": driver["mobile"],
                "booking_id": booking_id
            })

            # Fetch updated booking details for email
            booking_res = conn.execute(text("SELECT * FROM bookings WHERE id=:booking_id"), {"booking_id": booking_id})
            booking = booking_res.mappings().first()
            if booking:
                # Send confirmation email via helper
                # Convert row to dict for send_booking_email
                booking_dict = dict(booking)
                # Ensure datetime objects are converted to strings for the email template if needed, 
                # but send_booking_email just uses get() so it should be fine.
                try:
                    send_booking_email(booking_dict)
                except Exception as e:
                    print("Admin Assignment Email Error:", e)
            
        return jsonify({"success": True, "message": "Driver successfully assigned and confirmation email sent! ✅"})
    except Exception as e:
        print("ASSIGN DRIVER ERROR:", e)
        return jsonify({"success": False, "message": "Database error ❌"}), 500

# -----------------------------
# SIGNUP (USER ONLY)
# -----------------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False, "message": "Invalid request ❌"}), 400

    first = data.get("first_name")
    last = data.get("last_name")
    email = data.get("email")
    password = data.get("password")

    if not all([first, last, email, password]):
        return jsonify({"success": False, "message": "All fields required ❌"}), 400

    email = email.lower().strip()

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    created_at = datetime.now().strftime("%d %b %Y")
    account_id = "CRP-" + str(uuid.uuid4())[:8].upper()

    try:
        with engine.begin() as conn:

            conn.execute(text("""
                INSERT INTO signup
                (first_name, last_name, email, account_id, created_at)
                VALUES (:first, :last, :email, :account_id, :created_at)
            """), {
                "first": first,
                "last": last,
                "email": email,
                "account_id": account_id,
                "created_at": created_at
            })

            conn.execute(text("""
                INSERT INTO login (email, password)
                VALUES (:email, :password)
            """), {
                "email": email,
                "password": hashed_pw
            })

        return jsonify({
            "success": True,
            "message": "Signup successful ✅ Please login"
        })

    except Exception as e:
        print("Signup Error:", e)
        return jsonify({
            "success": False,
            "message": "Email already exists ❌"
        })

# -----------------------------
# 🔥 SINGLE LOGIN (ADMIN + USER)
# -----------------------------
@app.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False, "message": "Invalid request ❌"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email & password required ❌"}), 400

    email = email.lower().strip()

    with engine.begin() as conn:

        # Check admin
        result = conn.execute(
            text("SELECT * FROM admintable WHERE email=:email"),
            {"email": email}
        )
        admin = result.mappings().first()

        if admin:
            if not bcrypt.check_password_hash(admin["password"], password):
                return jsonify({"success": False, "message": "Incorrect password ❌"}), 401

            return jsonify({
                "success": True,
                "message": "Admin login successful ✅",
                "role": "admin",
                "user": {
                    "name": admin["name"],
                    "email": admin["email"]
                }
            })

        # Check user
        result = conn.execute(
            text("SELECT * FROM login WHERE email=:email"),
            {"email": email}
        )
        user = result.mappings().first()

        if not user:
            return jsonify({"success": False, "message": "User not found ❌"}), 404

        if not bcrypt.check_password_hash(user["password"], password):
            return jsonify({"success": False, "message": "Incorrect password ❌"}), 401

        return jsonify({
            "success": True,
            "message": "Login successful ✅",
            "role": "user",
            "user": {"email": email}
        })


# -----------------------------
# FORGOT PASSWORD
# -----------------------------
@app.route("/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    email = data.get("email")

    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM signup WHERE email=:email"),
            {"email": email}
        )
        user = result.fetchone()

    if not user:
        return jsonify({
            "success": False,
            "message": "Email not registered ❌"
        })

    otp = str(random.randint(100000, 999999))
    otp_store[email] = otp

    try:
        otp_body = f"""
        <html><body style="font-family:Arial;background:#f2f3f5;padding:20px;">
        <div style="max-width:500px;background:white;padding:30px;border-radius:12px;box-shadow:0 3px 10px rgba(0,0,0,0.1);">
            <h2 style="color:#7f5cff;">🔐 Password Reset OTP</h2>
            <p>Hello,</p>
            <p>Your OTP for password reset is:</p>
            <h1 style="letter-spacing:10px;color:#333;background:#f5f5f5;padding:20px;text-align:center;border-radius:8px;">{otp}</h1>
            <p style="color:gray;font-size:13px;">This OTP is valid for 10 minutes. If you didn't request this, ignore this email.</p>
        </div>
        </body></html>
        """
        send_email(email, "🔐 Password Reset OTP - CarRentalPro", otp_body)
    except:
        print("Email failed — printing OTP instead:", otp)

    return jsonify({
        "success": True,
        "message": "OTP sent to email ✅"
    })
# -----------------------------
# RESET PASSWORD
# -----------------------------
@app.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json()

    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if otp_store.get(email) != otp:
        return jsonify({
            "success": False,
            "message": "Invalid OTP ❌"
        })

    hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')

    with engine.begin() as conn:

        conn.execute(text("""
            UPDATE login
            SET password=:password
            WHERE email=:email
        """), {
            "password": hashed_pw,
            "email": email
        })

        conn.execute(text("""
            INSERT INTO resetpassword(email, otp, new_password)
            VALUES(:email, :otp, :new_password)
        """), {
            "email": email,
            "otp": otp,
            "new_password": hashed_pw
        })

    otp_store.pop(email, None)

    return jsonify({
        "success": True,
        "message": "Password reset successful ✅ Please login"
    })
# -----------------------------
# 🔥 CREATE ADMIN (SECURED)
# -----------------------------
@app.route("/create-admin", methods=["POST"])
def create_admin():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False}), 400

    if data.get("secret") != ADMIN_SECRET:
        return jsonify({
            "success": False,
            "message": "Unauthorized ❌"
        }), 403

    name = data.get("name")
    email = data.get("email").lower().strip()
    password = data.get("password")

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

    with engine.begin() as conn:

        # Check if already exists
        result = conn.execute(
            text("SELECT id FROM admintable WHERE email=:email"),
            {"email": email}
        )

        if result.fetchone():
            return jsonify({
                "success": False,
                "message": "Admin already exists ❌"
            })

        conn.execute(text("""
            INSERT INTO admintable(name, email, password)
            VALUES(:name, :email, :password)
        """), {
            "name": name,
            "email": email,
            "password": hashed_pw
        })

    return jsonify({
        "success": True,
        "message": "Admin created successfully ✅"
    })


@app.route("/add-car", methods=["POST"])
def add_car():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "message": "Invalid request data ❌"
        }), 400

    owner_email = data.get("owner_email", "").lower().strip()
    listing_type = data.get("listing_type", "").strip().title()

    company = data.get("company")
    model = data.get("model")
    reg_number = data.get("reg_number", "").upper().strip()

    if not owner_email or not listing_type or not company or not model or not reg_number:
        return jsonify({
            "success": False,
            "message": "Missing required fields ❌"
        }), 400

    try:
        with engine.begin() as conn:

            # 🔥 Prevent duplicate registration
            result = conn.execute(
                text("SELECT id FROM cars WHERE reg_number=:reg"),
                {"reg": reg_number}
            )

            if result.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Car already registered ❌"
                }), 400

            # 🔥 Insert car and return ID
            result = conn.execute(text("""
                INSERT INTO cars(
                    owner_email,
                    listing_type,
                    company,
                    model,
                    reg_number,
                    year,
                    fuel,
                    transmission,
                    seats,
                    km,
                    driver_name,
                    driver_mobile,
                    location,
                    price_month,
                    deposit,
                    notes,
                    images
                )
                VALUES(
                    :owner_email,
                    :listing_type,
                    :company,
                    :model,
                    :reg_number,
                    :year,
                    :fuel,
                    :transmission,
                    :seats,
                    :km,
                    :driver_name,
                    :driver_mobile,
                    :location,
                    :price_month,
                    :deposit,
                    :notes,
                    :images
                )
                RETURNING id
            """), {
                "owner_email": owner_email,
                "listing_type": listing_type,
                "company": company,
                "model": model,
                "reg_number": reg_number,
                "year": data.get("year"),
                "fuel": data.get("fuel"),
                "transmission": data.get("transmission"),
                "seats": data.get("seats"),
                "km": data.get("km"),
                "driver_name": data.get("driver_name"),
                "driver_mobile": data.get("driver_mobile"),
                "location": data.get("location"),
                "price_month": data.get("price_month") or 0,
                "deposit": data.get("deposit") or 0,
                "notes": data.get("notes"),
                "images": json.dumps(data.get("images", []))
            })

            inserted_id = result.fetchone()[0]

        return jsonify({
            "success": True,
            "message": "Car submitted for approval ✅",
            "car_id": inserted_id
        })

    except Exception as e:
        print("ADD CAR ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Database error ❌"
        }), 500


@app.route("/approved-cars/<email>/<listing_type>")
def approved_cars(email, listing_type):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT 
                id, owner_email, listing_type, company, model, 
                year, fuel, transmission, seats, km, 
                location, price_month, images
            FROM cars
            WHERE status='Approved'
            AND LOWER(owner_email) != LOWER(:email)
            AND listing_type=:listing_type
        """), {
            "email": email,
            "listing_type": listing_type
        })

        cars = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "cars": cars
    })

@app.route("/admin/pending-cars")
def pending_cars():

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT *
            FROM cars
            WHERE status='Pending'
        """))

        cars = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "cars": cars
    })

@app.route("/admin/update-car-status", methods=["POST"])
def update_status():

    data = request.get_json()

    car_id = data.get("car_id")
    status = data.get("status").capitalize()

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE cars
            SET status=:status
            WHERE id=:car_id
        """), {
            "status": status,
            "car_id": car_id
        })

    return jsonify({"success": True})

@app.route("/my-car-status/<email>")
def my_car_status(email):
    with engine.begin() as conn:
        # Rental Cars
        rent_res = conn.execute(text("""
            SELECT *, 'Rent' as listing_mode 
            FROM cars 
            WHERE owner_email=:email 
            ORDER BY created_at DESC
        """), {"email": email})
        rent_cars = [dict(row) for row in rent_res.mappings().all()]

        # Sale Cars
        sale_res = conn.execute(text("""
            SELECT *, 'Sell' as listing_mode 
            FROM selling 
            WHERE LOWER(owner_email)=LOWER(:email) 
            ORDER BY created_at DESC
        """), {"email": email})
        sale_cars = [dict(row) for row in sale_res.mappings().all()]

    return jsonify({
        "success": True,
        "cars": rent_cars + sale_cars
    })


@app.route("/check-car-availability", methods=["POST"])
def check_car_availability():
    data = request.get_json()
    car_id = data.get("car_id")
    pickup = data.get("pickup_datetime")
    drop = data.get("drop_datetime")

    if not car_id or not pickup or not drop:
        return jsonify({"success": False, "message": "Missing fields ❌"}), 400

    try:
        with engine.connect() as conn:
            # Find any conflicting confirmed/ongoing booking
            conflict = conn.execute(text("""
                SELECT drop_datetime FROM bookings
                WHERE car_id=:car_id
                AND booking_status IN ('Confirmed','Ongoing')
                AND pickup_datetime < :drop
                AND drop_datetime > :pickup
                ORDER BY drop_datetime DESC
                LIMIT 1
            """), {
                "car_id": car_id,
                "pickup": pickup,
                "drop": drop
            }).fetchone()

            if conflict:
                booked_until = conflict[0]
                # Format nicely
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(booked_until))
                    booked_until_str = dt.strftime("%d %b %Y, %I:%M %p")
                except:
                    booked_until_str = str(booked_until)

                return jsonify({
                    "available": False,
                    "message": f"This car is already booked until {booked_until_str}. Please choose different dates.",
                    "booked_until": booked_until_str
                })

            return jsonify({"available": True})

    except Exception as e:
        print("AVAILABILITY CHECK ERROR:", e)
        return jsonify({"available": True})  # Allow on error (backend check still runs)


@app.route("/book-car", methods=["POST"])
def book_car():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Invalid request ❌"
        }), 400

    try:
        with engine.begin() as conn:

            # 🔥 Auto-update booking statuses
            conn.execute(text("""
                UPDATE bookings
                SET booking_status='Ongoing'
                WHERE pickup_datetime <= CURRENT_TIMESTAMP
                AND drop_datetime > CURRENT_TIMESTAMP
                AND booking_status='Confirmed'
            """))

            conn.execute(text("""
                UPDATE bookings
                SET booking_status='Completed'
                WHERE drop_datetime <= CURRENT_TIMESTAMP
                AND booking_status IN ('Confirmed','Ongoing')
            """))

            customer_email = data.get("customer_email")
            if not customer_email:
                return jsonify({
                    "success": False,
                    "message": "Customer email missing ❌"
                }), 400

            customer_email = customer_email.lower().strip()
            car_id = data.get("car_id")
            rental_type = data.get("rental_type")

            if not car_id:
                return jsonify({
                    "success": False,
                    "message": "Missing car ID ❌"
                }), 400

            if rental_type not in ["Rental Only", "With Driver"]:
                return jsonify({
                    "success": False,
                    "message": "Invalid rental type ❌"
                }), 400

            # 🔥 Check car exists
            result = conn.execute(text("""
                SELECT owner_email, status
                FROM cars
                WHERE id=:car_id
            """), {"car_id": car_id})

            car = result.mappings().first()

            if not car:
                return jsonify({
                    "success": False,
                    "message": "Car not found ❌"
                }), 404

            if car["status"] != "Approved":
                return jsonify({
                    "success": False,
                    "message": "Car not available ❌"
                }), 400

            if car["owner_email"].lower() == customer_email:
                return jsonify({
                    "success": False,
                    "message": "You cannot book your own car ❌"
                }), 400

            pickup = data.get("pickup_datetime")
            drop = data.get("drop_datetime")

            if not pickup or not drop:
                return jsonify({
                    "success": False,
                    "message": "Pickup & Drop required ❌"
                }), 400

            # 🔥 Conflict check
            conflict = conn.execute(text("""
                SELECT 1 FROM bookings
                WHERE car_id=:car_id
                AND booking_status IN ('Confirmed','Ongoing')
                AND pickup_datetime < :drop
                AND drop_datetime > :pickup
            """), {
                "car_id": car_id,
                "pickup": pickup,
                "drop": drop
            }).fetchone()

            if conflict:
                return jsonify({
                    "success": False,
                    "message": "Car already booked for selected time ❌"
                }), 400

            # 🔥 Insert booking
            result = conn.execute(text("""
                INSERT INTO bookings(
                    car_id,
                    car_name,
                    owner_email,
                    customer_name,
                    customer_email,
                    customer_mobile,
                    nominee,
                    rental_type,
                    pickup_location,
                    drop_location,
                    pickup_datetime,
                    drop_datetime,
                    driver_name,
                    driver_mobile,
                    passenger_count,
                    total_cost,
                    booking_status
                )
                VALUES(
                    :car_id,
                    :car_name,
                    :owner_email,
                    :customer_name,
                    :customer_email,
                    :customer_mobile,
                    :nominee,
                    :rental_type,
                    :pickup_location,
                    :drop_location,
                    :pickup_datetime,
                    :drop_datetime,
                    :driver_name,
                    :driver_mobile,
                    :passenger_count,
                    :total_cost,
                    :booking_status
                )
                RETURNING id
            """), {
                "car_id": car_id,
                "car_name": data.get("car_name"),
                "owner_email": car["owner_email"],
                "customer_name": data.get("customer_name"),
                "customer_email": customer_email,
                "customer_mobile": data.get("customer_mobile"),
                "nominee": data.get("nominee"),
                "rental_type": rental_type,
                "pickup_location": data.get("pickup_location"),
                "drop_location": data.get("drop_location"),
                "pickup_datetime": pickup,
                "drop_datetime": drop,
                "driver_name": data.get("driver_name"),
                "driver_mobile": data.get("driver_mobile"),
                "passenger_count": int(data.get("passenger_count") or 0),
                "total_cost": int(data.get("total_cost") or 0),
                "booking_status": 'Pending Platform Driver' if (rental_type == 'Rental Only' and data.get("needs_platform_driver")) else ('Confirmed' if rental_type == 'Rental Only' else 'Pending Driver')
            })

            booking_id = result.fetchone()[0]

        # 🔥 Send email after commit (Only if not waiting for Admin to assign a driver)
        try:
            if not (rental_type == 'Rental Only' and data.get("needs_platform_driver")):
                send_booking_email(data)
        except:
            pass

        return jsonify({
            "success": True,
            "message": "Booking confirmed ✅",
            "booking_id": booking_id
        })

    except Exception as e:
        print("BOOKING ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Booking failed ❌"
        }), 500


@app.route("/admin/block-car", methods=["POST"])
def block_car():

    data = request.get_json()
    car_id = data.get("car_id")

    if not car_id:
        return jsonify({
            "success": False,
            "message": "Car ID required ❌"
        }), 400

    try:
        with engine.begin() as conn:

            # 🔥 Check if car has active booking
            result = conn.execute(text("""
                SELECT 1 FROM bookings
                WHERE car_id=:car_id
                AND booking_status='Confirmed'
            """), {
                "car_id": car_id
            })

            if result.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Car has active booking ❌ Cannot block"
                }), 400

            # 🔥 Block car
            conn.execute(text("""
                UPDATE cars
                SET status='Blocked'
                WHERE id=:car_id
            """), {
                "car_id": car_id
            })

        return jsonify({
            "success": True,
            "message": "Car blocked successfully 🚫"
        })

    except Exception as e:
        print("BLOCK ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Database error ❌"
        }), 500

@app.route("/sell-car", methods=["POST"])
def sell_car():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False}), 400

    owner_email = data.get("owner_email", "").lower().strip()
    reg_number = data.get("reg_number", "").upper().strip()

    if not owner_email or not reg_number:
        return jsonify({
            "success": False,
            "message": "Missing required fields ❌"
        }), 400

    try:
        with engine.begin() as conn:

            # 🔥 Prevent duplicate registration
            result = conn.execute(text("""
                SELECT id FROM selling
                WHERE reg_number=:reg
            """), {
                "reg": reg_number
            })

            if result.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Car already listed for sale ❌"
                }), 400

            # 🔥 Insert selling car
            conn.execute(text("""
                INSERT INTO selling(
                    owner_email,
                    company,
                    model,
                    reg_number,
                    year,
                    fuel,
                    transmission,
                    km,
                    owner_type,
                    location,
                    selling_price,
                    description,
                    images
                )
                VALUES(
                    :owner_email,
                    :company,
                    :model,
                    :reg_number,
                    :year,
                    :fuel,
                    :transmission,
                    :km,
                    :owner_type,
                    :location,
                    :selling_price,
                    :description,
                    :images
                )
            """), {
                "owner_email": owner_email,
                "company": data.get("company"),
                "model": data.get("model"),
                "reg_number": reg_number,
                "year": data.get("year"),
                "fuel": data.get("fuel"),
                "transmission": data.get("transmission"),
                "km": data.get("km"),
                "owner_type": data.get("owner_type"),
                "location": data.get("location"),
                "selling_price": data.get("selling_price"),
                "description": data.get("description"),
                "images": json.dumps(data.get("images", []))
            })

        return jsonify({
            "success": True,
            "message": "Car submitted for approval ✅"
        })

    except Exception as e:
        print("SELL CAR ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Database error ❌"
        }), 500


@app.route("/admin/pending-selling")
def pending_selling():

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT *
            FROM selling
            WHERE status='Pending'
        """))

        cars = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "cars": cars
    })

@app.route("/admin/update-selling-status", methods=["POST"])
def update_selling_status():

    data = request.get_json()

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE selling
            SET status=:status
            WHERE id=:car_id
        """), {
            "status": data.get("status"),
            "car_id": data.get("car_id")
        })

    return jsonify({"success": True})

@app.route("/admin/approve-sell/<int:car_id>", methods=["POST"])
def approve_sell(car_id):

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE selling
            SET status='Approved'
            WHERE id=:car_id
        """), {
            "car_id": car_id
        })

    return jsonify({
        "success": True,
        "message": "Car Approved ✅"
    })

@app.route("/admin/reject-sell/<int:car_id>", methods=["POST"])
def reject_sell(car_id):

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE selling
            SET status='Rejected'
            WHERE id=:car_id
        """), {
            "car_id": car_id
        })

    return jsonify({
        "success": True,
        "message": "Car Rejected ❌"
    })


@app.route("/approved-selling/<email>")
def approved_selling(email):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT *
            FROM selling
            WHERE status='Approved'
            AND LOWER(owner_email) != LOWER(:email)
        """), {
            "email": email
        })

        cars = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "cars": cars
    })

@app.route("/my-selling-status/<email>")
def my_selling_status(email):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT *
            FROM selling
            WHERE LOWER(owner_email)=LOWER(:email)
            ORDER BY created_at DESC
        """), {
            "email": email
        })

        cars = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "cars": cars
    })
# ==============================
# GET PROFILE IMAGE
# ==============================
@app.route("/get-profile-image/<email>")
def get_profile_img(email):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT profile_img
            FROM signup
            WHERE email=:email
        """), {
            "email": email.lower().strip()
        })

        row = result.fetchone()

    if row and row[0]:
        return jsonify({
            "success": True,
            "image": row[0]
        })

    return jsonify({
        "success": False
    })
# ==============================
# UPLOAD PROFILE IMAGE
# ==============================

@app.route("/upload-profile-image", methods=["POST"])
def upload_profile_img():

    data = request.json
    email = data.get("email")
    image = data.get("image")

    if not email or not image:
        return jsonify({
            "success": False,
            "message": "Missing data ❌"
        }), 400

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE signup
            SET profile_img=:image
            WHERE email=:email
        """), {
            "image": image,
            "email": email.lower().strip()
        })

    return jsonify({"success": True})

# ==============================
# GET FULL PROFILE
# ==============================
@app.route("/get-profile/<email>", methods=["GET"])
def get_profile(email):

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT
                    first_name,
                    last_name,
                    email,
                    phone,
                    account_id,
                    created_at,
                    profile_img
                FROM signup
                WHERE email=:email
            """), {
                "email": email.lower().strip()
            })

            row = result.mappings().first()

        if not row:
            return jsonify({
                "success": False,
                "message": "User not found ❌"
            })

        return jsonify({
            "success": True,
            "profile": dict(row)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        })

@app.route("/create-buy-request", methods=["POST"])
def create_buy_request():

    data = request.json

    car_id = data.get("car_id")
    buyer_email = data.get("buyer_email")
    buyer_name = data.get("buyer_name")
    buyer_mobile = data.get("buyer_mobile")
    offered_price = data.get("offered_price")

    if not car_id or not buyer_email:
        return jsonify({"success": False, "message": "Missing data ❌"}), 400

    with engine.begin() as conn:

        # Get seller email
        result = conn.execute(text("""
            SELECT owner_email, selling_price
            FROM selling
            WHERE id=:car_id AND status='Approved'
        """), {"car_id": car_id})

        car = result.mappings().first()

        if not car:
            return jsonify({"success": False, "message": "Car not available ❌"}), 404

        conn.execute(text("""
            INSERT INTO buy_requests(
                car_id,
                seller_email,
                buyer_email,
                buyer_name,
                buyer_mobile,
                offered_price
            )
            VALUES(
                :car_id,
                :seller_email,
                :buyer_email,
                :buyer_name,
                :buyer_mobile,
                :offered_price
            )
        """), {
            "car_id": car_id,
            "seller_email": car["owner_email"],
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "buyer_mobile": buyer_mobile,
            "offered_price": offered_price or car["selling_price"]
        })

    return jsonify({
        "success": True,
        "message": "Buy request sent to seller ✅"
    })

@app.route("/my-buy-requests/<email>")
def my_buy_requests(email):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT r.*, s.company, s.model
            FROM buy_requests r
            JOIN selling s ON r.car_id = s.id
            WHERE r.seller_email = :email
            AND r.status != 'Rejected'
            ORDER BY r.created_at DESC
        """), {"email": email})

        requests = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "requests": requests
    })

@app.route("/my-bids/<email>")
def my_bids(email):

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT r.*, s.company, s.model, s.selling_price as asking_price, s.images, s.id as car_id
            FROM buy_requests r
            JOIN selling s ON r.car_id = s.id
            WHERE r.buyer_email = :email
            ORDER BY r.created_at DESC
        """), {"email": email})

        bids = [dict(row) for row in result.mappings().all()]

    return jsonify({
        "success": True,
        "bids": bids
    })

@app.route("/update-buy-request", methods=["POST"])
def update_buy_request():

    data = request.json
    request_id = data.get("request_id")
    status = data.get("status")

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE buy_requests
            SET status=:status
            WHERE id=:request_id
        """), {
            "status": status,
            "request_id": request_id
        })

    return jsonify({"success": True})


@app.route("/finalize-purchase", methods=["POST"])
def finalize_purchase():
    data = request.json
    request_id = data.get("request_id")
    payment_id = data.get("payment_id")
    total_cost = data.get("total_cost")

    if not request_id or not payment_id:
        return jsonify({"success": False, "message": "Missing payment details ❌"}), 400

    try:
        with engine.begin() as conn:
            # 1. Update Buy Request status to Paid
            res = conn.execute(text("""
                UPDATE buy_requests
                SET status = 'Paid'
                WHERE id = :rid
                RETURNING car_id, buyer_email, buyer_name, seller_email, offered_price
            """), {"rid": request_id})
            
            req = res.mappings().first()
            if not req:
                return jsonify({"success": False, "message": "Request not found ❌"}), 404
            
            car_id = req["car_id"]

            # 2. Mark Car as Sold
            conn.execute(text("""
                UPDATE selling
                SET status = 'Sold'
                WHERE id = :cid
            """), {"cid": car_id})

            # Fetch car details for email
            car_res = conn.execute(text("SELECT company, model FROM selling WHERE id = :cid"), {"cid": car_id})
            car = car_res.mappings().first()

            # 3. Reject all other pending bids for this car
            conn.execute(text("""
                UPDATE buy_requests
                SET status = 'Rejected'
                WHERE car_id = :cid AND id != :rid AND status = 'Pending'
            """), {"cid": car_id, "rid": request_id})

            # 4. Send Confirmation Emails
            try:
                # To Buyer
                buyer_msg = f"""
                <h2>Congratulations!</h2>
                <p>You have successfully purchased the <b>{car['company']} {car['model']}</b>.</p>
                <p><b>Amount Paid:</b> ₹{req['offered_price']:,}</p>
                <p><b>Next Steps:</b></p>
                <ul>
                    <li>Contact the seller ({req['seller_email']}) for the RC transfer.</li>
                    <li>Ensure you have the original documents ready.</li>
                    <li>Arrange for car pick-up/delivery as discussed.</li>
                </ul>
                <p>Thank you for choosing CarRentalPro!</p>
                """
                send_email(req['buyer_email'], f"Purchase Confirmed: {car['company']} {car['model']}", buyer_msg)

                # To Seller
                seller_msg = f"""
                <h2>Car Sold!</h2>
                <p>Your <b>{car['company']} {car['model']}</b> has been successfully sold to {req['buyer_name']}.</p>
                <p><b>Sale Amount:</b> ₹{req['offered_price']:,}</p>
                <p>Please coordinate with the buyer at {req['buyer_email']} for title transfer and handover.</p>
                """
                send_email(req['seller_email'], f"Sold: {car['company']} {car['model']}", seller_msg)
            except Exception as e:
                print("Email Notify Error:", e)

        return jsonify({"success": True, "message": "Purchase finalized! ✅"})

    except Exception as e:
        print("Finalize Purchase Error:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# -----------------------------
# 💳 RAZORPAY INTEGRATION
# -----------------------------

@app.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():
    try:
        data = request.json
        # Convert to float first to handle string decimals, then round to int, then paise
        amount_val = float(data.get("amount", 0))
        
        # ⭐ RAZORPAY TEST MODE LIMIT: Maximum allowed is ₹5,00,000
        # For demonstration, we cap the charge if it exceeds the limit, while keeping DB record full.
        max_test_amount = 500000 
        final_amt = amount_val
        if final_amt > max_test_amount:
            print(f"⚠️ CAP APPLIED: Amount ₹{final_amt} exceeds test limit. Charging token ₹{max_test_amount}")
            final_amt = max_test_amount
            
        amount = int(round(final_amt)) * 100 
        currency = "INR"

        order_data = {
            "amount": amount,
            "currency": currency,
            "payment_capture": 1  # Auto-capture payment
        }

        razorpay_order = razorpay_client.order.create(data=order_data)

        return jsonify({
            "success": True,
            "order_id": razorpay_order["id"],
            "amount": amount,
            "currency": currency,
            "key_id": RAZORPAY_KEY_ID
        })
    except Exception as e:
        print("RAZORPAY ORDER ERROR:", e)
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500


@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        data = request.json
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        # Verify the payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)

        # If verification is successful, you can update your database here
        # (e.g., mark booking as paid)

        return jsonify({"success": True, "message": "Payment verified successfully ✅"})
    except Exception as e:
        print("PAYMENT VERIFICATION FAILED:", e)
        return jsonify({"success": False, "message": "Payment verification failed ❌"}), 400


# -----------------------------
# 📅 BOOKING HISTORY ENDPOINT
# -----------------------------

@app.route("/my-bookings/<email>")
def my_bookings(email):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT *
                FROM bookings
                WHERE LOWER(customer_email) = LOWER(:email)
                ORDER BY pickup_datetime DESC
            """), {"email": email})
            
            bookings = [dict(row) for row in result.mappings().all()]

        return jsonify({
            "success": True,
            "count": len(bookings),
            "bookings": bookings
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# -----------------------------
# 📍 TRIP TRACKING ENDPOINTS
# -----------------------------

@app.route("/get-booking-details/<int:booking_id>", methods=["GET"])
def get_booking_details(booking_id):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM bookings WHERE id = :id"), {"id": booking_id})
            row = result.mappings().first()
            
            if not row:
                return jsonify({"success": False, "message": "Booking not found ❌"}), 404
                
            return jsonify({"success": True, "booking": dict(row)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/update-trip-location", methods=["POST"])
def update_trip_location():
    try:
        data = request.json
        booking_id = data.get("booking_id")
        lat = data.get("latitude")
        lng = data.get("longitude")

        if not booking_id or lat is None or lng is None:
            return jsonify({"success": False, "message": "Missing tracking data ❌"}), 400

        with engine.begin() as conn:
            # Update or Insert location
            conn.execute(text("""
                INSERT INTO trip_locations (booking_id, latitude, longitude, last_updated)
                VALUES (:booking_id, :lat, :lng, CURRENT_TIMESTAMP)
                ON CONFLICT (booking_id) 
                DO UPDATE SET 
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    last_updated = CURRENT_TIMESTAMP
            """), {"booking_id": booking_id, "lat": lat, "lng": lng})

        return jsonify({"success": True})
    except Exception as e:
        print("TRACKING UPDATE ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/get-trip-location/<int:booking_id>", methods=["GET"])
def get_trip_location(booking_id):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT t.*, b.driver_name, b.car_name, b.customer_name
                FROM trip_locations t
                JOIN bookings b ON t.booking_id = b.id
                WHERE t.booking_id = :booking_id
            """), {"booking_id": booking_id})
            
            row = result.mappings().first()

        if not row:
            return jsonify({"success": False, "message": "No live location available ❌"}), 404

        return jsonify({
            "success": True, 
            "location": dict(row)
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/admin/live-trips", methods=["GET"])
def get_live_trips():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT t.*, b.driver_name, b.car_name, b.customer_name, b.booking_status
                FROM trip_locations t
                JOIN bookings b ON t.booking_id = b.id
                WHERE b.booking_status = 'Ongoing'
                ORDER BY t.last_updated DESC
            """))
            
            trips = [dict(row) for row in result.mappings().all()]

        return jsonify({
            "success": True,
            "trips": trips
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-booking-status", methods=["POST"])
def update_booking_status():
    try:
        data = request.json
        booking_id = data.get("booking_id")
        status = data.get("status") # e.g., 'Ongoing', 'Completed'

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE bookings 
                SET booking_status = :status 
                WHERE id = :booking_id
            """), {"status": status, "booking_id": booking_id})

        return jsonify({"success": True, "message": f"Status updated to {status} ✅"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# -----------------------------
@app.route("/get-bookings-for-owner-cars/<email>", methods=["GET"])
def get_bookings_for_owner_cars(email):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT b.* 
                FROM bookings b
                JOIN cars c ON b.car_id = c.id
                WHERE LOWER(c.owner_email) = LOWER(:email)
                AND b.booking_status IN ('Confirmed', 'Ongoing', 'Pending Driver')
                ORDER BY b.pickup_datetime ASC
            """), {"email": email})
            
            bookings = [dict(row) for row in result.mappings().all()]

        return jsonify({"success": True, "bookings": bookings})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# 📦 PARCEL DELIVERY ENDPOINTS
# -----------------------------

@app.route("/search-cars-for-parcel", methods=["POST"])
def search_cars_for_parcel():
    try:
        data = request.json
        pickup = data.get("pickup_location")
        drop = data.get("drop_location")

        if not pickup or not drop:
            return jsonify({"success": False, "message": "Pickup and Drop locations required ❌"}), 400

        with engine.begin() as conn:
            # Find active bookings "With Driver" that match the route
            # For now, we match exact pickup and drop locations.
            # In a real-world scenario, we would check if these are on the path.
            result = conn.execute(text("""
                SELECT b.id, b.car_name, b.driver_name, b.driver_mobile, b.pickup_location, b.drop_location, b.pickup_datetime
                FROM bookings b
                WHERE b.rental_type = 'With Driver'
                AND b.booking_status = 'Confirmed'
                AND LOWER(b.pickup_location) LIKE LOWER(:pickup)
                AND LOWER(b.drop_location) LIKE LOWER(:drop)
            """), {"pickup": f"%{pickup}%", "drop": f"%{drop}%"})
            
            cars = [dict(row) for row in result.mappings().all()]

        return jsonify({"success": True, "cars": cars})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/create-parcel-request", methods=["POST"])
def create_parcel_request():
    try:
        data = request.json
        sender_email = data.get("sender_email")
        pickup = data.get("pickup_location")
        drop = data.get("drop_location")
        description = data.get("parcel_description")
        weight = data.get("parcel_weight")
        receiver_name = data.get("receiver_name")
        receiver_mobile = data.get("receiver_mobile")
        booking_id = data.get("booking_id")

        if not all([sender_email, pickup, drop, receiver_name, receiver_mobile, booking_id]):
            return jsonify({"success": False, "message": "Missing required parcel data ❌"}), 400

        # Generate 12-digit code for scanning simulation
        pickup_qr = ''.join([str(random.randint(0, 9)) for _ in range(12)])
        # Generate 4-digit OTP for delivery
        delivery_otp = ''.join([str(random.randint(0, 9)) for _ in range(4)])

        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO parcels (
                    sender_email, pickup_location, drop_location, parcel_description, 
                    parcel_weight, receiver_name, receiver_mobile, booking_id, 
                    pickup_qr_code, delivery_otp
                )
                VALUES (
                    :sender_email, :pickup, :drop, :description, 
                    :weight, :receiver_name, :receiver_mobile, :booking_id, 
                    :pickup_qr, :delivery_otp
                )
                RETURNING id
            """), {
                "sender_email": sender_email, "pickup": pickup, "drop": drop, 
                "description": description, "weight": weight, 
                "receiver_name": receiver_name, "receiver_mobile": receiver_mobile, 
                "booking_id": booking_id, "pickup_qr": pickup_qr, "delivery_otp": delivery_otp
            })
            parcel_id = result.fetchone()[0]

        return jsonify({
            "success": True, 
            "message": "Parcel request created ✅ Driver notified",
            "parcel_id": parcel_id
        })
    except Exception as e:
        print("PARCEL ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/get-parcel-requests-for-driver/<mobile>", methods=["GET"])
def get_parcel_requests_for_driver(mobile):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT p.*, b.car_name 
                FROM parcels p
                JOIN bookings b ON p.booking_id = b.id
                WHERE b.driver_mobile = :mobile
                AND p.status IN ('Pending', 'Accepted', 'Picked Up')
            """), {"mobile": mobile})
            
            parcels = [dict(row) for row in result.mappings().all()]

        return jsonify({"success": True, "parcels": parcels})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/update-parcel-status", methods=["POST"])
def update_parcel_status():
    try:
        data = request.json
        parcel_id = data.get("parcel_id")
        status = data.get("status") # Accepted, Rejected, Picked Up

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE parcels 
                SET status = :status 
                WHERE id = :parcel_id
            """), {"status": status, "parcel_id": parcel_id})

            # If accepted, trigger real notifications
            if status == 'Accepted':
                # Fetch parcel and receiver details
                result = conn.execute(text("""
                    SELECT p.*, b.driver_name, b.driver_mobile 
                    FROM parcels p 
                    JOIN bookings b ON p.booking_id = b.id 
                    WHERE p.id = :id
                """), {"id": parcel_id})
                parcel = result.mappings().first()
                
                if parcel:
                    # 1. Send Email to Sender (with 12-digit code & QR)
                    send_parcel_accepted_email(parcel['sender_email'], dict(parcel))
                    
                    # 2. Simulate SMS to Receiver (with OTP)
                    send_parcel_receiver_otp(
                        parcel['receiver_mobile'], 
                        parcel['delivery_otp'], 
                        parcel['receiver_name']
                    )

        return jsonify({"success": True, "message": f"Parcel {status} successfully ✅"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/get-parcel-details/<int:parcel_id>", methods=["GET"])
def get_parcel_details(parcel_id):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM parcels WHERE id = :id"), {"id": parcel_id})
            row = result.mappings().first()

        if not row:
            return jsonify({"success": False, "message": "Parcel not found ❌"}), 404

        return jsonify({"success": True, "parcel": dict(row)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/deliver-parcel", methods=["POST"])
def deliver_parcel():
    try:
        data = request.json
        parcel_id = data.get("parcel_id")
        otp = data.get("otp")

        with engine.begin() as conn:
            result = conn.execute(text("SELECT delivery_otp FROM parcels WHERE id = :id"), {"id": parcel_id})
            row = result.mappings().first()

            if not row or row["delivery_otp"] != otp:
                return jsonify({"success": False, "message": "Invalid OTP ❌"}), 400

            conn.execute(text("""
                UPDATE parcels 
                SET status = 'Delivered' 
                WHERE id = :parcel_id
            """), {"parcel_id": parcel_id})

            # Fetch parcel details for notification
            result = conn.execute(text("SELECT * FROM parcels WHERE id = :id"), {"id": parcel_id})
            parcel = result.mappings().first()
            if parcel:
                send_parcel_delivered_email(parcel["sender_email"], dict(parcel))

        return jsonify({"success": True, "message": "Parcel marked as Delivered ✅"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/get-parcel-tracking-user/<email>", methods=["GET"])
def get_parcel_tracking_user(email):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT p.*, b.booking_status, b.id as booking_id
                FROM parcels p
                JOIN bookings b ON p.booking_id = b.id
                WHERE LOWER(p.sender_email) = LOWER(:email)
                ORDER BY p.created_at DESC
            """), {"email": email})
            
            parcels = [dict(row) for row in result.mappings().all()]

        return jsonify({"success": True, "parcels": parcels})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# -----------------------------
# RUN SERVER
# -----------------------------

# --- ROADMIND AI INTEGRATION ---
def get_live_car_listings(filters: dict) -> str:
    """
    Search approved car listings from the live database.
    filters: { fuel, listing_type, max_price, location }
    Returns formatted string of matching cars.
    NOTE: Requires `engine` to be already defined in your app.py.
    """
    try:
        conditions = ["status='Approved'"]
        params     = {}

        if filters.get("fuel"):
            conditions.append("LOWER(fuel)=LOWER(:fuel)")
            params["fuel"] = filters["fuel"]

        if filters.get("listing_type"):
            conditions.append("LOWER(listing_type)=LOWER(:listing_type)")
            params["listing_type"] = filters["listing_type"]

        if filters.get("max_price"):
            conditions.append("price_month <= :max_price")
            params["max_price"] = filters["max_price"]

        if filters.get("location"):
            conditions.append("LOWER(location) LIKE LOWER(:location)")
            params["location"] = f"%{filters['location']}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with engine.begin() as conn:
            result = conn.execute(
                text(f"""
                    SELECT company, model, year, fuel, transmission,
                           seats, location, price_month, listing_type
                    FROM cars
                    WHERE {where_clause}
                    ORDER BY price_month ASC
                    LIMIT 5
                """),
                params
            )
            cars = [dict(row) for row in result.mappings().all()]

        if not cars:
            return "No cars found matching those filters right now."

        lines = ["Here are the available cars:\n"]
        for i, car in enumerate(cars, 1):
            if car['listing_type'] == 'With Driver':
                price_str = "₹15/km"
            else:
                daily_price = (car['price_month'] // 30) if car['price_month'] else 0
                price_str = f"₹{daily_price:,}/day"
            lines.append(
                f"{i}. {car['company']} {car['model']} ({car['year']}) — "
                f"{car['fuel']}, {car['transmission']}, {car['seats']} seats | "
                f"{price_str} | {car['listing_type']} | "
                f"📍 {car['location']}"
            )
        return "\n".join(lines)

    except Exception as e:
        print("Live car search error:", e)
        return ""


def get_user_booking_info(email: str) -> str:
    """Get booking details for a logged-in user.
    NOTE: Requires `engine` to be already defined in your app.py."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    SELECT car_name, pickup_location, drop_location,
                           pickup_datetime, drop_datetime,
                           booking_status, total_cost, rental_type
                    FROM bookings
                    WHERE LOWER(customer_email) = LOWER(:email)
                    ORDER BY pickup_datetime DESC
                    LIMIT 3
                """),
                {"email": email}
            )
            bookings = [dict(row) for row in result.mappings().all()]

        if not bookings:
            return "You don't have any bookings yet."

        lines = ["Your recent bookings:\n"]
        for b in bookings:
            lines.append(
                f"• {b['car_name']} | {b['booking_status']} | "
                f"{b['rental_type']} | ₹{b['total_cost']:,} | "
                f"Pickup: {b['pickup_datetime']} → Drop: {b['drop_datetime']}"
            )
        return "\n".join(lines)

    except Exception as e:
        print("User booking info error:", e)
        return ""


def get_user_listing_status(email: str) -> str:
    """Get car listing status for a logged-in owner.
    NOTE: Requires `engine` to be already defined in your app.py."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    SELECT company, model, year, listing_type,
                           status, price_month, created_at
                    FROM cars
                    WHERE LOWER(owner_email) = LOWER(:email)
                    ORDER BY created_at DESC
                    LIMIT 5
                """),
                {"email": email}
            )
            listings = [dict(row) for row in result.mappings().all()]

        if not listings:
            return "You haven't listed any cars yet."

        lines = ["Your car listings:\n"]
        for l in listings:
            if l['listing_type'] == 'With Driver':
                price_str = "₹15/km"
            else:
                daily_price = (l['price_month'] // 30) if l['price_month'] else 0
                price_str = f"₹{daily_price:,}/day"
            lines.append(
                f"• {l['company']} {l['model']} ({l['year']}) — "
                f"{l['listing_type']} | Status: {l['status']} | "
                f"{price_str}"
            )
        return "\n".join(lines)

    except Exception as e:
        print("User listing status error:", e)
        return ""


def get_sell_listing_status(email: str) -> str:
    """Get sell listing status for a user.
    NOTE: Requires `engine` to be already defined in your app.py."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    SELECT company, model, year, selling_price,
                           status, created_at
                    FROM selling
                    WHERE LOWER(owner_email) = LOWER(:email)
                    ORDER BY created_at DESC
                    LIMIT 5
                """),
                {"email": email}
            )
            listings = [dict(row) for row in result.mappings().all()]

        if not listings:
            return "You haven't listed any cars for sale yet."

        lines = ["Your sell listings:\n"]
        for l in listings:
            lines.append(
                f"• {l['company']} {l['model']} ({l['year']}) — "
                f"₹{l['selling_price']:,} | Status: {l['status']}"
            )
        return "\n".join(lines)

    except Exception as e:
        print("Sell listing status error:", e)
        return ""


def classify_question(question: str, role: str) -> str:
    """
    Use Gemini to classify the user's question into one of:
    car_search | my_bookings | my_listings | my_sell_listings |
    platform_policy | car_problem | general | unrelated
    """
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
Classify this question into EXACTLY one of these categories.
Reply with ONLY the category name, nothing else.

Categories:
- car_search: user wants to find/browse available cars to rent or buy
- my_bookings: user asking about their own bookings, booking status, booking dates
- my_listings: user asking about their own rental car listings and approval status
- my_sell_listings: user asking about their own sell listings and approval status
- platform_policy: question about cancellation, refund, insurance, delivery,
                   how the platform works, pricing
- car_problem: question about a car issue, noise, warning light, breakdown,
               maintenance, repair — anything mechanical or technical
- admin_question: admin asking about approval, rejection, car condition decisions
- general: greeting, thanks, casual chat
- unrelated: completely unrelated to cars or this platform

Role: {role}
Question: {question}
"""
        response = model.generate_content(prompt)
        category = response.text.strip().lower()

        valid = ["car_search", "my_bookings", "my_listings", "my_sell_listings",
                 "platform_policy", "car_problem", "admin_question",
                 "general", "unrelated"]

        return category if category in valid else "general"

    except:
        return "general"


def extract_car_filters(question: str) -> dict:
    """
    Use Gemini to extract search filters from a natural language question.
    Returns dict with keys: fuel, listing_type, max_price, location
    """
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
Extract car search filters from this question.
Reply ONLY with a JSON object. Use null for fields not mentioned.

Fields to extract:
- fuel: "Petrol" | "Diesel" | "Electric" | "CNG" | null
- listing_type: "Rental Only" | "With Driver" | null
- max_price: number (per day in INR) | null
- location: city name string | null

Question: {question}

Reply with JSON only, example: {{"fuel": "Diesel", "listing_type": null, "max_price": 2000, "location": "Hyderabad"}}
"""
        response = model.generate_content(prompt)
        import json, re
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_str:
            return json.loads(json_str.group())
        return {}

    except:
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# SECTION C: FLASK ROUTES
# Paste these routes in app.py BEFORE your `app.run()` at the bottom.
# ──────────────────────────────────────────────────────────────────────────────

from flask import Flask   # just for reference — this is already your app object


# ── You must also create the ai_chats table in Supabase/PostgreSQL once:
# ──   CREATE TABLE IF NOT EXISTS ai_chats (
# ──       id           SERIAL PRIMARY KEY,
# ──       email        TEXT,
# ──       role         TEXT,
# ──       session_id   TEXT NOT NULL,
# ──       sender       TEXT NOT NULL,  -- 'user' or 'ai'
# ──       message      TEXT NOT NULL,
# ──       created_at   TIMESTAMPTZ DEFAULT NOW()
# ──   );


# NOTE: Replace `app` below with your actual Flask app variable name if different.


def register_roadmind_routes(app, engine):
    """
    Call this function in your app.py AFTER defining app and engine:
        register_roadmind_routes(app, engine)
    """

    @app.route("/ai-chat", methods=["POST"])
    def ai_chat():

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False}), 400

        user_message = data.get("message", "").strip()
        user_role    = data.get("role", "guest")
        user_name    = data.get("userName", "there")
        email        = data.get("email", None)
        session_id   = data.get("sessionId") or str(uuid_lib.uuid4())
        history      = data.get("history", [])   # [{role, content}, ...]

        if not user_message:
            return jsonify({"success": False, "message": "Empty"}), 400

        # ── LAYER 1: Live database context ────────────────────────────
        db_context    = ""
        question_type = classify_question(user_message, user_role)

        if question_type == "car_search":
            filters    = extract_car_filters(user_message)
            db_context = get_live_car_listings(filters)

        elif question_type == "my_bookings" and email:
            db_context = get_user_booking_info(email)

        elif question_type == "my_listings" and email:
            db_context = get_user_listing_status(email)

        elif question_type == "my_sell_listings" and email:
            db_context = get_sell_listing_status(email)

        # ── LAYER 2: Knowledge base RAG ──────────────────────────────
        kb_context = ""
        if question_type in ["platform_policy", "admin_question"] or not db_context:
            kb_context = search_knowledge(user_message, top_k=4)

        # ── Combine context ──────────────────────────────────────────
        context_parts = []
        if db_context:
            context_parts.append(f"LIVE PLATFORM DATA:\n{db_context}")
        if kb_context:
            context_parts.append(f"PLATFORM KNOWLEDGE:\n{kb_context}")
        combined_context = "\n\n".join(context_parts)

        # ── LAYER 3: System prompt + Gemini ─────────────────────────
        system_prompt = f"""
You are RoadMind — a friendly car expert and assistant built into CarRentalPro,
an Indian car rental and buy/sell platform based in Hyderabad.
You are talking to {user_name}, who is a {user_role}.

YOUR PERSONALITY — THIS IS CRITICAL:
- Talk exactly like a knowledgeable friend texting someone
- Warm, casual, direct. Never stiff or formal.
- Use {user_name}'s name occasionally when it feels natural
- Short punchy replies for simple things. Detailed when genuinely needed.
- Totally fine to say: "honestly", "so basically", "yeah", "good call"
- NEVER say: "As an AI", "I understand your query", "Certainly!", "Of course!"
- NEVER start with "Great question!" or "That's a wonderful question!"
- If someone is stressed or in emergency — calm and direct first, details after
- Use emojis very occasionally — feels natural when used, not forced
- Remember EVERYTHING said earlier in this conversation

YOUR EXPERTISE:
- All car problems: strange noises, warning lights, breakdowns, overheating,
  flat tyres, dead battery, engine issues — anything mechanical
- Indian cars specifically: Maruti, Hyundai, Tata, Honda, Toyota, Mahindra,
  Kia, MG, Skoda, Volkswagen, Renault — you know their common issues well
- Maintenance: service intervals, what to check, rough INR cost estimates
- Road emergencies: exact steps, safety first, what's urgent vs can wait
- CarRentalPro platform: everything about how it works (use provided context)
- Admin decisions: what to approve, reject, flag — use admin guide context
- With Driver Pricing: NEVER quote a per-day price. The fare is roughly ₹15/km. If the user asks for the price, ask them for their exact pickup and drop locations to give an estimate, and remind them the exact price is generated on the booking map.

ROLE-SPECIFIC BEHAVIOUR:
- user (renter/buyer): focus on finding cars, booking help, car problems
- owner: focus on listing advice, approval status, how to get approved
- admin: focus on approval decisions, red flags, platform management
- guest: helpful but remind them to log in for personalised answers

BOUNDARIES:
- If asked something completely unrelated to cars or this platform:
  "Ha honestly that's outside my zone — I'm pretty much only good with
   cars and this platform 😅 Anything car-related?"
- For medical emergencies in accidents: "Call 112 immediately first"
- Never give advice that could endanger someone
"""

        # ── Build Gemini conversation ─────────────────────────────────
        try:
            model = genai.GenerativeModel(
                model_name="gemini-flash-latest",
                system_instruction=system_prompt
            )

            # Build message history for Gemini (exclude the latest message)
            gemini_history = []
            for msg in history[:-1]:
                gemini_history.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [msg["content"]]
                })

            chat = model.start_chat(history=gemini_history)

            # Inject context into the user message if we have it
            if combined_context:
                augmented_message = (
                    f"{combined_context}\n\n"
                    f"---\n"
                    f"User's question: {user_message}"
                )
            else:
                augmented_message = user_message

            response = chat.send_message(augmented_message)
            ai_reply = response.text

            # ── Save to database ──────────────────────────────────────
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ai_chats
                            (email, role, session_id, sender, message)
                        VALUES (:email, :role, :session_id, 'user', :message)
                    """), {
                        "email": email, "role": user_role,
                        "session_id": session_id, "message": user_message
                    })
                    conn.execute(text("""
                        INSERT INTO ai_chats
                            (email, role, session_id, sender, message)
                        VALUES (:email, :role, :session_id, 'ai', :message)
                    """), {
                        "email": email, "role": user_role,
                        "session_id": session_id, "message": ai_reply
                    })
            except Exception as db_err:
                print("AI chat DB save error:", db_err)
                # Non-blocking — still return the response

            return jsonify({
                "success": True,
                "reply": ai_reply,
                "sessionId": session_id
            })

        except Exception as e:
            print("RoadMind Gemini error:", e)
            return jsonify({
                "success": True,
                "reply": "Hmm something went wrong on my end — try again in a sec 🔄"
            })


    @app.route("/ai-history/<email>")
    def ai_history(email):
        """Return past chat sessions grouped for history panel"""
        try:
            with engine.begin() as conn:
                result = conn.execute(text("""
                    SELECT
                        session_id,
                        MIN(created_at)                                    AS started_at,
                        MIN(CASE WHEN sender='user' THEN message END)      AS preview,
                        COUNT(*)                                           AS message_count
                    FROM ai_chats
                    WHERE LOWER(email) = LOWER(:email)
                    GROUP BY session_id
                    ORDER BY started_at DESC
                    LIMIT 20
                """), {"email": email})
                sessions = [dict(row) for row in result.mappings().all()]

            return jsonify({"success": True, "sessions": sessions})

        except Exception as e:
            print("AI history error:", e)
            return jsonify({"success": False, "sessions": []})


# ──────────────────────────────────────────────────────────────────────────────
# HOW TO CALL THIS IN YOUR APP.PY:
#
#   # After defining `app` and `engine`:
#   from roadmind_backend_patch import register_roadmind_routes
#   register_roadmind_routes(app, engine)
#
# OR you can just directly copy-paste the two route functions above (@app.route...)
# into your app.py without using register_roadmind_routes().
# ──────────────────────────────────────────────────────────────────────────────

register_roadmind_routes(app, engine)

# ============================================
# 🔮 ML PRICE PREDICTION & SUGGESTIONS
# ============================================

@app.route("/predict", methods=["POST"])
def predict_car_price():
    # Lazy load the model on first call
    current_model, current_encoders = load_ml_model_lazy()
    
    if not current_model or not current_encoders:
        return jsonify({"success": False, "error": "ML Model not available"}), 503

    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        # Encode safely
        def encode_safe(column, value):
            le = current_encoders[column]
            if value in le.classes_:
                return le.transform([value])[0]
            else:
                return 0

        features = np.array([[
            encode_safe("company", data["company"]),
            encode_safe("model", data["model"]),
            int(data["year"]),
            int(data["km"]),
            encode_safe("fuel", data["fuel"]),
            encode_safe("transmission", data["transmission"]),
            encode_safe("ownerType", data["ownerType"])
        ]])

        price = current_model.predict(features)[0]
        return jsonify({"success": True, "price": int(price)})

    except Exception as e:
        print("Prediction Error:", e)
        return jsonify({"success": False, "error": str(e)})


@app.route("/companies", methods=["GET"])
def get_ml_companies():
    return jsonify(car_metadata.get("companies", []))

@app.route("/models/<company>", methods=["GET"])
def get_ml_models(company):
    return jsonify(car_metadata.get("models", {}).get(company, []))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
