import os
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

print(f"Supabase URL from environment: {url}")
if not url or not key:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY not in container environment!")
    # Try fallback to /app/.env
    try:
        env = {}
        with open("/app/.env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"')
        url = env.get("SUPABASE_URL")
        key = env.get("SUPABASE_KEY")
        print(f"Loaded fallback from /app/.env. URL: {url}")
    except Exception as e:
        print(f"Fallback reading /app/.env failed: {e}")

client = create_client(url, key)

print("Checking RPC functions...")
try:
    # Try calling a common admin helper RPC if it exists
    res = client.rpc("exec_sql", {"query": "SELECT 1"}).execute()
    print("exec_sql RPC exists! Response:", res.data)
except Exception as e:
    print("exec_sql RPC failed:", e)

try:
    # Let's try calling match_knowledge_base RPC just to test RPC connectivity
    res = client.rpc("match_knowledge_base", {
        "query_embedding": [0.0]*768,
        "match_threshold": 0.1,
        "match_count": 1
    }).execute()
    print("match_knowledge_base RPC exists! Response:", res.data)
except Exception as e:
    print("match_knowledge_base RPC failed:", e)
