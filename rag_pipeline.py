from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import TextLoader


# Load documents
loader = TextLoader("knowledge_base.txt")
documents = loader.load()

# Split text into chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
texts = text_splitter.split_documents(documents)

# Use Ollama embeddings
embedding_model = OllamaEmbeddings(model="qwen2.5:0.5b")

# Store embeddings in ChromaDB
vector_store = Chroma.from_documents(texts, embedding_model)

# Create retriever
retriever = vector_store.as_retriever()


def get_rag_response(question: str):
    """Retrieve relevant information and generate a response"""
    docs = retriever.get_relevant_documents(question)
    if docs:
        context = "\n".join([doc.page_content for doc in docs])
        return f"Retrieved Info: {context}"
    return "No relevant information found."
