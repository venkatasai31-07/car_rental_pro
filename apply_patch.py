import os
import re

app_file = "backend/app.py"
patch_file = "ROADMIND_SHAREABLE/1_roadmind_backend_patch.py"

with open(app_file, "r", encoding="utf-8") as f:
    app_code = f.read()

with open(patch_file, "r", encoding="utf-8") as f:
    patch_code = f.read()

# EXTRACT HELPER FUNCTIONS
helper_start = patch_code.find("def get_live_car_listings(filters: dict) -> str:")
routes_start = patch_code.find("def register_roadmind_routes(app, engine):")

helper_functions = patch_code[helper_start:routes_start]
routes_functions = patch_code[routes_start:]

# 1. Add imports to top
imports_to_add = """import google.generativeai as genai
import uuid as uuid_lib
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_assistant.rag.retriever import search_knowledge

GEMINI_API_KEY = "AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM"
genai.configure(api_key=GEMINI_API_KEY)

"""

if "import google.generativeai" not in app_code:
    # insert immediately after "import os"
    app_code = app_code.replace("import os", "import os\n\n" + imports_to_add)

# 2. Add table creation
table_creation = """
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
"""

if "ai_chats" not in app_code:
    # insert after the trip_locations creation
    app_code = app_code.replace('print("✅ Tracking table verified/created")', 'print("✅ Tracking table verified/created")\n' + table_creation)

# 3. Add helper functions & routes before app.run()
# We will inject them before `if __name__ == "__main__":`

if "register_roadmind_routes" not in app_code:
    injection_block = "\n# --- ROADMIND AI INTEGRATION ---\n" + helper_functions + "\n" + routes_functions
    injection_block += "\nregister_roadmind_routes(app, engine)\n\n"
    
    app_code = app_code.replace('if __name__ == "__main__":', injection_block + 'if __name__ == "__main__":')

with open(app_file, "w", encoding="utf-8") as f:
    f.write(app_code)

print("backend/app.py patched successfully!")
