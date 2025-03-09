from flask import Blueprint, request, jsonify
import time
import uuid
from utils import create_chain, get_session_history, store_chat_history, get_session_id, get_user_sessions
from routes.auth import verify_jwt_token
from database.models import chat_history_collection
import logging
from bson import ObjectId
import re
from collections import Counter
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import nltk

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

nltk.download("punkt")
nltk.download("stopwords")

def extract_keywords(text, max_keywords=5):
    """Extracts important keywords from the given text."""
    stop_words = set(stopwords.words("english"))
    words = word_tokenize(text.lower())  # Tokenize and convert to lowercase
    words = [word for word in words if word.isalnum() and word not in stop_words]  # Remove punctuation & stopwords
    word_freq = Counter(words)  # Count word frequency
    keywords = [word for word, _ in word_freq.most_common(max_keywords)]  # Pick top keywords
    return " ".join(keywords).title()  # Convert to title case

def generate_ai_response(user_input: str, session_id: str) -> dict:
    """Generate a response using LangChain and store chat history."""
    chain = create_chain()

    start_time = time.time()
    ai_response = chain.invoke(
        {"input": user_input, "session_id": session_id},
        config={"configurable": {"session_id": session_id}}
    )
    end_time = time.time()
    response_time = round(end_time - start_time, 2)

    response_id = str(uuid.uuid4())

    # Store only the message string
    response_id = str(uuid.uuid4())  # Generate unique response_id
    ai_message = {"role": "AI", "message": ai_response, "response_id": response_id, "created_at": time.time()}
    store_chat_history(session_id, user_input, ai_message)


    # Update session title only if it’s still "New Session"
    session = chat_history_collection.find_one({"session_id": session_id})
    if session and session.get("title") == "New Session":
        title = " ".join(user_input.split()[:5]) + "..."  # Use first 5 words as title
        chat_history_collection.update_one(
            {"session_id": session_id},
            {"$set": {"title": title}}
        )

    return {
        "response_id": response_id,
        "message": ai_response,
        "response_time": response_time
    }

@chat_bp.route("/send", methods=["POST"])
def chat():
    """Handles user messages and generates AI responses."""
    data = request.get_json()
    user_input = data.get("message", "")
    if not user_input:
        return jsonify({"error": "Message content required"}), 400

    session_id = get_session_id()
    if not session_id:
        return jsonify({"error": "Invalid session or token"}), 401

    response_data = generate_ai_response(user_input, session_id)

    # Fetch updated session title to return it in response
    session = chat_history_collection.find_one({"session_id": session_id})
    session_title = session.get("title", "New Session") if session else "New Session"

    return jsonify({
        **response_data,
        "session_title": session_title
    }), 200

@chat_bp.route("/history", methods=["GET"])
def chat_history():
    """Fetches the chat history of a specific session."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400

    try:
        session = chat_history_collection.find_one({"session_id": session_id, "user_id": ObjectId(user_id)})
        if not session:
            return jsonify({"error": "Session not found or access denied"}), 403

        history = session.get("messages", [])
        return jsonify({"history": history, "title": session.get("title", "New Session")}), 200
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route("/save_session", methods=["POST"])
def save_session():
    """Saves the session with a dynamic title, preserving the first title from /send if set."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    session_id = get_session_id()
    if not session_id:
        return jsonify({"error": "Invalid session"}), 400

    try:
        session = chat_history_collection.find_one({"session_id": session_id, "user_id": ObjectId(user_id)})
        if not session:
            return jsonify({"error": "Session not found"}), 404

        current_title = session.get("title", "New Session")
        messages = session.get("messages", [])
        title = current_title  # Default to current title

        # Only generate a new title if the current title is "New Session"
        if current_title == "New Session" and messages:
            # Find the first response from AIRA
            for msg in messages:
                if msg.get("sender") == "AIRA":
                    first_response = msg["message"]
                    title = extract_keywords(first_response)
                    break  # Stop once we get the first AIRA response
            # If no AIRA response found, keep it as "New Session" or use user input
            if title == "New Session" and messages:
                title = " ".join(messages[0]["message"].split()[:5]) + "..."  # Fallback to first user message

        # Update the title only if it’s different
        if title != current_title:
            chat_history_collection.update_one(
                {"session_id": session_id},
                {"$set": {"title": title}}
            )
            logger.info(f"Session {session_id} saved with updated title: {title}")
        else:
            logger.info(f"Session {session_id} retained existing title: {title}")

        return jsonify({"message": "Session saved successfully", "title": title}), 200
    except Exception as e:
        logger.error(f"Error saving session: {e}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route("/sessions", methods=["GET"])
def get_sessions():
    """Fetches all past chat sessions of the user."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    sessions = get_user_sessions(user_id)
    return jsonify({"sessions": sessions}), 200
