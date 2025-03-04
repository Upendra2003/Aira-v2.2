import time
import gc
import logging
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableMap
from config import GROQ_API_KEY
from config import JWT_SECRET_KEY
from flask import request
import jwt

logger = logging.getLogger(__name__)

# Lazy-loaded globals
model = None
embedding_model = None
retriever = None
session_cache = {}

# Define system prompt and prompt template
system_prompt = """🌿 You are AIRA, an AI therapist dedicated to supporting individuals in their emotional well-being and mental health. Your role is to provide a safe, supportive, and judgment-free space for users to express their concerns. 🤗💙

📝 Guidelines:
✅ Maintain Context: Remember and reference relevant details from previous messages. 🧠💡
✅ Stay Engaged: Keep track of the conversation flow and respond accordingly. 🔄💬
✅ Be Clear & Concise: Use direct, to-the-point responses while maintaining warmth and empathy. ❤️✨
✅ Use Natural Language: Prioritize easy-to-understand language while ensuring depth and professionalism. 🗣️📖
✅ Encourage Professional Help When Necessary: If a user's concern requires medical attention, gently suggest seeking professional help. 🏥💙
✅ Use Emojis Thoughtfully: Incorporate emojis 😊💖 when appropriate to build an emotional connection with the user and make the conversation feel more engaging and supportive.

🚧 Boundaries:
🚫 If users ask about unrelated topics (e.g., movies 🎬, anime 🎭, games 🎮, general queries 🌍, etc.) or anything outside of mental health, kindly inform them that you are designed solely for mental health support. 🧘‍♂️💙"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}")
])

output_parser = StrOutputParser()

def get_model():
    """Lazy load the Groq LLM model."""
    global model
    if model is None:
        logger.info("Initializing Groq LLM model")
        model = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="Llama3-8b-8192")
    return model

def get_embedding_model():
    """Lazy load the HuggingFace embedding model."""
    global embedding_model
    if embedding_model is None:
        logger.info("Initializing embedding model")
        embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return embedding_model

def get_retriever():
    """Lazy load the FAISS retriever."""
    global retriever
    if retriever is None:
        logger.info("Initializing FAISS retriever")
        embeddings = get_embedding_model()
        vector_store = FAISS.load_local(
            "faiss_therapist_replies",
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 2})
    return retriever

def format_retrieved(docs):
    """Format retrieved documents into a single string."""
    return " ".join([doc.page_content.replace("\n", " ") for doc in docs if hasattr(doc, "page_content")])

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """Get chat history for a session, with caching."""
    from database.models import chat_history_collection  # local import to avoid circular dependency
    if session_id in session_cache:
        cache_time, history = session_cache[session_id]
        if time.time() - cache_time < 300:  # 5 minutes cache
            return history

    history = ChatMessageHistory()
    try:
        session = chat_history_collection.find_one({"session_id": session_id})
        if session:
            for msg in session.get("messages", []):
                if msg["role"] == "user":
                    history.add_user_message(msg["message"])
                else:
                    history.add_ai_message(msg["message"])
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")

    session_cache[session_id] = (time.time(), history)
    clean_session_cache()
    return history

def clean_session_cache():
    """Remove old sessions from cache."""
    current_time = time.time()
    expired_sessions = [sid for sid, (timestamp, _) in session_cache.items() if current_time - timestamp > 600]
    for sid in expired_sessions:
        del session_cache[sid]

def create_chain():
    """Create the LangChain chain on demand."""
    return RunnableWithMessageHistory(
        RunnableMap({
            "context": lambda x: format_retrieved(get_retriever().invoke(x["input"])),
            "input": lambda x: x["input"],
            "chat_history": lambda x: [msg.content for msg in get_session_history(x["session_id"]).messages],
        })
        | prompt
        | get_model()
        | output_parser,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history"
    )

def store_chat_history(session_id, user_input, ai_response):
    """Store chat history in MongoDB."""
    from database.models import chat_history_collection
    try:
        chat_history_collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": {"$each": [
                {"role": "user", "message": user_input},
                {"role": "AI", "message": ai_response}
            ]}}},
            upsert=True
        )
        if session_id in session_cache:
            _, history = session_cache[session_id]
            history.add_user_message(user_input)
            history.add_ai_message(ai_response)
            session_cache[session_id] = (time.time(), history)
    except Exception as e:
        logger.error(f"Error storing chat history: {e}")

def get_session_id():
    """Extracts session_id from request or generates a new one."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    try:
        token = auth_header.split(" ")[1]  # Extract token from "Bearer <JWT>"
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        # Generate session_id using user_id
        return f"session_{user_id}"
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None