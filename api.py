from fastapi import FastAPI
from pydantic import BaseModel
import config
from query import load_index, retrieve
from generate import generate_grounded_answer

app = FastAPI(
    title="THE DOCTOR - Medical RAG API",
    description="Medical RAG API for grounded answers from indexed medical guidelines.",
    version="1.0.0",
)


class QuestionRequest(BaseModel):
    question: str


# Load the vector database once when the API starts
vectordb = load_index()


@app.get("/")
def root():
    return {
        "message": "THE DOCTOR Medical RAG API is running",
        "status": "ok",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "ChromaDB",
        "model": config.GEMINI_MODEL,
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    question = request.question.strip()

    if not question:
        return {
            "recommendation": "Please provide a medical question.",
            "evidence": "",
            "citations": [],
            "confidence": "insufficient",
        }

    # Step 1: Retrieve relevant chunks
    results = retrieve(vectordb, question, config.TOP_K)

    # Step 2: Generate grounded answer using Gemini
    answer = generate_grounded_answer(question, results)

    return answer

