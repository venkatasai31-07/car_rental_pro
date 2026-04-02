"""
══════════════════════════════════════════════════════════════════════════
  ROADMIND AI ASSISTANT — BACKEND PATCH FILE
  File: 1_roadmind_backend_patch.py

  INSTRUCTIONS FOR YOUR FRIEND:
  ──────────────────────────────
  1. Open your project's main backend file (app.py or wherever your Flask app is).

  2. STEP A — Add these imports at the TOP of app.py (right after your existing imports):

        import google.generativeai as genai
        import uuid as uuid_lib
        import sys, os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ai_assistant.rag.retriever import search_knowledge

        GEMINI_API_KEY = "AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM"
        genai.configure(api_key=GEMINI_API_KEY)

  3. STEP B — Copy the HELPER FUNCTIONS section below and paste it anywhere
     before your Flask routes (e.g., right after your DB/engine setup).

  4. STEP C — Copy the FLASK ROUTES section below and paste it anywhere
     before your app.run() line.

  5. STEP D — Make sure the `ai_assistant/` folder (with rag/ and knowledge/) is
     placed in the ROOT of your project (same level as backend/).

  6. STEP E — Run the RAG index builder ONCE before starting your server:
        python ai_assistant/rag/build_index.py

  7. STEP F — Run your backend as usual:
        python backend/app.py

  8. STEP G — Add these 2 lines to EVERY HTML page's <head> tag:
        <link rel="stylesheet" href="../ai_assistant/roadmind.css">
        <script src="../ai_assistant/roadmind.js" defer></script>

  REQUIREMENTS — Install these if not already installed:
        pip install google-generativeai chromadb flask flask-cors
══════════════════════════════════════════════════════════════════════════
"""

# ──────────────────────────────────────────────────────────────────────────────
# SECTION A: IMPORTS (Add to TOP of your app.py)
# ──────────────────────────────────────────────────────────────────────────────

# === PASTE THIS IN YOUR APP.PY IMPORTS SECTION ===
#
#   import google.generativeai as genai
#   import uuid as uuid_lib
#   import sys, os
#   sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#   from ai_assistant.rag.retriever import search_knowledge
#
#   GEMINI_API_KEY = "AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM"
#   genai.configure(api_key=GEMINI_API_KEY)
#
# ======================================================


# ──────────────────────────────────────────────────────────────────────────────
# SECTION B: HELPER FUNCTIONS — LAYER 1 (Live Database)
# Paste these functions in app.py BEFORE your routes, after your engine/DB setup.
# These functions use `engine` which must already be defined in your app.py.
# ──────────────────────────────────────────────────────────────────────────────

from flask import request, jsonify  # already in your app.py - just for reference
from sqlalchemy import text          # already in your app.py - just for reference


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
            lines.append(
                f"{i}. {car['company']} {car['model']} ({car['year']}) — "
                f"{car['fuel']}, {car['transmission']}, {car['seats']} seats | "
                f"₹{car['price_month']:,}/day | {car['listing_type']} | "
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
            lines.append(
                f"• {l['company']} {l['model']} ({l['year']}) — "
                f"{l['listing_type']} | Status: {l['status']} | "
                f"₹{l['price_month']:,}/day"
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
