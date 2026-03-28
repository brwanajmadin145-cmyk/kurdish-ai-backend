import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ئێستا کلیلەکان لە ڕەیڵوەی وەردەگرین
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

def call_openrouter(prompt: str, model: str = None, history: list = None, system_prompt: str = None):
    """ئەم فانکشنە ڕاستەوخۆ دەچێت بۆ Groq نەک OpenRouter"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    model = MODEL_NAME # هەمیشە مۆدێلی Groq بەکاردەهێنێت
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    if history:
        for msg in history:
            if msg['role'] in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            print(f"❌ Groq error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

# فانکشنەکانی تەرجەمە و چات وەک خۆیان دەمێننەوە بەڵام call_openrouter بەکاردەهێنن
def translate_with_openrouter(text: str, target_lang: str, source_lang: str = "auto"):
    prompt = f"Translate to {target_lang}: {text}"
    return call_openrouter(prompt=prompt, system_prompt="You are a professional translator.")

def chat_with_openrouter(prompt: str, history: list = None, detected_lang: str = "en"):
    system_prompt = f"You are Kurdish AI. Respond in {detected_lang}."
    return call_openrouter(prompt=prompt, history=history, system_prompt=system_prompt)

def generate_content_with_openrouter(topic: str, num_pages: int, doc_type: str):
    prompt = f"Generate content about {topic}."
    return call_openrouter(prompt=prompt)
