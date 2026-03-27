from openrouter_ai import chat_with_openrouter

def is_kurdish(text: str) -> bool:
    """Detect Kurdish text"""
    kurdish_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
    total_chars = sum(1 for char in text if char.strip())
    return (kurdish_chars / total_chars if total_chars > 0 else 0) > 0


def call_kurdish_ai(prompt: str, history: list = None) -> str:
    """Call Kurdish AI using OpenRouter (lightweight!)"""
    return chat_with_openrouter(prompt, history, detected_lang="ku")
