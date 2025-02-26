from langchain_community.vectorstores import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import re

# Load documents with UTF-8 encoding to prevent decoding errors
loader = TextLoader("knowledge_base.txt", encoding="utf-8")
documents = loader.load()

# Split text into chunks for better retrieval
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
texts = text_splitter.split_documents(documents)

# Use Ollama embeddings for vector search
embedding_model = OllamaEmbeddings(model="qwen2.5:0.5b")

# Store embeddings in ChromaDB
vector_store = Chroma.from_documents(texts, embedding_model)

# Create a retriever with a maximum of 2 results
retriever = vector_store.as_retriever(search_kwargs={"k": 2})


def clean_response(text):
    """Format retrieved information for better readability."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Remove markdown bold
    text = re.sub(r"📌", "\n", text)  # Replace emoji bullets
    text = re.sub(r"\n\s*-\s*", "\n- ", text)  # Fix bullet points
    return text.strip()


def get_rag_response(question: str):
    """Retrieve relevant information and clean the output"""
    docs = retriever.invoke(question)

    # If no relevant documents are found, return a friendly response
    if not docs:
        return {
            "status": "error",
            "message": "I couldn't find relevant information for your question.",
        }

    # Get the most relevant document
    most_relevant_doc = docs[0].page_content

    # Define words related to automotive products
    keywords = [
        "wheels",
        "tires",
        "headlights",
        "PamsWorkz",
        "prices",
        "automotive",
        "store",
    ]

    # Check if query contains relevant keywords
    if not any(keyword in question.lower() for keyword in keywords):
        return {
            "status": "error",
            "message": "I couldn't find relevant information for your question.",
        }

    # Return cleaned response if relevant
    return {"status": "success", "info": clean_response(most_relevant_doc)}
