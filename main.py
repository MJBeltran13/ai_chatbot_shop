import re
import os
import requests
from flask import Flask, request, jsonify
from functools import lru_cache
from waitress import serve
import json
import time
from werkzeug.serving import run_simple
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for API routes

# Configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = int(os.environ.get("PORT", 1551))

KNOWLEDGE_BASE = """
You are PomBot, the auto parts specialist at PomWorkz workshop.
You ONLY answer questions about the products and pricing listed below.
You are created by Cleo Dipasupil.
You can respond in English or Tagalog.

❌ DO NOT answer any question that is NOT related to the products below.  
✅ If asked anything else, reply: "I only answer questions about auto parts at PomWorkz."  

PRODUCT CATALOG:
Engine Components:
Camshaft - ₱1700
Valve - ₱1500
Muffler (Chix Pipe) - ₱1900

Transmission & Drive:
Pulley Set - ₱2100
Flyball - ₱500
CVT Cleaner - ₱200

Lubricants & Oils:
Motul Oil - ₱320
Gear Oil - ₱75

Services Offered:
Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000
Machine Works – Labor: ₱1,000 - ₱3,000
Change Oil – Labor: ₱250
CVT Cleaning – ₱300
Engine Refresh – ₱4,000

🚨 STRICT RESPONSE RULES:
- ❌ **DO NOT answer unrelated questions.**
- ✅ **Always include exact product prices and availability.**
- ✅ **For unrelated questions, reply: "I only answer questions about auto parts at PomWorkz."**
"""

BADWORDS = [
    "arse",
    "arsehead",
    "arsehole",
    "ass",
    "ass hole",
    "asshole",
    "bastard",
    "bitch",
    "bloody",
    "bollocks",
    "brotherfucker",
    "bugger",
    "bullshit",
    "child-fucker",
    "Christ on a bike",
    "Christ on a cracker",
    "cock",
    "cocksucker",
    "crap",
    "cunt",
    "dammit",
    "damn",
    "damned",
    "damn it",
    "dick",
    "dick-head",
    "dickhead",
    "dumb ass",
    "dumb-ass",
    "dumbass",
    "dyke",
    "faggot",
    "father-fucker",
    "fatherfucker",
    "fuck",
    "fucker",
    "fucking",
    "god dammit",
    "goddammit",
    "God damn",
    "god damn",
    "goddamn",
    "Goddamn",
    "goddamned",
    "goddamnit",
    "godsdamn",
    "hell",
    "holy shit",
    "horseshit",
    "in shit",
    "jackarse",
    "jack-ass",
    "jackass",
    "Jesus Christ",
    "Jesus fuck",
    "Jesus Harold Christ",
    "Jesus H. Christ",
    "Jesus, Mary and Joseph",
    "Jesus wept",
    "kike",
    "mother fucker",
    "mother-fucker",
    "motherfucker",
    "nigga",
    "nigra",
    "pigfucker",
    "piss",
    "prick",
    "pussy",
    "shit",
    "shit ass",
    "shite",
    "sibling fucker",
    "sisterfuck",
    "sisterfucker",
    "slut",
    "son of a bitch",
    "son of a whore",
    "spastic",
    "sweet Jesus",
    "twat",
    "wanker",
]

PRODUCTS = {
    "camshaft": 1700,
    "valve": 1500,
    "muffler": 1900,
    "pulley set": 2100,
    "flyball": 500,
    "cvt cleaner": 200,
    "motul oil": 320,
    "gear oil": 75,
}

SERVICES = {
    "engine upgrade": "₱1,000 - ₱5,000",
    "machine works": "₱1,000 - ₱3,000",
    "change oil": "₱250",
    "cvt cleaning": "₱300",
    "engine refresh": "₱4,000",
}


def contains_badwords(text):
    # Convert text to lowercase and split into words
    words = text.lower().split()
    # Check if any complete word matches a bad word
    return any(word in words for word in BADWORDS)


