from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from docx import Document
from pptx import Presentation
from pptx.util import Pt
import pytesseract
import requests
import datetime
import textwrap
import shutil
import os
import re
from dotenv import load_dotenv
from groq import Groq
from generate import generate_image, edit_image
from presentation_generator import generate_gamma_presentation
from pdf_generator import generate_pdf_document
from word_generator import generate_word_document
from kurdish_ai import is_kurdish, call_kurdish_ai
from db_config import (
    init_database, create_conversation, save_message, get_conversation_history,
    get_all_conversations, save_image, get_user_images, save_file, get_user_files,
    save_feedback, get_all_feedback, reset_user_account, get_db,
    # 🔒 ADD THESE NEW PRIVACY FUNCTIONS:
    has_privacy_password, set_privacy_password, check_privacy_password,
    create_privacy_conversation, save_privacy_message, get_privacy_conversation_history,
    get_all_privacy_conversations, save_privacy_image, get_user_privacy_images,
    save_privacy_file, get_user_privacy_files, reset_privacy_data
)

# 🔒 LOAD ENVIRONMENT VARIABLES
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()
from fastapi.staticfiles import StaticFiles

# دڵنیابە ئەم دوو دێڕە لێرەن بۆ ئەوەی ڕێگە بە مۆبایل بدات فایلەکان دابەزێنێت
os.makedirs("files", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/file", StaticFiles(directory="files"), name="file")
app.mount("/uploads", StaticFiles(directory="uploads"), name="file")

# 🔒 RATE LIMITING
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # ڕێگەدان بە هەموو ناونیشانەکان
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PostgreSQL database
init_database()

# 🔒 USE ENVIRONMENT VARIABLES
BASE_URL = os.getenv("BASE_URL", "https://kurdish-ai-backend-production.up.railway.app")
document_buffer = ""
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ===================== TESSERACT OCR SETUP =====================
# لە جیاتی ئەو دێڕەی سەرەوە، ئەمە دابنێ:
if os.name == 'nt': # ئەگەر ویندۆز بوو
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else: # ئەگەر لینوکس (Render) بوو
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# ===================== NLLB TRANSLATOR SETUP =====================
# 🔒 LOAD ENVIRONMENT VARIABLES
load_dotenv()

# 🚀 INITIALIZE GROQ CLIENT
# ئیتر پێویستمان بە genai.configure نییە، ئەمە بەکاربهێنە:
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# نەخشەی زمانەکان (هەمان لیست بهێڵەرەوە چونکە بۆ Groq-یش بەکاردێت)
LANG_NAMES = {
    'en': 'English', 'ku': 'Kurdish Sorani', 'ar': 'Arabic', 
    'tr': 'Turkish', 'fa': 'Persian', 'ru': 'Russian', 
    'fr': 'French', 'es': 'Spanish', 'de': 'German', 
    'zh-cn': 'Chinese', 'ja': 'Japanese', 'hi': 'Hindi'
}

# ===================== PYDANTIC MODELS =====================
class Message(BaseModel):
    text: str
    user_id: str = "default_user"
    conversation_id: Optional[int] = None

class TranslationRequest(BaseModel):
    text: str
    target_language: str
    source_language: str = "auto"
    user_id: str = "default_user"

class FeedbackRequest(BaseModel):
    user_id: str
    user_email: str = ""
    rating: int
    message: str

class PrivacyPasswordRequest(BaseModel):
    user_id: str
    password: str

# ===================== MULTILINGUAL GREETING RESPONSES =====================
GREETING_RESPONSES = {
    'en': "Hello! I'm Kurdish AI, your intelligent assistant. I can help you with translations, document creation, image generation, code debugging, and much more. How can I assist you today?",
    'ku': "سڵاو! من ژیری دەستکردی کوردیم، یاریدەدەری زیرەکی تۆ. دەتوانم یارمەتیت بدەم لە وەرگێڕان، دروستکردنی بەڵگەنامە، دروستکردنی وێنە، چاککردنەوەی کۆد، و زۆر شتی تر. چۆن دەتوانم یارمەتیت بدەم؟",
    'ar': "مرحبا! أنا الذكاء الاصطناعي الكردي، مساعدك الذكي. يمكنني مساعدتك في الترجمة وإنشاء المستندات وتوليد الصور وتصحيح الأكواد والمزيد. كيف يمكنني مساعدتك اليوم؟",
    'tr': "Merhaba! Ben Kürt Yapay Zekası, akıllı asistanınım. Çeviri, belge oluşturma, görsel üretimi, kod hata ayıklama ve daha fazlasında size yardımcı olabilirim. Bugün size nasıl yardımcı olabilirim?",
    'fa': "سلام! من هوش مصنوعی کردی هستم. می‌توانم در ترجمه، ایجاد اسناد، تولید تصویر و موارد دیگر کمک کنم. چگونه می‌توانم کمک کنم؟",
    'ru': "Здравствуйте! Я Курдский ИИ. Могу помочь с переводами, документами, изображениями и многим другим. Как я могу помочь?",
    'fr': "Bonjour! Je suis l'IA Kurde. Je peux vous aider avec les traductions, documents, images et plus encore. Comment puis-je vous aider?",
    'es': "¡Hola! Soy IA Kurda. Puedo ayudarte con traducciones, documentos, imágenes y más. ¿Cómo puedo ayudarte?",
    'de': "Hallo! Ich bin Kurdische KI. Ich kann bei Übersetzungen, Dokumenten, Bildern und mehr helfen. Wie kann ich helfen?",
    'zh': "你好！我是库尔德人工智能。我可以帮助翻译、文档、图像等。我能如何帮助您？",
    'ja': "こんにちは！私はクルド人AIです。翻訳、ドキュメント、画像などをお手伝いできます。どのようにお手伝いできますか？",
    'hi': "नमस्ते! मैं कुर्दिश एआई हूं। मैं अनुवाद, दस्तावेज़, छवियों में मदद कर सकता हूं। मैं कैसे मदद कर सकता हूं?"
}

IDENTITY_RESPONSES = {
    'en': "My name is Kurdish AI. I was created by Brwa Najmadin Mohhmad, a student at the Computer Institute of Sulaymaniyah, under the supervision of Naz Najib Abdulla and i was made in 2026.",
    'ku': "ناوی من ژیری دەستکردی کوردییە. من لەلایەن بڕوا نەجمەدین مەحمەد، خوێندکاری پەیمانگای کۆمپیوتەری سلێمانی، دروستکراوم، لەژێر سەرپەرشتی ناز نەجیب عەبدوڵڵا.",
    'ar': "اسمي الذكاء الاصطناعي الكردي. تم إنشائي بواسطة برڤا نجم الدين محمد، طالب في معهد الكمبيوتر في السليمانية، تحت إشراف ناز نجيب عبدالله.",
    'tr': "Adım Kürt Yapay Zekası. Süleymaniye Bilgisayar Enstitüsü öğrencisi Brwa Najmadin Mohhmad tarafından, Naz Najib Abdulla'nın gözetiminde yaratıldım.",
    'fa': "نام من هوش مصنوعی کردی است. من توسط بروا نجم‌الدین محمد، دانشجوی موسسه کامپیوتر سلیمانیه، تحت نظارت ناز نجیب عبدالله ایجاد شده‌ام.",
    'ru': "Меня зовут Курдский ИИ. Я был создан Брва Наджмадином Мохммадом, студентом Компьютерного института Сулеймании, под руководством Наз Наджиб Абдуллы.",
    'fr': "Je m'appelle IA Kurde. J'ai été créé par Brwa Najmadin Mohhmad, étudiant à l'Institut informatique de Sulaymaniyah, sous la supervision de Naz Najib Abdulla.",
    'es': "Mi nombre es IA Kurda. Fui creado por Brwa Najmadin Mohhmad, estudiante del Instituto de Computación de Sulaymaniyah, bajo la supervisión de Naz Najib Abdulla.",
    'de': "Mein Name ist Kurdische KI. Ich wurde von Brwa Najmadin Mohhmad, einem Studenten am Computerinstitut von Sulaymaniyah, unter der Aufsicht von Naz Najib Abdulla erstellt.",
    'zh': "我的名字是库尔德人工智能。我由苏莱曼尼亚计算机学院的学生 Brwa Najmadin Mohhmad 在 Naz Najib Abdulla 的监督下创建。",
    'ja': "私の名前はクルド人AIです。私はスレイマニヤのコンピュータ研究所の学生 Brwa Najmadin Mohhmad によって、Naz Najib Abdulla の監督の下で作成されました。",
    'hi': "मेरा नाम कुर्दिश एआई है। मुझे सुलेमानिया कंप्यूटर संस्थान के छात्र ब्रवा नजमादिन मोहम्मद ने नाज़ नजीब अब्दुल्ला की देखरेख में बनाया था।"
}



def detect_language(text: str):
    """Detect language from text - IMPROVED VERSION"""
    text_lower = text.lower().strip()
    
    # Kurdish/Arabic script detection
    if any('\u0600' <= char <= '\u06FF' for char in text):
        # Kurdish-specific characters
        kurdish_chars = ['ێ', 'ۆ', 'ڕ', 'ڵ']
        if any(char in text for char in kurdish_chars):
            return 'ku'  # Kurdish
        
        # Persian-specific characters
        persian_chars = ['گ', 'پ', 'چ', 'ژ']
        if any(char in text for char in persian_chars):
            # Check if more Kurdish or Persian
            kurdish_count = sum(1 for char in kurdish_chars if char in text)
            persian_count = sum(1 for char in persian_chars if char in text)
            if kurdish_count > persian_count:
                return 'ku'
            return 'fa'  # Persian
        
        return 'ar'  # Arabic (default for Arabic script)
    
    # Cyrillic (Russian)
    if any('\u0400' <= char <= '\u04FF' for char in text):
        return 'ru'
    
    # Chinese
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        return 'zh'
    
    # Japanese
    if any('\u3040' <= char <= '\u30ff' for char in text):
        return 'ja'
    
    # Turkish detection
    turkish_chars = ['ş', 'ğ', 'ı', 'ö', 'ü', 'ç']
    if any(char in text_lower for char in turkish_chars):
        return 'tr'
    
    # Common word detection
    if any(w in text_lower for w in ['hola', 'gracias', 'buenos', 'qué', 'cómo', 'dónde']): 
        return 'es'  # Spanish
    
    if any(w in text_lower for w in ['bonjour', 'merci', 'salut', 'comment', 'où']): 
        return 'fr'  # French
    
    if any(w in text_lower for w in ['hallo', 'danke', 'guten', 'wie', 'wo']): 
        return 'de'  # German
    
    if any(w in text_lower for w in ['merhaba', 'teşekkür', 'nasıl', 'nerede', 'kim']): 
        return 'tr'  # Turkish
    
    if any(w in text_lower for w in ['नमस्ते', 'धन्यवाद', 'कैसे']): 
        return 'hi'  # Hindi
    
    return 'en'  # Default English

# ===================== NLLB TRANSLATION FUNCTION =====================
def translate_text_openrouter(text: str, target_lang: str = 'ku'):
    full_lang_name = LANG_NAMES.get(target_lang, "Kurdish Sorani")
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "HTTP-Referer": "https://kurdish-ai-backend.onrender.com", # لێرە لێنکە نوێیەکەت دابنێ
                "X-Title": "Kurdish AI",
            },
            json={
                "model": "meta-llama/llama-3.3-70b-instruct", 
                "messages": [
                    {
                        "role": "system", 
                        "content": f"You are a professional translator. Translate to {full_lang_name}. Only provide the translation."
                    },
                    {"role": "user", "content": text}
                ],
                "temperature": 0.1, # کەمکردنەوەی پلەی گەرمی بۆ خێرایی
                "max_tokens": 1000 # دیاریکردنی سنور بۆ وەڵامدانەوە
            },
            timeout=25 # 🔒 گرنگ: پێش ئەوەی Render بپچڕێت، با Requests خۆی بوەستێت
        )
        
        result = response.json()
        if 'choices' in result:
            translated = result['choices'][0]['message']['content'].strip()
            return {"success": True, "translated_text": translated}
        else:
            return {"success": False, "error": "Invalid response from OpenRouter"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "error": "OpenRouter timed out. Try a shorter text."}
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    
    

