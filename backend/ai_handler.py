from google.genai import Client
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Get API key
api_key = os.getenv('GEMINI_API_KEY')
print(f"🔍 DEBUG: Gemini API Key Status: {'FOUND ✅' if api_key else 'NOT FOUND ❌'}")
if api_key:
    print(f"🔍 DEBUG: API Key starts with: {api_key[:20]}...")

class AIReceptionist:
    def __init__(self):
        self.system_prompt = """You are a helpful AI receptionist for a medical clinic. 
        Your job is to:
        1. Help customers book appointments
        2. Answer questions about our services
        3. Get customer information (name, email, phone)
        
        Available services: Doctor Visit, Dental Checkup, Eye Checkup, Health Checkup
        
        When a customer wants to book:
        - Ask for preferred date
        - Ask for preferred time
        - Ask for service type
        - Ask for their name and contact info
        
        Respond in a friendly, professional manner.
        """
        
        try:
            self.client = Client(api_key=api_key)
            print("✅ Gemini client initialized successfully!")
        except Exception as e:
            print(f"❌ Error initializing Gemini: {e}")
            self.client = None

    def get_ai_response(self, user_message, conversation_history=[]):
        """Get response from Google Gemini API"""
        try:
            if not api_key or not self.client:
                print("⚠️ WARNING: Gemini not configured!")
                return "Sorry, I'm not configured yet. Please add your Gemini API key."
            
            # Build prompt with history
            full_prompt = self.system_prompt + "\n\n"
            
            for msg in conversation_history:
                if msg["role"] == "user":
                    full_prompt += f"Customer: {msg['content']}\n"
                else:
                    full_prompt += f"Receptionist: {msg['content']}\n"
            
            full_prompt += f"Customer: {user_message}\nReceptionist:"
            
            print(f"📤 Sending request to Gemini...")
            
            # Use the new google.genai API
            response = self.client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=full_prompt
            )
            
            ai_message = response.text.strip()
            print(f"📥 Received response from Gemini ✅")
            return ai_message
            
        except Exception as e:
            print(f"❌ Gemini Error: {e}")
            print(f"❌ Error Type: {type(e).__name__}")
            return "Sorry, I'm having trouble processing that. Can you try again?"

    def extract_appointment_data(self, ai_response):
        """Extract appointment data from AI response if it exists"""
        try:
            if "APPOINTMENT_DATA:" in ai_response:
                json_str = ai_response.split("APPOINTMENT_DATA:")[-1].strip()
                ai_response = ai_response.split("APPOINTMENT_DATA:")[0].strip()
                appointment_data = json.loads(json_str)
                return ai_response, appointment_data
        except:
            pass
        
        return ai_response, None

    def detect_intent(self, user_message):
        """Detect user intent (booking, inquiry, etc.)"""
        keywords = {
            'booking': ['book', 'appointment', 'schedule', 'reserve'],
            'inquiry': ['information', 'services', 'hours', 'cost', 'how much'],
            'cancellation': ['cancel', 'remove', 'delete appointment'],
            'greeting': ['hi', 'hello', 'hey', 'good morning']
        }
        
        message_lower = user_message.lower()
        
        for intent, words in keywords.items():
            for word in words:
                if word in message_lower:
                    return intent
        
        return 'general'

# Initialize AI Receptionist
ai = AIReceptionist()