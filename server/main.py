from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
import re

openai.api_key = "YOUR_KEY_HERE"
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "MeetMind is working!"}

def clean_transcript(text):
    fillers = r'\b(um|uh|like|you know|basically|literally|actually|so yeah|i mean)\b'
    text = re.sub(fillers, '', text, flags=re.IGNORECASE)
    text = re.sub(r' +', ' ', text).strip()
    return text

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await file.read()
    with open("temp_audio.mp3", "wb") as f:
        f.write(audio)
    with open("temp_audio.mp3", "rb") as f:
        result = openai.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    raw_transcript = result.text
    clean = clean_transcript(raw_transcript)
    os.remove("temp_audio.mp3")
    return {
        "raw_transcript": raw_transcript,
        "clean_transcript": clean
    }