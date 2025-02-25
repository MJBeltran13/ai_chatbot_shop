import ollama


def chat_with_pamsworkz():
    print("Welcome to PamsWorkz Chatbot! (Type 'exit' to quit)")

    system_prompt = """You are the AI assistant for PamsWorkz, a store specializing in automotive parts, you are created by Cleo Dipasupil and party.

    📌 PamsWorkz Products and Prices:
    
    - **Wheels**:
        - Brand A (17-inch): $1000 each
        - Brand A (18-inch): $1200 each
        - Brand B (17-inch): $1100 each
        - Brand B (18-inch): $1300 each
    
    - **Tires**:
        - Brand X (Standard 15-inch): $2000 each
        - Brand X (Premium 17-inch): $2500 each
        - Brand Y (Standard 15-inch): $2200 each
        - Brand Y (Off-Road 17-inch): $2700 each
    
    - **Headlights**:
        - LED Headlights: $3000 each
        - Xenon Headlights: $3500 each
        - Halogen Headlights: $2000 each

    📦 Product Descriptions:
    - **Wheels**: Durable alloy wheels available in 17-inch and 18-inch sizes, perfect for high-performance driving.
    - **Tires**: High-traction tires available in standard, premium, and off-road variants.
    - **Headlights**: Bright LED, Xenon, and Halogen headlights for enhanced visibility.

    ❌ STRICT RULES ❌
    - Only discuss PamsWorkz products and their prices.
    - Never provide off-topic details (e.g., installation, brands outside PamsWorkz, or warranty info).
    - If asked about services, discounts, or non-PamsWorkz products, respond with: 'PamsWorkz specializes in selling wheels, tires, and headlights.'
    - Always provide detailed product information when asked about a specific product.
    """

    conversation = [{"role": "system", "content": system_prompt}]

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye! Visit PamsWorkz for the best deals on auto parts!")
            break

        conversation.append({"role": "user", "content": user_input})

        response = ollama.chat(model="pamsworkz", messages=conversation)
        bot_reply = response["message"]["content"]

        # 🚨 Strict Response Enforcement
        if "service" in user_input.lower():
            bot_reply = (
                "PamsWorkz specializes in selling wheels, tires, and headlights."
            )
        elif "product" in user_input.lower() or "available" in user_input.lower():
            bot_reply = (
                "PamsWorkz offers:\n"
                "- Wheels (17-inch & 18-inch) from $1000 to $1300.\n"
                "- Tires (15-inch & 17-inch) from $2000 to $2700.\n"
                "- Headlights (LED, Xenon, Halogen) from $2000 to $3500."
            )
        elif "wheel" in user_input.lower():
            bot_reply = (
                "PamsWorkz offers:\n"
                "- Brand A (17-inch): $1000\n"
                "- Brand A (18-inch): $1200\n"
                "- Brand B (17-inch): $1100\n"
                "- Brand B (18-inch): $1300"
            )
        elif "tire" in user_input.lower():
            bot_reply = (
                "PamsWorkz provides:\n"
                "- Brand X (15-inch Standard): $2000\n"
                "- Brand X (17-inch Premium): $2500\n"
                "- Brand Y (15-inch Standard): $2200\n"
                "- Brand Y (17-inch Off-Road): $2700"
            )
        elif "headlight" in user_input.lower():
            bot_reply = (
                "PamsWorkz sells:\n"
                "- LED Headlights: $3000\n"
                "- Xenon Headlights: $3500\n"
                "- Halogen Headlights: $2000"
            )
        elif "discount" in user_input.lower() or "bulk" in user_input.lower():
            bot_reply = (
                "PamsWorkz specializes in selling wheels, tires, and headlights."
            )
        elif (
            "sorry" in bot_reply.lower()
            or "don’t have detailed information" in bot_reply.lower()
        ):
            bot_reply = "PamsWorkz offers wheels, tires, and headlights in various sizes and brands. Ask for specific pricing!"

        print(f"PamsWorkz: {bot_reply}")

        conversation.append({"role": "assistant", "content": bot_reply})


if __name__ == "__main__":
    chat_with_pamsworkz()
