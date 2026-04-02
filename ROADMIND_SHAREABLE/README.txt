══════════════════════════════════════════════════════════════════════════
 ROADMIND AI ASSISTANT — SHAREABLE PACKAGE
 Created for: CarRentalPro (CarSync / Roadsync project)
══════════════════════════════════════════════════════════════════════════

WHAT IS THIS?
─────────────
This folder contains everything needed to add the RoadMind AI chat assistant
to any CarRentalPro-based project. The AI uses a 3-layer intelligence system:

  Layer 1 → Live Supabase database (real cars, bookings, listings)
  Layer 2 → Platform knowledge base (your .txt policy files via ChromaDB RAG)
  Layer 3 → Gemini's built-in car expertise (breakdowns, maintenance, advice)


FOLDER STRUCTURE OF THIS PACKAGE:
────────────────────────────────
  ROADMIND_SHAREABLE/
  ├── README.txt                          ← You are reading this
  ├── 1_roadmind_backend_patch.py        ← Backend code (copy into app.py)
  └── ai_assistant/
      ├── roadmind.js                    ← Frontend chat widget (copy to project)
      ├── roadmind.css                   ← Widget styling (copy to project)
      ├── knowledge/                     ← Add your .txt policy files here
      │   └── (place your .txt files here)
      └── rag/
          ├── retriever.py               ← RAG search module (copy to project)
          └── build_index.py             ← Run once to build vector index


STEP-BY-STEP SETUP:
──────────────────

  STEP 1 — Copy files into your project
  ────────────────────────────────────────
  Copy the ai_assistant/ folder into the ROOT of your project:

      your_project/
      ├── backend/
      │   └── app.py             ← your Flask backend
      ├── ai_assistant/          ← paste this whole folder here
      │   ├── roadmind.js
      │   ├── roadmind.css
      │   ├── knowledge/
      │   └── rag/
      │       ├── retriever.py
      │       └── build_index.py
      ├── login/
      ├── dashboard/
      └── (other HTML pages)


  STEP 2 — Install Python dependencies
  ──────────────────────────────────────
      pip install google-generativeai chromadb flask flask-cors flask-bcrypt sqlalchemy


  STEP 3 — Edit your backend (app.py)
  ─────────────────────────────────────
  Open 1_roadmind_backend_patch.py and follow the instructions inside.
  In short:

  A) Add these lines at the TOP of your app.py (after existing imports):

      import google.generativeai as genai
      import uuid as uuid_lib
      import sys, os
      sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
      from ai_assistant.rag.retriever import search_knowledge

      GEMINI_API_KEY = "AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM"
      genai.configure(api_key=GEMINI_API_KEY)

  B) Copy all the HELPER FUNCTIONS from 1_roadmind_backend_patch.py
     and paste them in app.py BEFORE your routes (after engine/DB setup).

  C) Copy the two FLASK ROUTES (@app.route("/ai-chat") and @app.route("/ai-history/..."))
     from 1_roadmind_backend_patch.py and paste them in app.py BEFORE app.run().


  STEP 4 — Create the ai_chats table in your Supabase database
  ─────────────────────────────────────────────────────────────
  Run this SQL in Supabase SQL Editor:

      CREATE TABLE IF NOT EXISTS ai_chats (
          id          SERIAL PRIMARY KEY,
          email       TEXT,
          role        TEXT,
          session_id  TEXT NOT NULL,
          sender      TEXT NOT NULL,
          message     TEXT NOT NULL,
          created_at  TIMESTAMPTZ DEFAULT NOW()
      );


  STEP 5 — Add your knowledge .txt files
  ────────────────────────────────────────
  Place your platform policy .txt files inside ai_assistant/knowledge/.
  For example:
      - cancellation_policy.txt
      - booking_guide.txt
      - owner_guide.txt
      - admin_guide.txt

  Each file should contain plain English text about your platform's policies.


  STEP 6 — Build the RAG index (run ONCE, re-run if you change .txt files)
  ──────────────────────────────────────────────────────────────────────────
  From the ROOT of your project, run:

      python ai_assistant/rag/build_index.py


  STEP 7 — Add the chat widget to your HTML pages
  ─────────────────────────────────────────────────
  Add these 2 lines to the <head> tag of EVERY HTML page:

      <link rel="stylesheet" href="../ai_assistant/roadmind.css">
      <script src="../ai_assistant/roadmind.js" defer></script>

  Note: Adjust the path (../ai_assistant/) based on where your HTML file is.
  For example:
      - If HTML is in root:      href="ai_assistant/roadmind.css"
      - If HTML is 1 level deep: href="../ai_assistant/roadmind.css"
      - If HTML is 2 levels deep: href="../../ai_assistant/roadmind.css"


  STEP 8 — Start the backend server
  ─────────────────────────────────
      python backend/app.py

  
  STEP 9 — Serve your frontend (for local testing only)
  ──────────────────────────────────────────────────────
      python -m http.server 8001

  Then visit: http://localhost:8001


TESTING THE AI:
──────────────
  A purple floating button will appear at the bottom-right of every page.
  Click it to open the chat. Test each layer:

  Layer 1 (Database):  "Show me cars under 3000 per day"
  Layer 2 (Knowledge): "What is your cancellation policy?"
  Layer 3 (Gemini):    "My car's engine is making a grinding sound, what's wrong?"


TROUBLESHOOTING:
───────────────
  Error: "Hmm something went wrong"
    → Make sure backend is running on port 3000
    → Check that GEMINI_API_KEY is valid and has quota remaining
    → Ensure the ai_chats table exists in your database

  Widget not visible on page:
    → Check browser console for JS errors (F12)
    → Verify the <script> and <link> paths are correct in your HTML
    → Make sure the backend server is running

  RAG not finding answers:
    → Run build_index.py again
    → Make sure your knowledge/ folder has .txt files with content


GEMINI API KEY:
──────────────
  The API key in this package: AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM

  If you hit a 429 quota error, the free tier is exhausted for the day.
  You can get a new free key at: https://aistudio.google.com/

══════════════════════════════════════════════════════════════════════════
