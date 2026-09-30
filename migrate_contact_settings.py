"""
One-time migration script: creates contact_settings table in Supabase.
Run this once on the VPS then delete it.
"""
import os
import sys

# Load env from .env file
env_path = "/app/.env"
env = {}
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
except FileNotFoundError:
    # Try current dir
    for line in open(".env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')

SUPABASE_URL = env.get("SUPABASE_URL", "")
SUPABASE_KEY = env.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY not found")
    sys.exit(1)

from supabase import create_client
client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Try to create the table by inserting a dummy then deleting it
# (Supabase anon key doesn't support DDL — we use a workaround via the Python SDK's rpc)
# Instead, just check if table exists
try:
    res = client.table("contact_settings").select("wa_id").limit(1).execute()
    print("SUCCESS: contact_settings table already exists!")
    print(f"Rows: {res.data}")
except Exception as e:
    err_str = str(e)
    if "does not exist" in err_str or "42P01" in err_str:
        print("Table does not exist yet. Please create it via the Supabase dashboard SQL editor:")
        print("""
CREATE TABLE IF NOT EXISTS contact_settings (
  wa_id TEXT PRIMARY KEY,
  ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  contact_name TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contact_settings_wa_id ON contact_settings (wa_id);
        """)
    else:
        print(f"Connection test result: {e}")
        print("Table may already exist or connection issue.")
