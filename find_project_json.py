import os
import json

folder = r"C:\Users\Admin\.gemini\config\projects"
for filename in os.listdir(folder):
    if filename.endswith(".json"):
        path = os.path.join(folder, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                content_str = json.dumps(data)
                if "whats'app_bot_uae" in content_str or "whats-app-bot" in content_str:
                    print(f"FOUND in {filename}: Project Name: {data.get('name')}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")
