from flask import Blueprint, request, jsonify
import time
from models import get_database, initialize_collections
from auth import verify_jwt_token  
from utils import get_session_id

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")

def get_feedback_collections():
    """Retrieve feedback collections dynamically."""
    db = get_database()
    return db["feedback_responses"], db["daily_feedback"]

@feedback_bp.route("/submit", methods=["POST"])
def submit_feedback():
    """Submit structured feedback for chatbot responses."""
    feedback_collection, _ = get_feedback_collections()

    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.json
    session_id = get_session_id()
    response_id = data.get("response_id")
    feedback_type = data.get("feedback_type")

    if not session_id or not response_id or feedback_type not in ["like", "dislike"]:
        return jsonify({"error": "Invalid feedback data."}), 400

    # Find user feedback history or create new
    user_feedback = feedback_collection.find_one({"user_id": user_id, "session_id": session_id})

    new_feedback = {
        "response_id": response_id,
        "feedback_type": feedback_type,
        "timestamp": time.time()
    }

    if user_feedback:
        feedback_collection.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$push": {"feedbacks": new_feedback}}
        )
    else:
        feedback_collection.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "feedbacks": [new_feedback]
        })

    return jsonify({"message": "Feedback recorded successfully"}), 200


@feedback_bp.route("/daily_feedback", methods=["POST"])
def submit_daily_feedback():
    """Users provide overall experience feedback at the end of the day."""
    _, daily_feedback_collection = get_feedback_collections()

    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.json
    session_id = get_session_id()
    rating = data.get("rating")
    comment = data.get("comment", "")

    if not session_id or rating is None:
        return jsonify({"error": "Invalid data. 'rating' is required."}), 400

    if not isinstance(rating, (int, float)) or not (1 <= rating <= 5):
        return jsonify({"error": "Rating must be between 1 and 5."}), 400

    daily_feedback_collection.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "rating": rating,
        "comment": comment,
        "timestamp": time.time()
    })

    return jsonify({"message": "Daily experience feedback submitted successfully"}), 200
