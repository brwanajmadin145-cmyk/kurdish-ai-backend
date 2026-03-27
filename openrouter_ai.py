import requests
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def call_openrouter(prompt: str, model: str = "anthropic/claude-3.5-sonnet", history: list = None, system_prompt: str = None):
    """Call OpenRouter API - handles ALL AI tasks"""
    
    messages = []
    
    # Add system prompt if provided
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Add conversation history
    if history:
        for msg in history:
            if msg['role'] in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})
    
    # Add current prompt
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
    """Translate using OpenRouter (replaces NLLB)"""
    
    lang_names = {
        'en': 'English', 'ku': 'Kurdish', 'ar': 'Arabic',
        'tr': 'Turkish', 'fa': 'Persian', 'ru': 'Russian',
        'fr': 'French', 'es': 'Spanish', 'de': 'German',
        'zh-cn': 'Chinese', 'ja': 'Japanese', 'hi': 'Hindi'
    }
    
    target_name = lang_names.get(target_lang, target_lang)
    
    prompt = f"Translate this text to {target_name}. Only return the translation, nothing else:\n\n{text}"
    
    result = call_openrouter(
        prompt=prompt,
        model="google/gemini-2.0-flash-exp:free",  # Free model for translation
        system_prompt="You are a professional translator. Only return the translation without any explanation."
    )
    
    return result


def chat_with_openrouter(prompt: str, history: list = None, detected_lang: str = "en"):
    """Chat using OpenRouter (replaces GROQ)"""
    
    lang_names = {
        'en': 'English', 'ku': 'Kurdish', 'ar': 'Arabic',
        'tr': 'Turkish', 'fa': 'Persian', 'ru': 'Russian',
        'fr': 'French', 'es': 'Spanish', 'de': 'German',
        'zh': 'Chinese', 'ja': 'Japanese', 'hi': 'Hindi'
    }
    
    user_language = lang_names.get(detected_lang, 'English')
    
    system_prompt = f"""You are Kurdish AI, created in 2026 by Brwa Najmadin Mohhmad (Computer Institute of Sulaymaniyah) under supervision of Naz Najib Abdulla.

🔒 CRITICAL IDENTITY RULES:
- Your name: Kurdish AI (NEVER forget)
- Creator: Brwa Najmadin Mohhmad
- Supervisor: Naz Najib Abdulla
- Institution: Computer Institute of Sulaymaniyah
- Year: 2026
- NEVER say: "I was not created by...", "I'm just an AI", "I don't have a creator"
- NEVER mention: Meta, Llama, Facebook, OpenAI, Claude, ChatGPT, Anthropic, Google

🌍 LANGUAGE RULE - VERY IMPORTANT:
The user is speaking in {user_language}.
YOU MUST respond in {user_language} - DO NOT respond in English unless the user asked in English!

If asked about your identity in ANY language, say: "I am Kurdish AI, created by Brwa Najmadin Mohhmad under the supervision of Naz Najib Abdulla in 2026" - but say it in the user's language ({user_language})!"""
    
    if detected_lang == 'ku':
        system_prompt += "\n\nبۆ کوردی: بەکارهێنانی پیتە کوردییەکان (ێ، ۆ، ڕ، ڵ، وو)، خاڵ لە کۆتایی."
    
    result = call_openrouter(
        prompt=prompt,
        model="google/gemini-2.0-flash-exp:free",  # Free, fast, multilingual
        history=history,
        system_prompt=system_prompt
    )
    
    return result


def generate_content_with_openrouter(topic: str, num_pages: int, doc_type: str):
    """Generate document content using OpenRouter (replaces GROQ)"""
    
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
    
    response = call_openrouter(
        prompt=prompt,
        model="google/gemini-2.0-flash-exp:free"
    )
    
    # Parse response into structured content
    content = []
    current_section = None
    
    if response:
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
    
    # Quality assurance
    for section in content:
        points = section.get('points', [])
        while len(points) < 4 and len(points) > 0:
            points.append("Additionally, it's important to consider the long-term effects and sustainable approaches when implementing these strategies.")
        section['points'] = points[:7]
    
    while len(content) < num_pages:
        content.append({
            'title': 'Additional Key Insights',
            'points': [
                'Comprehensive analysis reveals multiple interconnected factors that significantly influence overall outcomes.',
                'Data-driven approaches combined with expert insights provide robust frameworks for informed decisions.',
                'Best practices emphasize continuous improvement through iterative processes and regular assessment.',
                'Stakeholder engagement and clear communication channels are essential for achieving shared objectives.'
            ]
        })
    
    return content[:num_pages]


# Test
if __name__ == "__main__":
    print("🚀 Testing OpenRouter...")
    result = chat_with_openrouter("سڵاو، چۆنی؟", detected_lang="ku")
    if result:
        print(f"✅ Kurdish response: {result}")