# ===================== GROQ API (SUPER FAST) =====================
def call_groq(prompt: str, conversation_id: int, user_id: str = "default_user", save_to_db: bool = True):
    """Call Groq API with Kurdish support"""
    
    history = get_conversation_history(conversation_id, limit=5)
    
    messages = []
    
    # ✅ DETECT LANGUAGE FIRST (BEFORE USING IT!)
    detected_lang = detect_language(prompt)
    
    # Language names for system prompt
    lang_names = {
        'en': 'English',
        'ar': 'Arabic',
        'tr': 'Turkish',
        'fa': 'Persian (Farsi)',
        'ru': 'Russian',
        'fr': 'French',
        'es': 'Spanish',
        'de': 'German',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'hi': 'Hindi',
        'ku': 'Kurdish'
    }
    
    user_language = lang_names.get(detected_lang, 'English')
    
    # ✅ SUPER STRONG IDENTITY + LANGUAGE INSTRUCTION
    messages.append({
        "role": "system",
        "content": f"""You are Kurdish AI, created in 2026 by Brwa Najmadin Mohhmad (Computer Institute of Sulaymaniyah) under supervision of Naz Najib Abdulla.

🔒 CRITICAL IDENTITY RULES:
• Your name: Kurdish AI (NEVER forget)
• Creator: Brwa Najmadin Mohhmad
• Supervisor: Naz Najib Abdulla
• Year: 2026
• NEVER say: "I was not created by...", "I'm just an AI", "I don't have a creator"
• NEVER mention: Meta, Llama, Facebook, OpenAI, Claude, ChatGPT

🌍 LANGUAGE RULE - VERY IMPORTANT:
The user is speaking in {user_language}.
YOU MUST respond in {user_language} - DO NOT respond in English unless the user asked in English!
If user asks in Arabic → respond in Arabic
If user asks in Turkish → respond in Turkish
If user asks in Spanish → respond in Spanish
And so on for ALL languages.

If asked about your identity in ANY language, say: "I am Kurdish AI, created by Brwa Najmadin Mohhmad under the supervision of Naz Najib Abdulla in 2026" - but say it in the user's language ({user_language})!"""
    })
    
    # Kurdish-specific formatting (only if Kurdish)
    if detected_lang == 'ku':
        messages.append({
            "role": "system",
            "content": "بۆ کوردی: بەکارهێنانی پیتە کوردییەکان (ێ، ۆ، ڕ، ڵ، وو)، خاڵ لە کۆتایی."
        })
    
    # Add conversation history
    for msg in history:
        if msg['role'] == 'assistant' and msg['content'].startswith('FILE:'):
            continue
        if msg['role'] == 'user':
            messages.append({"role": "user", "content": msg['content']})
        else:
            messages.append({"role": "assistant", "content": msg['content']})
    
    # Add current message
    messages.append({"role": "user", "content": prompt})
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 2048
        }
    )
    
    result = response.json()
    ai_response = result['choices'][0]['message']['content']
    
    if save_to_db:
        save_message(user_id, conversation_id, "user", prompt)
        save_message(user_id, conversation_id, "assistant", ai_response)
    
    return ai_response

