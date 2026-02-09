"""
Test script to verify image analysis functionality
"""
import sys
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.vision import VisionAnalyzer
from dotenv import load_dotenv

def test_image_analysis():
    """Test the vision analyzer with the uploaded image"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if API keys are configured
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
    
    print("=" * 70)
    print("JEEVO VISION ANALYZER TEST")
    print("=" * 70)
    print()
    
    if use_groq:
        if not groq_key:
            print("❌ ERROR: USE_GROQ=true but GROQ_API_KEY not found in .env")
            print("   Please add GROQ_API_KEY to your .env file")
            return
        print(f"✅ Using Groq Vision API")
    else:
        if not openai_key:
            print("❌ ERROR: OPENAI_API_KEY not found in .env")
            print("   Please add OPENAI_API_KEY to your .env file")
            print("   OR set USE_GROQ=true and add GROQ_API_KEY")
            return
        print(f"✅ Using OpenAI Vision API")
    
    print()
    
    # Initialize vision analyzer
    try:
        vision = VisionAnalyzer()
        print("✅ Vision Analyzer initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Vision Analyzer: {e}")
        return
    
    print()
    
    # Test with the uploaded image
    image_path = "WhatsApp Image 2026-02-09 at 21.46.17.jpeg"
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    print(f"📷 Analyzing image: {image_path}")
    print(f"   File size: {os.path.getsize(image_path)} bytes")
    print()
    
    # Test in English
    print("-" * 70)
    print("TEST 1: Analysis in English")
    print("-" * 70)
    try:
        result = vision.analyze_image(
            image_path=image_path,
            query="Please analyze this image and describe what you see. Is there any visible injury, rash, or medical condition?",
            language="en"
        )
        print("✅ Analysis completed")
        print()
        print("RESULT:")
        print(result)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print()
    
    # Test in Hindi
    print("-" * 70)
    print("TEST 2: Analysis in Hindi")
    print("-" * 70)
    try:
        result = vision.analyze_image(
            image_path=image_path,
            query="कृपया इस चित्र का विश्लेषण करें और बताएं कि आप क्या देखते हैं। क्या कोई दिखाई देने वाली चोट, दाने, या चिकित्सा स्थिति है?",
            language="hi"
        )
        print("✅ Analysis completed")
        print()
        print("RESULT:")
        print(result)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
    
    print()
    print("=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)

if __name__ == "__main__":
    test_image_analysis()
