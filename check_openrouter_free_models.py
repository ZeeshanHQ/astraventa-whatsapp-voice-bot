import urllib.request
import json

def check_free():
    url = "https://openrouter.ai/api/v1/models"
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode())
        models = data.get("data", [])
        
        free_models = []
        for m in models:
            pricing = m.get("pricing", {})
            prompt = float(pricing.get("prompt", 0))
            completion = float(pricing.get("completion", 0))
            if prompt == 0.0 and completion == 0.0:
                free_models.append(m.get("id"))
                
        print("Active Free Models on OpenRouter:")
        for fm in free_models:
            print(f"- {fm}")
    except Exception as e:
        print("Error fetching models:", e)

if __name__ == "__main__":
    check_free()
