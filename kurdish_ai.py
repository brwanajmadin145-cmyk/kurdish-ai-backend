from openrouter_ai import chat_with_openrouter
# لێرەدا پێویستە مۆدیوڵی Groq یان هەر مۆدیوڵێکی تر کە بۆ عەرەبی بەکاری دەهێنیت هاوردە بکەیت
# بۆ نموونە: from groq_ai import chat_with_groq 

def is_kurdish(text: str) -> bool:
    """Detect Kurdish text based on Unicode range"""
    kurdish_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
    total_chars = sum(1 for char in text if char.strip())
    return (kurdish_chars / total_chars if total_chars > 0 else 0) > 0

def detect_language(text: str) -> str:
    """Detect if the text is Arabic or Kurdish based on specific characters"""
    # ئەو پیتانەی تەنها لە عەرەبیدا هەن
    arabic_exclusive_chars = ['ض', 'ص', 'ث', 'ط', 'ذ', 'ظ', 'ة', 'ك']
    
    # ئەو پیتانەی تەنها لە کوردیدا هەن
    kurdish_exclusive_chars = ['پ', 'چ', 'ژ', 'گ', 'ڤ', 'ڕ', 'ڵ', 'ۆ', 'ێ']

    # ئەگەر پیتێکی عەرەبی تایبەتی تێدا بوو، بڵێ عەرەبییە
    if any(char in text for char in arabic_exclusive_chars):
        return "ar"
    
    # ئەگەر پیتێکی کوردی تایبەتی تێدا بوو، بڵێ کوردییە
    if any(char in text for char in kurdish_exclusive_chars):
        return "ku"
    
    # ئەگەر هیچیانی تێدا نەبوو، پشت بە ڕێژەی پیتەکان دەبەستین
    return "ku" if is_kurdish(text) else "ar"

def call_kurdish_ai(prompt: str, history: list = None) -> str:
    """Routes the prompt to either Groq (Arabic) or OpenRouter (Kurdish)"""
    lang = detect_language(prompt)
    
    if lang == "ar":
        # لێرەدا بانگی Groq بکە چونکە لە زمانی عەرەبیدا بەهێزترە
        # تێبینی: دەبێت فانکشنی chat_with_groq پێناسە کرابێت
        try:
            from groq_service import chat_with_groq # نموونە بۆ ناوی فایلەکە
            return chat_with_groq(prompt, history)
        except ImportError:
            # ئەگەر هێشتا Groq ئامادە نییە، وەک جێگرەوە OpenRouter بەکاربهێنە بە زمانی عەرەبی
            return chat_with_openrouter(prompt, history, detected_lang="ar")
    else:
        # ئەگەر کوردی بوو، وەک پێشوو بەردەوام بە
        return chat_with_openrouter(prompt, history, detected_lang="ku")