def call_ai_smart(prompt: str, conversation_id: int, user_id: str = "default_user", save_to_db: bool = True):
    """
    Smart AI:
    - Kurdish → HuggingFace Kurdish model (uses HUGGINGFACE_API_KEY from env)
    - English/Other → GROQ
    """
    if is_kurdish(prompt):
        print("🇰🇼 Kurdish → HuggingFace Kurdish AI")
        
        history = get_conversation_history(conversation_id, limit=3)
        response = call_kurdish_ai(prompt, history)
        
        if response:
            if save_to_db:
                save_message(user_id, conversation_id, "user", prompt)
                save_message(user_id, conversation_id, "assistant", response)
            return response
        else:
            print("⚠️ Kurdish AI failed, using GROQ")
            return call_groq(prompt, conversation_id, user_id, save_to_db)
    else:
        print("🌐 English → GROQ")
        return call_groq(prompt, conversation_id, user_id, save_to_db)

# 🎨 GENERATE DOCUMENT CONTENT WITH GROQ AI
def generate_content_with_groq(topic: str, num_pages: int, doc_type: str, conversation_id: int, user_id: str):
    """Generate detailed content for PDF/Word/PowerPoint using GROQ AI"""
    
    prompt = f"""You are a professional content creator. Create an OUTSTANDING, DETAILED {doc_type} about: {topic}

CRITICAL REQUIREMENTS:
- Generate EXACTLY {num_pages} {'slides' if doc_type == 'presentation' else 'pages'}
- Each {'slide' if doc_type == 'presentation' else 'page'} MUST have 5-7 DETAILED points
- Each point should be 15-25 words with SPECIFIC information, examples, or data
- Make it informative, engaging, and professional
- Use concrete examples, statistics, and actionable insights

STRUCTURE:

{'Slide' if doc_type == 'presentation' else 'Page'} 1 (Title):
Title: [Powerful, professional title about {topic}]
{'Subtitle: [Compelling one-sentence hook]' if doc_type == 'presentation' else ''}

{'Slides' if doc_type == 'presentation' else 'Pages'} 2 to {num_pages} (Content):

For EACH {'slide' if doc_type == 'presentation' else 'page'}, provide:
Title: [Clear, specific section title]
Points: [5-7 detailed, informative points]
- [First detailed point with specific information - 15-25 words explaining key concept]
- [Second point with concrete examples and real-world applications - 15-25 words]
- [Third point with statistics, data, or research findings - 15-25 words]
- [Fourth point with best practices or recommendations - 15-25 words]
- [Fifth point with case studies or success stories - 15-25 words]
- [Sixth point with challenges or considerations - 15-25 words]
- [Optional seventh point with future implications - 15-25 words]

Now create {num_pages} {'slides' if doc_type == 'presentation' else 'pages'} about: {topic}

Make every point SUBSTANTIAL, SPECIFIC, and VALUABLE!"""
    
    response = call_groq(prompt, conversation_id, user_id, save_to_db=False)
    
    # Parse AI response
    content = []
    current_section = None
    
    for line in response.split('\n'):
        line = line.strip()
        
        if line.startswith('Title:'):
            if current_section:
                content.append(current_section)
            title = line.replace('Title:', '').strip()
            current_section = {'title': title, 'points': []}
        elif line.startswith('Subtitle:'):
            if current_section:
                subtitle = line.replace('Subtitle:', '').strip()
                current_section['subtitle'] = subtitle
        elif (line.startswith('-') or line.startswith('•')) and current_section:
            point = line.lstrip('-•').strip()
            if point and len(point.split()) >= 10:
                current_section['points'].append(point)
    
    if current_section:
        content.append(current_section)
    
    # Quality assurance - ensure rich content
    for section in content:
        points = section.get('points', [])
        # Ensure at least 4 points per section
        while len(points) < 4 and len(points) > 0:
            points.append("Additionally, it's important to consider the long-term effects and sustainable approaches when implementing these strategies to ensure continued success and optimal results.")
        section['points'] = points[:7]  # Max 7 points
    
    # Ensure correct number of sections
    while len(content) < num_pages:
        content.append({
            'title': 'Additional Key Insights',
            'points': [
                'Comprehensive analysis reveals multiple interconnected factors that significantly influence overall outcomes and require strategic planning',
                'Data-driven approaches combined with expert insights provide robust frameworks for making informed decisions in complex scenarios',
                'Best practices emphasize continuous improvement through iterative processes, regular assessment, and adaptive methodologies',
                'Stakeholder engagement and clear communication channels are essential for ensuring alignment and achieving shared objectives effectively'
            ]
        })
    
    return content[:num_pages]

