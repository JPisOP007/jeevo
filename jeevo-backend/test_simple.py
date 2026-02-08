"""
Simple test script for Jeevo Bot - Quick verification
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_message(query, phone="919999999999"):
    """Send a test message and show response"""
    print(f"\n{'='*60}")
    print(f"📱 Query: {query}")
    print('='*60)
    
    webhook_data = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": "1058738433982120"
                    },
                    "contacts": [{
                        "profile": {"name": "Test User"},
                        "wa_id": phone
                    }],
                    "messages": [{
                        "from": phone,
                        "id": f"wamid.test.{int(time.time())}",
                        "timestamp": str(int(time.time())),
                        "text": {"body": query},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    response = requests.post(f"{BASE_URL}/webhook", json=webhook_data)
    result = response.json()
    
    print(f"✅ Status: {result['status']}")
    print(f"📝 Message ID: {result['message_id']}")
    
    # Wait and get response from DB
    time.sleep(3)
    
    import subprocess
    cmd = [
        "docker", "exec", "jeevo-postgres",
        "psql", "-U", "postgres", "-d", "jeevo", "-t", "-c",
        f"SELECT bot_response FROM conversations WHERE message_id = '{result['message_id']}';"
    ]
    
    try:
        db_result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        response_text = db_result.stdout.strip()
        
        print(f"\n🤖 Bot Response:")
        print("-" * 60)
        print(response_text)
        print("-" * 60)
    except Exception as e:
        print(f"Could not fetch response: {e}")

def main():
    print("\n🏥 JEEVO HEALTHCARE BOT - QUICK TEST\n")
    
    # Test 1: Health check
    print("1️⃣ Testing health endpoint...")
    health = requests.get(f"{BASE_URL}/health").json()
    print(f"   ✅ Status: {health['status']}, DB: {health['database']}\n")
    
    # Test 2: Simple query
    test_message("What are the symptoms of high blood pressure?")
    
    # Test 3: Hindi query
    test_message("मुझे बुखार है। क्या करूं?", phone="918888888888")
    
    # Test 4: Prevention query
    test_message("How to prevent diabetes naturally?", phone="917777777777")
    
    print("\n✅ All tests completed!\n")

if __name__ == "__main__":
    main()
