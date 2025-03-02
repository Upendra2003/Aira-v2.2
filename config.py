import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_CONNECTION_STRING")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
PORT = int(os.getenv("PORT", 5000))
print(f"🔍 Loaded MONGO_URI: {MONGO_URI}")