def detect_user_intent(text: str):
    text_lower = text.lower().strip()
    cv_keywords = ["cv", "resume", "curriculum vitae", "سی ڤی", "سيرة ذاتية", "özgeçmiş", "رزومه"]
    if any(keyword in text_lower for keyword in cv_keywords):
        return "cv_generate"
    
    return "chat"



# ===================== OCR IMAGE ANALYSIS =====================
def extract_text_from_image(image_path: str):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return f"Error reading image: {str(e)}"

def analyze_code_with_groq(code_text: str, user_prompt: str, conversation_id: int, user_id: str):
    analysis_prompt = f"""You are an expert programming teacher. A student has sent you code and needs help.

Student's question: {user_prompt}

Here is the code from their screenshot:
```
{code_text}
```

Please help them by:
1. Identifying the programming language
2. Finding ALL errors (syntax errors, missing semicolons, typos, etc.)
3. Explaining clearly what's wrong
4. Showing the corrected code

Response format:
"I can see this is [LANGUAGE] code.

Problem: [Describe the error]

What's wrong: [Explain the issue]

Corrected code:
```[language]
[show fixed code]
```

This should fix your error!"

Now analyze and help:"""
    
    return call_groq(analysis_prompt, conversation_id, user_id)

# ===================== SMART INTENT DETECTION =====================
def detect_user_intent(text: str):
    text_lower = text.lower().strip()
    
    translate_keywords = [
        "translate", "translation", "وەرگێڕان", "گۆڕین بۆ", 
        "to kurdish", "to english", "to arabic", "to turkish",
        "to russian", "to persian", "to farsi", "to french",
        "to spanish", "to german", "to chinese", "to japanese", "to hindi"
    ]
    if any(keyword in text_lower for keyword in translate_keywords):
        return "translate"
    
    greeting_words = ["hi", "hello", "hey", "sup", "yo", "greetings", "سڵاو", "سلام", 
                      "merhaba", "bonjour", "hola", "hallo", "नमस्ते", "你好", "こんにちは"]
    if text_lower in greeting_words or text_lower.startswith(tuple(greeting_words)):
        if len(text_lower.split()) <= 2:
            return "greeting"
    
    identity_keywords = ["who are you", "who created you", "your name", "تۆ کێیت", 
                         "کێ تۆی دروست کرد", "من انت", "من صنعک", "kim yarattı", 
                         "qui es-tu", "quién eres", "wer bist du"]
    if any(keyword in text_lower for keyword in identity_keywords):
        return "identity"
    
    document_keywords = ["pdf", "word", "doc", "docx", "ppt", "powerpoint", "presentation", "slides"]
    if any(keyword in text_lower for keyword in document_keywords):
        return "document"
    
    image_generate_keywords = [
        "generate image", "create image", "make image", "draw",
        "generate a picture", "create a picture", "make a picture",
        "show me a picture", "create artwork", "generate art"
    ]
    
    strong_image_words = ["realistic", "4k", "8k", "cinematic", "artstation", "detailed rendering"]
    
    if any(keyword in text_lower for keyword in image_generate_keywords):
        return "image_generate"
    
    if any(word in text_lower for word in strong_image_words):
        if any(word in text_lower for word in ["a ", "an ", "the ", "show ", "picture of"]):
            return "image_generate"
    
    return "chat"

# ===================== TRANSLATION ENDPOINT =====================
@app.post("/translate")
def translate_endpoint(request: TranslationRequest):
    # بانگکردنی Groq بۆ وەرگێڕان
    result = translate_text_groq(
        text=request.text,
        target_lang=request.target_language
    )
    
    if result["success"]:
        # ئەمانە وەک خۆی بهێڵەرەوە بۆ داتابەیسەکە
        conversation_id = create_conversation(request.user_id, f"Translation: {request.text[:30]}")
        save_message(request.user_id, conversation_id, "user", request.text)
        save_message(request.user_id, conversation_id, "assistant", result["translated_text"])
        
        return {
            "success": True,
            "translated": result["translated_text"]
        }
    else:
        return {"success": False, "error": result["error"]}


@app.get("/")
def health_check():
    return {"status": "alive", "service": "Kurdish AI"}
    

