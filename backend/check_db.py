from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres.pxnangovncbvfbjywnbv:omSriganesha06@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Checking columns in buy_requests...")
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'buy_requests'"))
    for row in res:
        print(row[0])
