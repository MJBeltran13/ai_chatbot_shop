import os
import re
from flask import Flask, request, jsonify
import subprocess

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
CVT Cleaner - ₱00
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


# 🔹 Extract product prices and stock dynamically
def get_product_details():
    product_prices = {}
    stock_info = {}

    # Extract product names, prices, and stock
    product_pattern = re.findall(
        r"- (.+?): \$([\d]+) each(?: \((.+?)\))?", KNOWLEDGE_BASE
    )

    for product, price, stock in product_pattern:
        product_prices[product.lower()] = int(price)
        if stock:
            stock_info[product.lower()] = stock  # Store stock info if available

    return product_prices, stock_info


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' field in request body"}), 400

        user_message = data["message"].lower()
        product_prices, stock_info = get_product_details()

        # # 🔹 Check if the user is asking for all products
        # if any(
        #     word in user_message
        #     for word in ["all products", "full catalog", "list of products"]
        # ):
        #     response = "Here is the full product list:\n"
        #     for product, price in product_prices.items():
        #         stock_text = (
        #             f" ({stock_info[product]})" if product in stock_info else ""
        #         )
        #         response += f"- {product}: ${price} each{stock_text}\n"
        #     return jsonify({"response": response.strip()})

        # # 🔹 Extract product name & quantity using regex
        # quantity_match = re.search(r"(\d+)", user_message)  # Extract quantity
        # quantity = int(quantity_match.group(1)) if quantity_match else 1  # Default to 1

        # matched_product = None
        # for product in product_prices:
        #     if product in user_message:
        #         matched_product = product
        #         break

        # # 🔹 If product found, return its price
        # if matched_product:
        #     unit_price = product_prices[matched_product]
        #     total_price = unit_price * quantity
        #     response = f"The price of {matched_product} is ${unit_price} each."

        #     # 🔹 Add stock availability if it exists
        #     if matched_product in stock_info:
        #         response += f" {stock_info[matched_product]}."

        #     response += f" The total price for {quantity} is ${total_price}."
        #     return jsonify({"response": response})

        # 🔹 If no product matched, use Ollama to generate response
        prompt = f"{KNOWLEDGE_BASE}\nUser: {user_message}\nAssistant:"
        ollama_cmd = ["ollama", "run", "mistral", prompt]
        result = subprocess.run(
            ollama_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        response = result.stdout.strip()

        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