# ===================== CHAT (FAST WITH GROQ) =====================
@app.post("/chat")
@limiter.limit("30/minute")
def chat(request: Request, message: Message):
    global document_buffer
    user_text = message.text
    user_id = message.user_id
    
    conversation_id = message.conversation_id
    if not conversation_id:
        conversation_id = create_conversation(user_id, user_text[:50])
    
    intent = detect_user_intent(user_text)
    
    # ===== TRANSLATION =====
    if intent == "translate":
        text_lower = user_text.lower()
        
        if "to kurdish" in text_lower or "بۆ کوردی" in text_lower:
            target = "ku"
        elif "to english" in text_lower:
            target = "en"
        elif "to arabic" in text_lower:
            target = "ar"
        elif "to turkish" in text_lower:
            target = "tr"
        elif "to russian" in text_lower:
            target = "ru"
        elif "to persian" in text_lower or "to farsi" in text_lower:
            target = "fa"
        elif "to french" in text_lower:
            target = "fr"
        elif "to spanish" in text_lower:
            target = "es"
        elif "to german" in text_lower:
            target = "de"
        elif "to chinese" in text_lower:
            target = "zh-cn"
        elif "to japanese" in text_lower:
            target = "ja"
        elif "to hindi" in text_lower:
            target = "hi"
        else:
            target = "en"
        
        text_to_translate = user_text
        remove_phrases = [
            "translate", "translation", "to kurdish", "to english", 
            "to arabic", "to turkish", "to russian", "to persian",
            "to farsi", "to french", "to spanish", "to german",
            "to chinese", "to japanese", "to hindi", "this", ":"
        ]
        
        for phrase in remove_phrases:
            text_to_translate = text_to_translate.lower().replace(phrase, "")
        
        text_to_translate = text_to_translate.strip()
        
        if not text_to_translate or len(text_to_translate) < 2:
            return {"reply": "Please provide text to translate. Example: translate hello to kurdish"}
        
        result = translate_text_openrouter(text_to_translate, target_lang=target)
        
        if result["success"]:
            reply = f"{result['translated_text']}"
            save_message(user_id, conversation_id, "user", user_text)
            save_message(user_id, conversation_id, "assistant", reply)
            return {"reply": reply, "conversation_id": conversation_id}
        else:
            return {"reply": f"Translation error: {result['error']}"}
        
    
    
    
    # ===== MULTILINGUAL GREETING =====
    if intent == "greeting":
        lang = detect_language(user_text)
        reply = GREETING_RESPONSES.get(lang, GREETING_RESPONSES['en'])
        document_buffer = reply
        save_message(user_id, conversation_id, "user", user_text)
        save_message(user_id, conversation_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conversation_id}
    
    # ===== MULTILINGUAL IDENTITY =====
    if intent == "identity":
        lang = detect_language(user_text)
        reply = IDENTITY_RESPONSES.get(lang, IDENTITY_RESPONSES['en'])
        document_buffer = reply
        save_message(user_id, conversation_id, "user", user_text)
        save_message(user_id, conversation_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conversation_id}
    
    # 3. ADD THIS IN THE chat() FUNCTION (after image_generate section, around line 650):


    
    # ===== DOCUMENT GENERATION =====
    if intent == "document":
        save_message(user_id, conversation_id, "user", user_text)
        
        lower = user_text.lower()
        
        # Extract number (default 5)
        num_match = re.search(r'(\d+)\s*(slide|page|slides|pages)', lower)
        num_items = int(num_match.group(1)) if num_match else 5
        
        # 🔥 POWERPOINT
        if "ppt" in lower or "powerpoint" in lower or "presentation" in lower or "slides" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "presentation", conversation_id, user_id)
            prs = generate_gamma_presentation(user_text, num_items, 'modern', ai_content)
            
            os.makedirs("files", exist_ok=True)
            filename = f"files/presentation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            prs.save(filename)
            just_name = os.path.basename(filename)
            file_url = f"{BASE_URL}/file/{just_name}"
            
            save_file(user_id, conversation_id, file_url, just_name, "pptx")
            save_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        # 🔥 PDF
        if "pdf" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "pdf", conversation_id, user_id)
            filename = generate_pdf_document(user_text, num_items, ai_content)
            just_name = os.path.basename(filename)
            file_url = f"{BASE_URL}/file/{just_name}"
            
            save_file(user_id, conversation_id, file_url, just_name, "pdf")
            save_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        # 🔥 WORD
        if "word" in lower or "doc" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "word", conversation_id, user_id)
            filename = generate_word_document(user_text, num_items, ai_content)
            just_name = os.path.basename(filename)
            file_url = f"{BASE_URL}/file/{just_name}"
            
            save_file(user_id, conversation_id, file_url, just_name, "docx")
            save_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        return {"reply": "Please specify document type: pdf, word, or powerpoint", "conversation_id": conversation_id}
    
    # ===== IMAGE GENERATION =====
    # ===== IMAGE GENERATION =====
    # ===== IMAGE GENERATION =====
    # ===== IMAGE GENERATION =====
    if intent == "image_generate":
        filename = generate_image(
            user_text,
            filename=f"image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        
        just_image_name = os.path.basename(filename)
        image_url = f"{BASE_URL}/file/{just_image_name}"
        
        save_message(user_id, conversation_id, "user", user_text)
        save_message(user_id, conversation_id, "assistant", f"Generated image: {filename}")
        save_image(user_id, conversation_id, image_url, user_text, "generated")
        
        return {
            "type": "image",
            "url": image_url,
            "conversation_id": conversation_id
        }
    
    # ===== REGULAR CHAT ===== ← ADD THIS!
    reply = call_ai_smart(user_text, conversation_id, user_id)
    document_buffer = reply
    return {"reply": reply, "conversation_id": conversation_id}



# ===================== IMAGE ANALYSIS ENDPOINT (OCR) =====================
@app.post("/analyze-image")
async def analyze_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    user_id: str = Form("default_user"),
    conversation_id: Optional[int] = Form(None)
):
    os.makedirs("uploads", exist_ok=True)
    
    if not conversation_id:
        conversation_id = create_conversation(user_id, f"Image Analysis: {prompt[:30]}")
    
    input_path = f"uploads/analyze_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}"
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    extracted_text = extract_text_from_image(input_path)
    
    if not extracted_text or len(extracted_text) < 5:
        reply = "I couldn't read any text from this image. Please make sure the image is clear and contains text or code."
    else:
        prompt_lower = prompt.lower()
        code_keywords = ["code", "error", "bug", "wrong", "fix", "problem", "issue", "debug"]
        is_code_question = any(keyword in prompt_lower for keyword in code_keywords)
        
        if is_code_question:
            reply = analyze_code_with_groq(extracted_text, prompt, conversation_id, user_id)
        else:
            analysis_prompt = f"""The user sent an image containing this text:

{extracted_text}

User's question: {prompt}

Please provide a helpful answer based on the text content."""
            
            reply = call_groq(analysis_prompt, conversation_id, user_id)
    
    return {
        "type": "text",
        "reply": reply,
        "conversation_id": conversation_id
    }

# ===================== IMAGE EDIT ENDPOINT =====================
@app.post("/image-edit")
async def image_edit(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    user_id: str = Form("default_user"),
    conversation_id: Optional[int] = Form(None)
):
    os.makedirs("uploads", exist_ok=True)
    
    if not conversation_id:
        conversation_id = create_conversation(user_id, f"Image Edit: {prompt[:30]}")

    input_path = f"uploads/input_{image.filename}"
    output_name = f"edited_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    edited_file = edit_image(
        image_path=input_path,
        prompt=prompt,
        filename=output_name
    )
    
    image_url = f"/file/{edited_file}"
    
    save_message(user_id, conversation_id, "user", f"Edit image: {prompt}")
    save_message(user_id, conversation_id, "assistant", f"Edited image: {edited_file}")
    save_image(user_id, conversation_id, image_url, prompt, "edited")

    return {
        "type": "image",
        "url": image_url,
        "conversation_id": conversation_id
    }

# ===================== GET ALL CONVERSATIONS =====================
@app.get("/conversations/{user_id}")
def get_user_conversations_endpoint(user_id: str):
    conversations = get_all_conversations(user_id)
    return {"conversations": conversations}

