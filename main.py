from fastapi import FastAPI
from pydantic import BaseModel
from rag_pipeline import get_rag_response

app = FastAPI(
    title="RAG API",
    description="A simple RAG API for Postman testing.",
    version="1.0",
    docs_url=None,  # Disable Swagger UI
    redoc_url=None,  # Disable ReDoc
)


class QueryRequest(BaseModel):
    question: str


@app.post("/ask")
def ask_question(request: QueryRequest):
    """Handles user queries from Postman"""
    response = get_rag_response(request.question)
    return {"answer": response}
