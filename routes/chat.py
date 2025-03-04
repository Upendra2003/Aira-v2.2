from flask import Blueprint, request, jsonify
import time
import gc
import jwt
from utils import create_chain, get_session_history, store_chat_history
from routes.auth import verify_jwt_token
from utils import get_session_id
import uuid

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


import uuid  
import time  # Import time module

def generate_ai_response(user_input, session_id):
    """Generate a response using LangChain and store chat history."""
    chain = create_chain()
    
    # Start timing the response generation
    start_time = time.time()

    # Generate AI response
    ai_response = chain.invoke(
        {"input": user_input, "session_id": session_id},
        config={"configurable": {"session_id": session_id}}
    )

    # End timing
    end_time = time.time()
    response_time = round(end_time - start_time, 2)  # Round to 2 decimal places

    # Generate a unique response_id
    response_id = str(uuid.uuid4())

    # Store chat history with response_id and response_time
    store_chat_history(session_id, user_input, {
        "response_id": response_id, 
        "message": ai_response, 
        "response_time": response_time
    })
    
    return {
        "response_id": response_id,
        "message": ai_response,
        "response_time": response_time  # Include response time
    }


@chat_bp.route("/send", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")
    if not user_input:
        return jsonify({"error": "Message content required"}), 400

    session_id = get_session_id()  # Extract session_id from the token
    if not session_id:
        return jsonify({"error": "Invalid session or token"}), 401

    response_data = generate_ai_response(user_input, session_id)

    return jsonify(response_data)  # Now includes response_id & response_time



@chat_bp.route("/history", methods=["GET"])
def chat_history():
    user_id = verify_jwt_token(request)
    print("Extracted user_id:", user_id)  # Debug line

    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    session_id = request.args.get("session_id", f"session_{user_id}")
    try:
        chat_history_obj = get_session_history(session_id)
        if hasattr(chat_history_obj, "user_id") and chat_history_obj.user_id != user_id:
            return jsonify({"error": "Access denied. Invalid session ID."}), 403

        history = [
            {"role": "user", "message": msg.content} if msg.type == "human" 
            else {"role": "AI", "message": msg.content} 
            for msg in chat_history_obj.messages
        ]
        return jsonify({"history": history}), 200
    except Exception as e:
        return jsonify({"error": f"Error retrieving chat history: {str(e)}"}), 500