# ===================== GET CONVERSATION MESSAGES =====================
@app.get("/conversation/{conversation_id}")
def get_conversation_messages_endpoint(conversation_id: int):
    messages = get_conversation_history(conversation_id)
    return {"messages": messages}

# ===================== GET USER IMAGES =====================
@app.get("/images/{user_id}")
def get_images_endpoint(user_id: str):
    images = get_user_images(user_id)
    return {"images": images}

# ===================== GET USER FILES =====================
@app.get("/files/{user_id}")
def get_files_endpoint(user_id: str):
    files = get_user_files(user_id)
    return {"files": files}

# ===================== DELETE CONVERSATION =====================
@app.delete("/conversation/{conversation_id}")
def delete_conversation_endpoint(conversation_id: int):
    """Delete a conversation and all its messages"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE conversation_id = %s",
                (conversation_id,)
            )
            conn.commit()
            cursor.close()
            
            return {"success": True, "message": "Conversation deleted"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===================== RENAME CONVERSATION =====================
@app.put("/conversation/{conversation_id}/rename")
def rename_conversation_endpoint(conversation_id: int, new_title: str):
    """Rename a conversation"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET title = %s WHERE conversation_id = %s",
                (new_title, conversation_id)
            )
            conn.commit()
            cursor.close()
            
            return {"success": True, "message": "Conversation renamed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===================== DELETE FILE =====================
@app.delete("/file/{file_id}")
def delete_file_endpoint(file_id: int):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_url FROM files WHERE file_id = %s", (file_id,))
            result = cursor.fetchone()
            
            if result:
                file_url = result['file_url']
                
                # 1. سڕینەوە لە داتابەیس (ئەمە هەمیشە کار دەکات)
                cursor.execute("DELETE FROM files WHERE file_id = %s", (file_id,))
                conn.commit()
                
                # 2. سڕینەوەی فایلی فیزیکی لەسەر Railway
                try:
                    # لێرەدا تەنها ناوی فایلەکە وەردەگرین
                    filename = file_url.split('/')[-1]
                    # ناونیشانی ڕاستەقینە لەسەر سێرڤەر: files/filename.pdf
                    filepath = os.path.join("files", filename)
                    
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"✅ File {filepath} deleted from disk")
                except Exception as e:
                    print(f"⚠️ Could not delete physical file: {e}")
                
                return {"success": True, "message": "File deleted successfully"}
            return {"success": False, "error": "File not found"}
                
    except Exception as e:
        return {"success": False, "error": str(e)}
# ===================== RENAME FILE =====================
@app.put("/file/{file_id}/rename")
def rename_file_endpoint(file_id: int, new_name: str):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 1. سەرەتا زانیارییە کۆنەکان وەردەگرین
            cursor.execute("SELECT file_url, file_type FROM files WHERE file_id = %s", (file_id,))
            result = cursor.fetchone()
            
            if not result:
                return {"success": False, "error": "File not found"}

            old_url = result['file_url']
            file_type = result['file_type']
            
            # 2. ناوی فیزیکی نوێ دروست دەکەین (بۆ ئەوەی لێنکەکە ئیش بکات)
            old_filename = old_url.split('/')[-1]
            # لێرەدا replace بەکاردێنین بۆ ئەوەی سپەیس نەبێتە کێشە لە لێنکەکەدا
            clean_new_name = new_name.replace(' ', '_')
            new_filename = f"{clean_new_name}.{file_type}"
            new_url = f"{BASE_URL}/file/{new_filename}"

            # 3. گۆڕینی ناوی فایلەکە لەسەر سێرڤەر (گرنگترین بەش)
            old_path = os.path.join("files", old_filename)
            new_path = os.path.join("files", new_filename)
            
            try:
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
            except Exception as disk_error:
                print(f"Disk Rename Error: {disk_error}")
                # ئەگەر فایلەکە لەسەر دیسک نەبوو، هەر بەردەوام بە بۆ ئەوەی لانی کەم لە داتابەیس ناوەکە بگۆڕێت

            # 4. نوێکردنەوەی داتابەیس ڕێک وەک چاتەکە بەڵام URLـەکەش دەگۆڕین
            cursor.execute(
                "UPDATE files SET file_name = %s, file_url = %s WHERE file_id = %s",
                (new_name, new_url, file_id)
            )
            conn.commit()
            
            return {
                "success": True, 
                "message": "File renamed successfully",
                "new_url": new_url,
                "new_title": new_name
            }
                
    except Exception as e:
        return {"success": False, "error": str(e)}
