from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres.pxnangovncbvfbjywnbv:omSriganesha06@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    print("Adding missing columns to buy_requests...")
    conn.execute(text("ALTER TABLE buy_requests ADD COLUMN IF NOT EXISTS buyer_name VARCHAR(255)"))
    conn.execute(text("ALTER TABLE buy_requests ADD COLUMN IF NOT EXISTS buyer_mobile VARCHAR(20)"))
    print("✅ Columns added successfully!")
