import re
import subprocess
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

KNOWLEDGE_BASE = """
You are PamsBot, the auto parts specialist at PamsWorkz workshop.
You ONLY answer questions about the products and pricing listed below.
You are created by Cleo Dipasupil.
You can respond in English or Tagalog.

❌ DO NOT answer any question that is NOT related to the products below.  
✅ If asked anything else, reply: "I only answer questions about auto parts at PamsWorkz."  

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
- ✅ **For unrelated questions, reply: "I only answer questions about auto parts at PamsWorkz."**
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


def get_ai_explanation(query, context):
    try:
        prompt = f"""You are PamsBot, the auto parts specialist at PamsWorkz workshop. 
Explain this query in 2-3 sentences: {query}
Context: {context}
Keep it simple and focused on auto parts/services only."""
        
        result = subprocess.run(
            ['ollama', 'run', 'phi', prompt],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return None


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' field in request body"}), 400

        user_message = data["message"].lower()

        # Handle "what is" queries
        if "what is" in user_message:
            # Check for services first
            for service, price in SERVICES.items():
                if service in user_message:
                    context = f"This is a service offered at PamsWorkz. The cost is {price}."
                    ai_response = get_ai_explanation(service, context)
                    if ai_response:
                        return jsonify({
                            "response": f"{ai_response}\nThe cost for this service is {price}."
                        })

            # Check for products
            for product, price in PRODUCTS.items():
                if product in user_message:
                    context = f"This is a product sold at PamsWorkz. The price is ₱{price}."
                    ai_response = get_ai_explanation(product, context)
                    if ai_response:
                        return jsonify({
                            "response": f"{ai_response}\nThe price is ₱{price}."
                        })

        # Check for service list requests
        if any(keyword in user_message for keyword in ["what services", "available services", "list services", "services available"]):
            services_list = "\n".join([
                "Available Services at PamsWorkz:",
                "1. Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000",
                "2. Machine Works – Labor: ₱1,000 - ₱3,000",
                "3. Change Oil – Labor: ₱250",
                "4. CVT Cleaning – ₱300",
                "5. Engine Refresh – ₱4,000"
            ])
            return jsonify({"response": services_list})

        # Check for product list requests
        if any(keyword in user_message for keyword in ["what products", "available products", "list products", "products available"]):
            products_list = "\n".join([
                "Available Products at PamsWorkz:",
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
            return jsonify({"response": products_list})

        # Check for bad words
        if contains_badwords(user_message):
            return jsonify({"response": "Please use respectful language."})

        # Check for product prices (fast response)
        for product, price in PRODUCTS.items():
            if product in user_message:
                return jsonify(
                    {"response": f"The price of {product.capitalize()} is ₱{price}."}
                )

        # Check for service prices (fast response)
        for service, price in SERVICES.items():
            if service in user_message:
                return jsonify(
                    {"response": f"The cost of {service.capitalize()} is {price}."}
                )

        # For greetings
        greetings = ["hi", "hello", "kumusta", "magandang", "good"]
        if any(greeting in user_message for greeting in greetings):
            return jsonify({
                "response": "Hello! How can I help you today? I can provide prices for our auto parts and services."
            })

        # Default response for unknown queries
        return jsonify({
            "response": "How can I help you? You can ask about:\n1. Specific product prices\n2. Service costs\n3. List of available products\n4. List of available services"
        })

    except Exception as e:
        return jsonify({
            "response": "I apologize, but I'm having trouble processing your request. Please try asking about specific products or services."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 1551))
    app.run(debug=False, host="0.0.0.0", port=port)