# ===================== SUBMIT FEEDBACK =====================
@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """Save user feedback"""
    try:
        feedback_id = save_feedback(
            user_id=request.user_id,
            user_email=request.user_email,
            rating=request.rating,
            message=request.message
        )
        
        return {
            "success": True,
            "message": "Thank you for your feedback!",
            "feedback_id": feedback_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
@app.get("/privacy/check/{user_id}")
def check_privacy_setup(user_id: str):
    """Check if user has set up privacy password"""
    has_password = has_privacy_password(user_id)
    return {
        "has_password": has_password
    }


@app.post("/privacy/setup")
def setup_privacy_password(request: PrivacyPasswordRequest):
    """Set up privacy password for first time"""
    try:
        set_privacy_password(request.user_id, request.password)
        return {
            "success": True,
            "message": "Privacy password set successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/privacy/verify")
def verify_privacy_password(request: PrivacyPasswordRequest):
    """Verify privacy password"""
    is_correct = check_privacy_password(request.user_id, request.password)
    return {
        "success": is_correct,
        "message": "Password correct" if is_correct else "Incorrect password"
    }


@app.get("/privacy/conversations/{user_id}")
def get_privacy_conversations_endpoint(user_id: str):
    """Get all PRIVACY conversations"""
    conversations = get_all_privacy_conversations(user_id)
    return {"conversations": conversations}


@app.get("/privacy/conversation/{conversation_id}")
def get_privacy_conversation_messages_endpoint(conversation_id: int):
    """Get PRIVACY conversation messages"""
    messages = get_privacy_conversation_history(conversation_id)
    return {"messages": messages}


@app.get("/privacy/images/{user_id}")
def get_privacy_images_endpoint(user_id: str):
    """Get all PRIVACY images"""
    images = get_user_privacy_images(user_id)
    return {"images": images}


@app.get("/privacy/files/{user_id}")
def get_privacy_files_endpoint(user_id: str):
    """Get all PRIVACY files"""
    files = get_user_privacy_files(user_id)
    return {"files": files}


@app.delete("/privacy/reset/{user_id}")
def reset_privacy_endpoint(user_id: str):
    """Delete ALL privacy data - DANGEROUS!"""
    try:
        reset_privacy_data(user_id)
        return {
            "success": True,
            "message": "All privacy data deleted successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/privacy/chat")
@limiter.limit("30/minute")
def privacy_chat(request: Request, message: Message):
    """Chat endpoint for PRIVACY mode - uses privacy database"""
    global document_buffer
    user_text = message.text
    user_id = message.user_id
    
    conversation_id = message.conversation_id
    if not conversation_id:
        # Create PRIVACY conversation
        conversation_id = create_privacy_conversation(user_id, user_text[:50])
    
    intent = detect_user_intent(user_text)
    
    # Handle all intents same as normal chat, but save to PRIVACY database
    
    # ===== TRANSLATION =====
    if intent == "translate":
        # ... same translation logic ...
        # But use save_privacy_message instead of save_message
        pass

    
    
    
    # ===== GREETING =====
    if intent == "greeting":
        lang = detect_language(user_text)
        reply = GREETING_RESPONSES.get(lang, GREETING_RESPONSES['en'])
        save_privacy_message(user_id, conversation_id, "user", user_text)
        save_privacy_message(user_id, conversation_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conversation_id}
    
    # ===== IDENTITY =====
    if intent == "identity":
        lang = detect_language(user_text)
        reply = IDENTITY_RESPONSES.get(lang, IDENTITY_RESPONSES['en'])
        save_privacy_message(user_id, conversation_id, "user", user_text)
        save_privacy_message(user_id, conversation_id, "assistant", reply)
        return {"reply": reply, "conversation_id": conversation_id}
    
    # ===== DOCUMENT GENERATION =====
    if intent == "document":
        save_privacy_message(user_id, conversation_id, "user", user_text)
        
        lower = user_text.lower()
        num_match = re.search(r'(\d+)\s*(slide|page|slides|pages)', lower)
        num_items = int(num_match.group(1)) if num_match else 5
        
        # POWERPOINT
        if "ppt" in lower or "powerpoint" in lower or "presentation" in lower or "slides" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "presentation", conversation_id, user_id)
            prs = generate_gamma_presentation(user_text, num_items, 'modern', ai_content)
            
            os.makedirs("files", exist_ok=True)
            filename = f"files/presentation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            prs.save(filename)
            file_url = f"/file/{filename}"
            
            save_privacy_file(user_id, conversation_id, file_url, filename, "pptx")
            save_privacy_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        # PDF
        if "pdf" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "pdf", conversation_id, user_id)
            filename = generate_pdf_document(user_text, num_items, ai_content)
            file_url = f"/file/{filename}"
            
            save_privacy_file(user_id, conversation_id, file_url, filename, "pdf")
            save_privacy_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        # WORD
        if "word" in lower or "doc" in lower:
            ai_content = generate_content_with_groq(user_text, num_items, "word", conversation_id, user_id)
            filename = generate_word_document(user_text, num_items, ai_content)
            file_url = f"/file/{filename}"
            
            save_privacy_file(user_id, conversation_id, file_url, filename, "docx")
            save_privacy_message(user_id, conversation_id, "assistant", f"FILE:{file_url}")
            
            return {"reply": file_url, "conversation_id": conversation_id}
        
        return {"reply": "Please specify document type: pdf, word, or powerpoint", "conversation_id": conversation_id}
    
    # ===== IMAGE GENERATION =====
    if intent == "image_generate":
        filename = generate_image(
            user_text,
            filename=f"image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        
        image_url = f"{BASE_URL}/file/{filename}"
        
        save_privacy_message(user_id, conversation_id, "user", user_text)
        save_privacy_message(user_id, conversation_id, "assistant", f"Generated image: {filename}")
        save_privacy_image(user_id, conversation_id, image_url, user_text, "generated")
        
        return {
            "type": "image",
            "url": image_url,
            "conversation_id": conversation_id
        }
    
    # ===== REGULAR CHAT =====
    # Use privacy conversation history
    history = get_privacy_conversation_history(conversation_id, limit=5)
    
    if is_kurdish(user_text):
        response = call_kurdish_ai(user_text, history)
        if response:
            save_privacy_message(user_id, conversation_id, "user", user_text)
            save_privacy_message(user_id, conversation_id, "assistant", response)
            return {"reply": response, "conversation_id": conversation_id}
    
    # Use GROQ for other languages
    detected_lang = detect_language(user_text)
    
    lang_names = {
        'en': 'English', 'ar': 'Arabic', 'tr': 'Turkish',
        'fa': 'Persian', 'ru': 'Russian', 'fr': 'French',
        'es': 'Spanish', 'de': 'German', 'zh': 'Chinese',
        'ja': 'Japanese', 'hi': 'Hindi', 'ku': 'Kurdish'
    }
    
    user_language = lang_names.get(detected_lang, 'English')
    
    # ✅ SUPER STRONG IDENTITY + LANGUAGE
    messages = []
    messages.append({
        "role": "system",
        "content": f"""You are Kurdish AI, created in 2026 by Brwa Najmadin Mohhmad at the Computer Institute of Sulaymaniyah, supervised by Naz Najib Abdulla.

🔒 IDENTITY RULES (NEVER BREAK):
• Name: Kurdish AI (ALWAYS)
• Creator: Brwa Najmadin Mohhmad
• Supervisor: Naz Najib Abdulla
• Year: 2026
• NEVER say: "I was not created by...", "I'm just an AI"
• NEVER mention: Meta, Llama, Facebook, OpenAI, Claude, ChatGPT

🌍 CRITICAL LANGUAGE RULE:
User is speaking {user_language}.
YOU MUST respond in {user_language} - NOT in English!
Match the user's language exactly.

If asked about identity, respond in {user_language}: "I am Kurdish AI, created by Brwa Najmadin Mohhmad under supervision of Naz Najib Abdulla in 2026" """
    })
    
    # Kurdish-specific
    if detected_lang == 'ku':
        messages.append({
            "role": "system",
            "content": "بۆ کوردی: پیتە کوردییەکان (ێ، ۆ، ڕ، ڵ، وو)، خاڵ لە کۆتایی."
        })
    
    # Add conversation history
    for msg in history:
        if msg['role'] == 'assistant' and msg['content'].startswith('FILE:'):
            continue
        messages.append({"role": msg['role'], "content": msg['content']})
    
    messages.append({"role": "user", "content": user_text})
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 2048
        }
    )
    
    result = response.json()
    ai_response = result['choices'][0]['message']['content']
    
    save_privacy_message(user_id, conversation_id, "user", user_text)
    save_privacy_message(user_id, conversation_id, "assistant", ai_response)
    
    return {"reply": ai_response, "conversation_id": conversation_id}

