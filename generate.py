import os
from openai import OpenAI
from dotenv import load_dotenv
import requests


load_dotenv()

IMAGE_FOLDER = "files"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# 🔑 Configure OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

print("✅ OpenAI DALL-E 3 configured!")


def generate_image(prompt, filename="output.png"):
    """Generate image using DALL-E 3 - HIGH QUALITY!"""
    print(f"🎨 Generating with DALL-E 3: {prompt[:50]}...")
    
    filepath = f"{IMAGE_FOLDER}/{filename}"
    
    try:
        # 🔥 GENERATE IMAGE WITH DALL-E 3
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",  # or "hd" for higher quality (costs more)
            n=1,
        )
        
        # Get the image URL
        image_url = response.data[0].url
        
        # Download the image
        print("📥 Downloading generated image...")
        img_response = requests.get(image_url, timeout=60)
        
        if img_response.status_code == 200:
            # Save image
            with open(filepath, 'wb') as f:
                f.write(img_response.content)
            
            print(f"✅ DALL-E 3 image saved: {filepath}")
            return filepath
        else:
            print(f"❌ Download failed: {img_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ DALL-E 3 error: {e}")
        return None


# Test function
if __name__ == "__main__":
    print("🚀 Testing DALL-E 3...")
    
    if not OPENAI_API_KEY:
        print("❌ No OpenAI API key found in .env file!")
    else:
        print(f"✅ API Key found: {OPENAI_API_KEY[:20]}...")
        result = generate_image("A beautiful Kurdish mountain landscape at sunset, highly detailed, professional photography", "test_dalle3.png")
        
        if result:
            print(f"✅ Success! Image saved at: {result}")
        else:
            print("❌ Failed to generate image!")
