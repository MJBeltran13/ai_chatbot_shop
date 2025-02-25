from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json

app = FastAPI()

# Sample shop pricing data
shop_pricing = {
    "laptop": 50000,
    "headphones": 2000,
    "smartphone": 30000,
    "keyboard": 1500,
}

# Allowed shop-related keywords
shop_keywords = {"price", "buy", "order", "product", "cost", "shop", "available"}


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.post("/chat")
def chat(request: ChatRequest):
    message = request.message.lower()

    # Restrict to shop-related topics
    if not any(word in message for word in shop_keywords):
        return {
            "response": "I only answer questions related to our shop. How can I assist you with our products?"
        }

    # Handle product pricing queries with flexible matching
    for product in shop_pricing:
        if product in message or product.rstrip("s") in message:
            return {
                "response": f"The price of {product.capitalize()} is PHP {shop_pricing[product]:,}."
            }

    # Run Ollama inference
    try:
        result = subprocess.run(
            ["ollama", "run", "qwen2.5:0.5b", message], capture_output=True, text=True
        )
        response_text = result.stdout.strip()
    except Exception as e:
        response_text = "Error processing your request. Please try again later."

    return {"response": response_text}