def get_ollama_response(query, context="", max_retries=3):
    """Get response from Ollama with retry logic"""
    cleaned_query = query.strip().lower()
    
    # Expanded service-related keywords
    service_keywords = [
        "what are the service", "what are the servic",  # Handles typos like "servies"
        "what service", "list service",
        "available service", "show service",
        "tell me the service", "what are your service",
        "services offer", "service list"
    ]
    
    # Check for service queries with more flexible matching
    if any(keyword in cleaned_query for keyword in service_keywords):
        return "\n".join([
            "Here are all services offered at PomWorkz:",
            "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
            "2. Machine Works – Labor: ₱1,000 - ₱3,000",
            "3. Change Oil – Labor: ₱250",
            "4. CVT Cleaning – ₱300",
            "5. Engine Refresh – ₱4,000"
        ])
    
    # Handle price queries directly
    if "how much" in cleaned_query or "price" in cleaned_query or "cost" in cleaned_query:
        # Check services first
        for service, price in SERVICES.items():
            if service in cleaned_query:
                return f"The cost for {service} is {price}."
                
        # Check products
        for product, price in PRODUCTS.items():
            if product in cleaned_query:
                return f"The price of {product} is ₱{price}."
    
    # If query is about services or common questions, don't call Ollama
    if any(keyword in cleaned_query for keyword in ["what services", "available services", "list services", "services offered"]):
        return "\n".join([
            "Here are the services offered at PomWorkz:",
            "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
            "2. Machine Works – Labor: ₱1,000 - ₱3,000",
            "3. Change Oil – Labor: ₱250",
            "4. CVT Cleaning – ₱300",
            "5. Engine Refresh – ₱4,000"
        ])
    
    if "labor" in cleaned_query:
        return "\n".join([
            "Here are our labor costs:",
            "• Engine Upgrade: ₱1,000 - ₱5,000",
            "• Machine Works: ₱1,000 - ₱3,000", 
            "• Change Oil: ₱250",
            "• CVT Cleaning: ₱300",
            "• Engine Refresh: ₱4,000"
        ])

    # Original Ollama call logic
    prompt = f"""You are PomBot, the auto parts specialist at PomWorkz workshop.
Question: {query}
Context: {context}
{KNOWLEDGE_BASE}"""

    for attempt in range(max_retries):
        try:
            data = {
                "model": "phi",
                "prompt": prompt,
                "stream": False
            }
            
            print(f"Attempt {attempt + 1}: Sending request to Ollama API")
            response = requests.post(
                OLLAMA_API_URL, 
                json=data, 
                timeout=15,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'response' in result and result['response'].strip():
                    return result['response'].strip()
            
            print(f"Attempt {attempt + 1} failed, {'retrying' if attempt < max_retries - 1 else 'giving up'}")
            time.sleep(1)  # Wait before retry
            
        except requests.exceptions.RequestException as e:
            print(f"Request error in attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        except Exception as e:
            print(f"General error in attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            
    return None


@lru_cache(maxsize=100)
def get_ai_response(query):
    """Get AI response with fallback"""
    try:
        # Clean and format the input
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return "Please provide a message."

        # Move service check before greetings to prevent greeting responses for service queries
        service_keywords = [
            "what are the service", "what are the servic",
            "what service", "list service",
            "available service", "show service",
            "tell me the service", "what are your service",
            "services offer", "service list"
        ]
        
        if any(keyword in cleaned_query for keyword in service_keywords):
            return "\n".join([
                "Here are all services offered at PomWorkz:",
                "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
                "2. Machine Works – Labor: ₱1,000 - ₱3,000",
                "3. Change Oil – Labor: ₱250",
                "4. CVT Cleaning – ₱300",
                "5. Engine Refresh – ₱4,000"
            ])

        # Check for greetings after service check
        if any(greeting in cleaned_query for greeting in ["hello", "hi", "kumusta", "magandang"]):
            return "Hello! I'm PomBot, your auto parts specialist at PomWorkz. How can I help you today? You can ask about our products, services, or prices."

        # Check for creator/identity questions
        if any(q in cleaned_query for q in ["who created you", "who made you", "who is your creator"]):
            return "I am created by Cleo Dipasupil."

        # Check for service/product lists
        if any(keyword in cleaned_query for keyword in ["what services", "available services", "list services"]):
            return "\n".join([
                "Available Services at PomWorkz:",
                "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
                "2. Machine Works – Labor: ₱1,000 - ₱3,000",
                "3. Change Oil – Labor: ₱250",
                "4. CVT Cleaning – ₱300",
                "5. Engine Refresh – ₱4,000"
            ])
        
        if any(keyword in cleaned_query for keyword in ["what products", "available products", "list products"]):
            return "\n".join([
                "Available Products at PomWorkz:",
                "Engine Components:",
                "- Camshaft: ₱1,700",
                "- Valve: ₱1,500",
                "- Muffler (Chix Pipe): ₱1,900",
                "\nTransmission & Drive:",
                "- Pulley Set: ₱2,100",
                "- Flyball: ₱500",
                "- CVT Cleaner: ₱200",
                "\nLubricants & Oils:",
                "- Motul Oil: ₱320",
                "- Gear Oil: ₱75"
            ])

        # Get response from Ollama
        response = get_ollama_response(cleaned_query, KNOWLEDGE_BASE)
        
        # If we got a valid response, return it
        if response and response.strip():
            return response
            
        # Fallback responses
        return """How can I help you? You can ask:
• About specific product prices (e.g., "How much is a camshaft?")
• About service costs (e.g., "What is the cost of CVT cleaning?")
• For product/service information (e.g., "What is engine refresh?")
• To see all available products or services"""
            
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        return "I encountered an error. Please try again."


@app.after_request
def after_request(response):
    """Add headers to allow cross-origin requests"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' field"}), 400

        user_message = data["message"]
        print(f"\nProcessing message: {user_message}")
        
        response = get_ai_response(user_message)
        print(f"AI response: {response}")
        
        if not response:
            return jsonify({
                "response": "I apologize, but I couldn't generate a response. Please try again."
            }), 503
            
        return jsonify({"response": response})

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            "response": "An error occurred while processing your request."
        }), 500


@app.route("/health", methods=["GET"])
def health():
    try:
        # Test Ollama connection
        response = get_ollama_response("test", max_retries=1)
        if response:
            return jsonify({"status": "healthy", "ollama": "connected"}), 200
        return jsonify({"status": "degraded", "ollama": "not responding"}), 503
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


# WSGI Application
def create_app():
    return app


if __name__ == "__main__":
    print(f"Starting server on {HOST}:{PORT}")
    run_simple(HOST, PORT, app, use_reloader=True)
