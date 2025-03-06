from flask import Blueprint, request, jsonify
import time
import uuid
from utils import create_chain, get_session_history, store_chat_history, get_session_id, get_user_sessions
from routes.auth import verify_jwt_token
from database.models import chat_history_collection
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

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
    store_chat_history(session_id, user_input, ai_response)

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
    return jsonify(response_data), 200

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
        return jsonify({"history": history}), 200
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route("/save_session", methods=["POST"])
def save_session():
    """Saves the session with a dynamic title based on the first message."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    session_id = get_session_id()
    print(session_id)
    if not session_id:
        return jsonify({"error": "Invalid session"}), 400

    try:
        session = chat_history_collection.find_one({"session_id": session_id, "user_id": ObjectId(user_id)})
        if not session:
            return jsonify({"error": "Session not found"}), 404

        messages = session.get("messages", [])
        title = "Empty Session"
        if messages:
            first_message = messages[0]["message"]
            title = " ".join(first_message.split()[:5]) + "..."

        chat_history_collection.update_one(
            {"session_id": session_id},
            {"$set": {"title": title}}
        )
        logger.info(f"Session {session_id} saved with title: {title}")
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