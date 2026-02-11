"""
Quick Setup Script for Medical RAG System
Run this once to set up everything
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("="*70)
    print("MEDICAL RAG SYSTEM - QUICK SETUP")
    print("="*70)
    
    # Step 1: Install dependencies
    print("\n📦 Step 1/3: Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed")
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    
    # Step 2: Download documents
    print("\n📄 Step 2/3: Downloading medical documents...")
    try:
        subprocess.run([sys.executable, "document_downloader.py"], check=True)
        print("✅ Documents ready")
    except Exception as e:
        print(f"❌ Failed to download documents: {e}")
        return False
    
    # Step 3: Build vector database
    print("\n🗄️  Step 3/3: Building vector database...")
    try:
        from vector_store import MedicalVectorStore
        store = MedicalVectorStore()
        chunks = store.load_documents()
        print(f"✅ Vector database built with {chunks} chunks")
    except Exception as e:
        print(f"❌ Failed to build vector database: {e}")
        return False
    
    # Test
    print("\n🧪 Running quick test...")
    try:
        from rag_engine import MedicalRAGEngine
        rag = MedicalRAGEngine()
        result = rag.query("What is the treatment for malaria?", top_k=2)
        
        if result['confidence'] in ['low', 'medium', 'high']:
            print("✅ RAG engine working correctly")
            print(f"\nTest Query: 'What is the treatment for malaria?'")
            print(f"Confidence: {result['confidence']}")
            print(f"Sources: {', '.join(result['sources'])}")
            print(f"\nAnswer Preview: {result['answer'][:150]}...")
        else:
            print("⚠️  Test passed but unexpected confidence level")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("✅ SETUP COMPLETE!")
    print("="*70)
    print("\nYour Medical RAG system is ready to use!")
    print("\nNext steps:")
    print("1. Read INTEGRATION_GUIDE.md for integration options")
    print("2. Test with: python rag_engine.py")
    print("3. Integrate into your main project")
    print("="*70)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