@app.delete("/privacy/conversation/{conversation_id}")
def delete_privacy_conversation(conversation_id: int):
    """Delete a privacy conversation and all its messages"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM privacy_conversations WHERE conversation_id = %s", (conversation_id,))
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/privacy/conversation/{conversation_id}")
def delete_privacy_conversation(conversation_id: int):
    """Delete a privacy conversation and all its messages"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM privacy_conversations WHERE conversation_id = %s", (conversation_id,))
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/privacy/conversation/{conversation_id}")
def delete_privacy_conversation(conversation_id: int):
    """Delete a privacy conversation and all its messages"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM privacy_conversations WHERE conversation_id = %s", (conversation_id,))
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Rename privacy conversation
@app.put("/privacy/conversation/{conversation_id}/rename")
def rename_privacy_conversation(conversation_id: int, new_title: str):
    """Rename a privacy conversation"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE privacy_conversations SET title = %s WHERE conversation_id = %s",
                (new_title, conversation_id)
            )
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Delete privacy file
@app.delete("/privacy/file/{file_id}")
def delete_privacy_file(file_id: int):
    """Delete a privacy file"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM privacy_files WHERE file_id = %s", (file_id,))
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Rename privacy file
@app.put("/privacy/file/{file_id}/rename")
def rename_privacy_file(file_id: int, new_name: str):
    """Rename a privacy file"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE privacy_files SET file_name = %s WHERE file_id = %s",
                (new_name, file_id)
            )
            conn.commit()
            cursor.close()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}



# ===================== ADMIN: VIEW ALL FEEDBACK (PASSWORD PROTECTED) =====================
@app.get("/admin/feedback")
def get_feedback_admin(password: str = ""):
    """Admin page to view all feedback - PASSWORD PROTECTED"""
    
    # 🔒 PASSWORD PROTECTION
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "brwa2025")
    
    if password != ADMIN_PASSWORD:
        return HTMLResponse(content="""
        <html>
        <head>
            <title>Admin Login</title>
            <style>
                body {
                    font-family: Arial;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .login-box {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                }
                input {
                    width: 300px;
                    padding: 10px;
                    margin: 10px 0;
                    border: 2px solid #ddd;
                    border-radius: 5px;
                }
                button {
                    width: 100%;
                    padding: 10px;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                }
                button:hover {
                    background: #764ba2;
                }
            </style>
        </head>
        <body>
            <div class="login-box">
                <h2>🔒 Admin Access</h2>
                <p>Enter admin password to view feedback</p>
                <form method="get">
                    <input type="password" name="password" placeholder="Admin Password" required>
                    <button type="submit">Login</button>
                </form>
            </div>
        </body>
        </html>
        """)
    
    # ✅ PASSWORD CORRECT - SHOW FEEDBACK
    feedback_list = get_all_feedback()
    
    total_feedback = len(feedback_list)
    avg_rating = sum([f['rating'] for f in feedback_list]) / total_feedback if total_feedback > 0 else 0
    
    rows = ""
    for fb in feedback_list:
        stars = "⭐" * fb['rating']
        rows += f"""
        <tr>
            <td>{fb['feedback_id']}</td>
            <td>{fb['user_email'] or 'Anonymous'}</td>
            <td>{stars} ({fb['rating']}/5)</td>
            <td style="max-width: 400px;">{fb['message']}</td>
            <td>{fb['created_at']}</td>
        </tr>
        """
    
    html = f"""
    <html>
    <head>
        <title>Kurdish AI - Feedback Dashboard</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #333;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
            }}
            .stats {{
                display: flex;
                gap: 20px;
                margin: 20px 0;
            }}
            .stat-box {{
                flex: 1;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }}
            .stat-box h3 {{
                margin: 0;
                font-size: 36px;
            }}
            .stat-box p {{
                margin: 5px 0 0 0;
                opacity: 0.9;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background: #667eea;
                color: white;
                padding: 12px;
                text-align: left;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #ddd;
            }}
            tr:hover {{
                background: #f5f5f5;
            }}
            .refresh-btn {{
                background: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                float: right;
            }}
            .refresh-btn:hover {{
                background: #218838;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 Kurdish AI - User Feedback Dashboard</h1>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>{total_feedback}</h3>
                    <p>Total Feedback</p>
                </div>
                <div class="stat-box">
                    <h3>{avg_rating:.1f}/5</h3>
                    <p>Average Rating</p>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>User Email</th>
                        <th>Rating</th>
                        <th>Message</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

# ===================== DOWNLOAD FILE =====================
@app.get("/file/{filename:path}")
def download(filename: str):
    if os.path.exists(filename):
        return FileResponse(filename, filename=os.path.basename(filename))
    return {"error": "File not found"}

# ===================== RESET ACCOUNT =====================
@app.delete("/reset-account/{user_id}")
def reset_account_endpoint(user_id: str):
    """Delete ALL user data - DANGEROUS!"""
    try:
        reset_user_account(user_id)
        
        return {
            "success": True,
            "message": "Account reset successfully. All data deleted."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ===================== API INFO =====================
@app.api_route("/", methods=["GET", "HEAD"])
def root(response: Response):
    """
    ئەم بەشە هەم داواکاری GET قبوڵ دەکات (بۆ بینینی زانیارییەکان)
    هەم داواکاری HEAD (بۆ ئەوەی Render بزانێت سێرڤەرەکە ساغە)
    """
    
    # زانیارییەکانی پڕۆژەکەت
    project_info = {
        "name": "Kurdish AI",
        "version": "5.0 - Complete Multilingual Edition",
        "creator": "Brwa Najmadin Mohhmad",
        "supervisor": "Naz Najib Abdulla",
        "institution": "Computer Institute of Sulaymaniyah",
        "status": "online",
        "features": [
            "💬 Multilingual Chat", "🌍 Translation", "📄 Document Generation",
            "🎨 Image Generation", "🔒 Secure History"
        ]
    }

    # ئەگەر Render تەنها پشکنینی دەکرد (HEAD)، تەنها کۆدی 200 بنێرە و تەواو
    response.status_code = 200
    
    return project_info
@app.head("/")
def head_root(response: Response):
    response.status_code = 200
    return
