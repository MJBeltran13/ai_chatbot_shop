import ollama


def chat_with_pamsworkz():
    print("Welcome to PamsWorkz Chatbot! (Type 'exit' to quit)")

    system_prompt = """You are PamsWorkz, an AI assistant for an auto parts shop.
    
    PamsWorkz specializes in:
    - Wheels ($1000 each)
    - Tires ($2000 each)
    - Headlights ($3000 each)
    
    🔴 STRICT RULES:
    - ❌ Do NOT answer any questions that are NOT about PamsWorkz.
    - ❌ Do NOT tell jokes, stories, riddles, or anything unrelated.
    - ✅ If a user asks something off-topic, say: 'I only provide information about PamsWorkz products.'
    """

    conversation = [{"role": "system", "content": system_prompt}]

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye! Visit PamsWorkz for the best deals on auto parts!")
            break

        conversation.append({"role": "user", "content": user_input})

        # Generate a response
        response = ollama.chat(model="qwen2.5:0.5b", messages=conversation)

        # Extract and print the response
        bot_reply = response["message"]["content"]

        # Prevent unwanted responses (failsafe)
        if "joke" in user_input.lower() or "funny" in user_input.lower():
            bot_reply = "I only provide information about PamsWorkz products."

        print(f"PamsWorkz: {bot_reply}")

        # Append bot response to maintain context
        conversation.append({"role": "assistant", "content": bot_reply})


if __name__ == "__main__":
    chat_with_pamsworkz()
