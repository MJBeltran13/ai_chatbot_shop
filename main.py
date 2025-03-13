import re
import subprocess
import os
from flask import Flask, request, jsonify
from functools import lru_cache

app = Flask(__name__)

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


@lru_cache(maxsize=100)
def get_ai_response(query_type, query, context=""):
    """Get AI response using Phi model with caching"""
    try:
        prompts = {
            "what_is": f"""You are PomBot, the auto parts specialist at PomWorkz workshop.
Explain in 2-3 sentences what this is: {query}
Context: {context}
Keep it focused on auto parts/services only.
Be direct and technical in your explanation.""",
            
            "greeting": f"""You are PomBot, the auto parts specialist at PomWorkz workshop.
{query}
Respond with a friendly greeting in 1-2 sentences. Mention you can help with auto parts and services.
If the greeting is in Tagalog, respond in Tagalog.""",
            
            "help": """You are PomBot, the auto parts specialist at PomWorkz workshop.
Generate a helpful response with 4-5 example questions about our products and services.
Include specific examples about prices, services, and product information.""",

            "general": f"""You are PomBot, the auto parts specialist at PomWorkz workshop.
Question: {query}
Context: {context}
Respond in 1-2 sentences, focusing only on auto parts and services.
If the question is unrelated, respond: "I only answer questions about auto parts at PomWorkz."
"""
        }
        
        result = subprocess.run(
            ['ollama', 'run', 'phi', prompts.get(query_type, "")],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"AI Error: {str(e)}")  # For debugging
        return None


def format_products_list():
    """Format products list with prices"""
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


def format_services_list():
    """Format services list with prices"""
    return "\n".join([
        "Available Services at PomWorkz:",
        "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
        "2. Machine Works – Labor: ₱1,000 - ₱3,000",
        "3. Change Oil – Labor: ₱250",
        "4. CVT Cleaning – ₱300",
        "5. Engine Refresh – ₱4,000"
    ])


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' field in request body"}), 400

        user_message = data["message"].lower().strip()

        # Check for bad words first
        if contains_badwords(user_message):
            return jsonify({"response": "Please use respectful language."})

        # Check for creator/identity questions
        if any(q in user_message for q in ["who created you", "who made you", "who is your creator"]):
            return jsonify({"response": "I am created by Cleo Dipasupil."})

        # Handle list requests with static responses (for speed and reliability)
        if any(keyword in user_message for keyword in ["what services", "available services", "list services"]):
            return jsonify({"response": format_services_list()})
        
        if any(keyword in user_message for keyword in ["what products", "available products", "list products"]):
            return jsonify({"response": format_products_list()})

        # Handle "what is" queries with AI
        if "what is" in user_message:
            # Check services first
            for service, price in SERVICES.items():
                if service.replace(" ", "") in user_message.replace(" ", ""):
                    context = f"""Service details:
                    - Name: {service}
                    - Cost: {price}
                    - This is a professional automotive service at PomWorkz"""
                    
                    ai_response = get_ai_response("what_is", service, context)
                    if ai_response:
                        return jsonify({
                            "response": f"{ai_response}\n\nService cost: {price}"
                        })

            # Then check products
            for product, price in PRODUCTS.items():
                if product.replace(" ", "") in user_message.replace(" ", ""):
                    context = f"""Product details:
                    - Name: {product}
                    - Price: ₱{price}
                    - This is an automotive part sold at PomWorkz"""
                    
                    ai_response = get_ai_response("what_is", product, context)
                    if ai_response:
                        return jsonify({
                            "response": f"{ai_response}\n\nPrice: ₱{price}"
                        })

        # Handle greetings with AI
        greetings = ["hi", "hello", "kumusta", "magandang", "good"]
        if any(greeting in user_message for greeting in greetings):
            greeting_response = get_ai_response("greeting", user_message)
            if greeting_response:
                return jsonify({"response": greeting_response})
            return jsonify({
                "response": "Hello! How can I help you with our auto parts and services today?"
            })

        # Handle price queries
        if any(word in user_message for word in ["price", "cost", "how much"]):
            for product, price in PRODUCTS.items():
                if product in user_message:
                    context = f"The price of {product} is ₱{price}"
                    ai_response = get_ai_response("general", user_message, context)
                    if ai_response:
                        return jsonify({"response": ai_response})
                    return jsonify({"response": f"The price of {product.capitalize()} is ₱{price}."})

            for service, price in SERVICES.items():
                if service in user_message:
                    context = f"The cost of {service} is {price}"
                    ai_response = get_ai_response("general", user_message, context)
                    if ai_response:
                        return jsonify({"response": ai_response})
                    return jsonify({"response": f"The cost of {service.capitalize()} is {price}."})

        # Try general AI response for other queries
        ai_response = get_ai_response("general", user_message, KNOWLEDGE_BASE)
        if ai_response:
            return jsonify({"response": ai_response})

        # Default help response with AI
        help_response = get_ai_response("help", "") or """How can I help you? You can ask:
• About specific product prices (e.g., "How much is a camshaft?")
• About service costs (e.g., "What is the cost of CVT cleaning?")
• For product/service information (e.g., "What is engine refresh?")
• To see all available products or services"""
        
        return jsonify({"response": help_response})

    except Exception as e:
        print(f"Error: {str(e)}")  # For debugging
        return jsonify({
            "response": "I apologize, but I'm having trouble processing your request. Please try asking about specific products or services."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 1551))
    app.run(debug=False, host="0.0.0.0", port=port)
