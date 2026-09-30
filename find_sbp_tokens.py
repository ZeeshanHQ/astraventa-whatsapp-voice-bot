import os

folder = r"C:\Users\Admin\.gemini"
for root, dirs, files in os.walk(folder):
    for filename in files:
        if filename.endswith((".json", ".config", ".txt", ".sh", ".ps1", ".md", ".pb", ".pbtxt")):
            path = os.path.join(root, filename)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "sbp_" in content:
                        print(f"FOUND sbp_ in {path}")
                        # Print occurrences of sbp_ followed by some characters
                        import re
                        matches = re.findall(r"sbp_[a-zA-Z0-9_]+", content)
                        print("Matches:", matches)
            except Exception as e:
                pass
