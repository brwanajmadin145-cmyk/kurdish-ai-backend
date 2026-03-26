import os
from openai import OpenAI
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO

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


def edit_image(image_path, prompt, filename="edited.png"):
    """Edit image using DALL-E 2 (DALL-E 3 doesn't support editing yet)"""
    print(f"✏️ Editing image with DALL-E 2: {prompt[:50]}...")
    
    filepath = f"{IMAGE_FOLDER}/{filename}"
    
    try:
        # Open and prepare the image
        img = Image.open(image_path).convert("RGBA")
        
        # Resize to 1024x1024 (DALL-E requirement)
        img = img.resize((1024, 1024))
        
        # Save as PNG temporarily
        temp_path = f"{IMAGE_FOLDER}/temp_edit.png"
        img.save(temp_path, "PNG")
        
        # 🔥 EDIT WITH DALL-E 2
        with open(temp_path, "rb") as image_file:
            response = client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt=f"Transform this image: {prompt}. Keep the overall composition but apply the changes. High quality, professional.",
                n=1,
                size="1024x1024"
            )
        
        # Get the edited image URL
        image_url = response.data[0].url
        
        # Download the edited image
        print("📥 Downloading edited image...")
        img_response = requests.get(image_url, timeout=60)
        
        if img_response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(img_response.content)
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            print(f"✅ Edited image saved: {filepath}")
            return filepath
        else:
            print(f"❌ Download failed: {img_response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Edit error: {e}")
        print(f"💡 Generating new image instead...")
        # Fallback: generate a new image with the edit prompt
        return generate_image(f"{prompt}, high quality, professional", filename)


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