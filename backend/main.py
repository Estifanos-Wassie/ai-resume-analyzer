from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

@app.get("/")
def home():
    return{"message" : "AI Resume Analyzer is running!"}

@app.get("/health")
def health():
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return {"status": "healthy", "api_key_loaded": True}
    return {"status": "unhealthy", "api_key_loaded": False}