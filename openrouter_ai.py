import requests
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# لێرەدا وا دەکەین کە هەمیشە ناوی مۆدێلەکە لە ڕەیڵوەی وەربگرێت
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

def call_openrouter(prompt: str, model: str = None, history: list = None, system_prompt: str = None):
    """Call OpenRouter API - handles ALL AI tasks"""
    
    # ئەگەر مۆدێل دیاری نەکرابوو، ئەو مۆدێلە بەکاربهێنە کە لە Variables دامانناوە
    if model is None:
        model = MODEL_NAME
    
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
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Kurdish AI",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            print(f"❌ OpenRouter error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ OpenRouter error: {e}")
        return None


def translate_with_openrouter(text: str, target_lang: str, source_lang: str = "auto"):
    lang_names = {
        'en': 'English', 'ku': 'Kurdish', 'ar': 'Arabic',
        'tr': 'Turkish', 'fa': 'Persian', 'ru': 'Russian',
        'fr': 'French', 'es': 'Spanish', 'de': 'German',
        'zh-cn': 'Chinese', 'ja': 'Japanese', 'hi': 'Hindi'
    }
    
    target_name = lang_names.get(target_lang, target_lang)
    prompt = f"Translate this text to {target_name}. Only return the translation, nothing else:\n\n{text}"
    
    return call_openrouter(
        prompt=prompt,
        model=MODEL_NAME, # لێرە گۆڕدرا بۆ گۆڕاوە نوێیەکە
        system_prompt="You are a professional translator. Only return the translation without any explanation."
    )


def chat_with_openrouter(prompt: str, history: list = None, detected_lang: str = "en"):
    lang_names = {
        'en': 'English', 'ku': 'Kurdish', 'ar': 'Arabic',
        'tr': 'Turkish', 'fa': 'Persian', 'ru': 'Russian',
        'fr': 'French', 'es': 'Spanish', 'de': 'German',
        'zh': 'Chinese', 'ja': 'Japanese', 'hi': 'Hindi'
    }
    
    user_language = lang_names.get(detected_lang, 'English')
    
    system_prompt = f"""You are Kurdish AI, created in 2026 by Brwa Najmadin Mohhmad (Computer Institute of Sulaymaniyah) under supervision of Naz Najib Abdulla.
🔒 identity rules apply. Respond in {user_language}."""
    
    return call_openrouter(
        prompt=prompt,
        model=MODEL_NAME, # لێرە گۆڕدرا بۆ گۆڕاوە نوێیەکە
        history=history,
        system_prompt=system_prompt
    )


def generate_content_with_openrouter(topic: str, num_pages: int, doc_type: str):
    prompt = f"Generate professional content about {topic} for {num_pages} {doc_type}."
    return call_openrouter(
        prompt=prompt,
        model=MODEL_NAME # لێرە گۆڕدرا بۆ گۆڕاوە نوێیەکە
    )
