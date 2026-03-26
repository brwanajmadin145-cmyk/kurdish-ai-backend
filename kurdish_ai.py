import requests
import os
from dotenv import load_dotenv

load_dotenv()

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")


def is_kurdish(text: str) -> bool:
    """Detect Kurdish text"""
    kurdish_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
    total_chars = sum(1 for char in text if char.strip())
    return (kurdish_chars / total_chars if total_chars > 0 else 0) > 0.2


def call_kurdish_ai(prompt: str, history: list = None) -> str:
    """Call Kurdish AI model from HuggingFace - with fallback if model unavailable"""
    try:
        # UPDATED: Using a more stable Kurdish model
        url = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
        
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Build conversation context
        full_prompt = prompt
        
        if history:
            context = ""
            for msg in history[-3:]:
                if msg['role'] == 'user':
                    context += f"پرسیار: {msg['content']}\n"
                elif msg['role'] == 'assistant':
                    context += f"وەڵام: {msg['content']}\n"
            
            full_prompt = context + f"پرسیار: {prompt}\nوەڵام:"
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 500,
                "temperature": 0.7,
                "return_full_text": False
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # Check if model is loading (503) and wait
        if response.status_code == 503:
            print("⏳ Kurdish model loading, waiting...")
            import time
            time.sleep(20)  # Wait for model to load
            response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract response
            if isinstance(result, list) and len(result) > 0:
                answer = result[0].get('generated_text', '').strip()
            else:
                answer = result.get('generated_text', '').strip()
            
            if answer:
                print(f"✅ Kurdish AI: {answer[:80]}...")
                return answer
            else:
                print("⚠️ Kurdish AI returned empty response")
                return None
        else:
            print(f"❌ HuggingFace error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Kurdish AI error: {e}")
        return None


if __name__ == "__main__":
    # Test
    test = call_kurdish_ai("سڵاو، چۆنی؟")
    if test:
        print(f"\n{test}")