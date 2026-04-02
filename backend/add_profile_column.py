import os
from sqlalchemy import create_engine, text
from datetime import datetime
import random

# 🔐 Use environment variable (IMPORTANT)
DATABASE_URL = "postgresql://postgres.pxnangovncbvfbjywnbv:omSriganesha06@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

engine = create_engine(DATABASE_URL)

print("🚀 Starting PostgreSQL migration...")

with engine.begin() as conn:

    # -----------------------------
    # 1️⃣ Add missing columns safely
    # -----------------------------
    conn.execute(text("""
        ALTER TABLE signup
        ADD COLUMN IF NOT EXISTS phone TEXT
    """))

    conn.execute(text("""
        ALTER TABLE signup
        ADD COLUMN IF NOT EXISTS account_id TEXT
    """))

    conn.execute(text("""
        ALTER TABLE signup
        ADD COLUMN IF NOT EXISTS profile_img TEXT
    """))

    conn.execute(text("""
        ALTER TABLE signup
        ADD COLUMN IF NOT EXISTS created_at TEXT
    """))

    print("✅ Columns verified/added")

    # -----------------------------
    # 2️⃣ Fill missing created_at
    # -----------------------------
    today = datetime.now().strftime("%d %b %Y")

    conn.execute(text("""
        UPDATE signup
        SET created_at = :today
        WHERE created_at IS NULL
    """), {"today": today})

    print("📅 created_at updated")

    # -----------------------------
    # 3️⃣ Generate account IDs safely
    # -----------------------------
    users = conn.execute(text("""
        SELECT id FROM signup
        WHERE account_id IS NULL
    """)).fetchall()

    for u in users:
        acc_id = "CRP" + str(random.randint(10000, 99999))

        conn.execute(text("""
            UPDATE signup
            SET account_id = :acc_id
            WHERE id = :id
        """), {
            "acc_id": acc_id,
            "id": u[0]
        })

    print("🆔 Account IDs generated")

print("🎉 Migration completed successfully!")