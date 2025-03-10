from flask import Blueprint, request, jsonify
from datetime import datetime
from database.models import get_database
from routes.auth import verify_jwt_token  
from utils import get_session_id
import logging

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")
logger = logging.getLogger(__name__)

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
    comment = data.get("comment", "")

    if not session_id or not response_id or feedback_type not in ["like", "dislike"]:
        return jsonify({"error": "Invalid feedback data", 
                        "details": "session_id, response_id, and feedback_type ('like' or 'dislike') are required."}), 400

    if feedback_type == "dislike" and not comment.strip():
        return jsonify({"error": "Comment required", 
                        "details": "A comment is required when submitting a 'dislike' feedback."}), 400

    new_feedback = {
        "response_id": response_id,
        "feedback_type": feedback_type,
        "comment": comment,
        "timestamp": datetime.utcnow()
    }

    try:
        # Check if feedback for this response_id already exists
        existing_feedback = feedback_collection.find_one(
            {"user_id": user_id, "session_id": session_id, "feedbacks.response_id": response_id},
            {"feedbacks.$": 1}  # Projection to fetch only matching feedback
        )

        if existing_feedback:
            # Update existing feedback entry
            feedback_collection.update_one(
                {"user_id": user_id, "session_id": session_id, "feedbacks.response_id": response_id},
                {"$set": {"feedbacks.$": new_feedback}}
            )
        else:
            # Append if no feedback exists for this response_id
            feedback_collection.update_one(
                {"user_id": user_id, "session_id": session_id},
                {"$push": {"feedbacks": new_feedback}},
                upsert=True  # Create a new document if user_id + session_id doesn't exist
            )

        logger.info(f"Feedback updated by user {user_id} for session {session_id}, response {response_id}")

    except Exception as e:
        logger.error(f"Database error while submitting feedback: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500

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
        return jsonify({"error": "Invalid data", "details": "'session_id' and 'rating' are required."}), 400

    if not isinstance(rating, (int, float)) or not (1 <= rating <= 5):
        return jsonify({"error": "Invalid rating", "details": "Rating must be a number between 1 and 5."}), 400

    try:
        daily_feedback_collection.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.utcnow()
        })
        logger.info(f"Daily feedback submitted by user {user_id} for session {session_id}")
    except Exception as e:
        logger.error(f"Database error while submitting daily feedback: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500

    return jsonify({"message": "Daily experience feedback submitted successfully"}), 200