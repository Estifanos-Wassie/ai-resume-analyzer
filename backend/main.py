from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from groq import Groq
from input_validation import validate_inputs
import os
import json

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.get("/")
def home():
    return{"message" : "AI Resume Analyzer is running!"}

@app.get("/health")
def health():
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return {"status": "healthy", "api_key_loaded": True}
    return {"status": "unhealthy", "api_key_loaded": False}


@app.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...)
):
    resume_text, job_description = await validate_inputs(file, job_description)

    prompt = f"""You are an expert technical recruiter and career coach.
Analyze the resume against the job description and return ONLY a JSON object.
No markdown, no explanation — raw JSON only.

Required format:
{{
  "match_score": <integer 0-100>,
  "strengths": ["..."],
  "missing_skills": ["..."],
  "suggestions": ["..."]
}}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a resume analysis assistant. Always respond with valid JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Model returned non-JSON output: {raw[:300]}"
        )

    return result
