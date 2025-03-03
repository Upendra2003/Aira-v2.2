from flask import Blueprint, request, jsonify
import datetime
from auth import verify_jwt_token

assessment_bp = Blueprint("assessment", __name__, url_prefix="/api/assessment")

# Define different question sets
QUESTION_SETS = {
    "lonely": [
        "Do you feel disconnected from people around you?",
        "Do you often find yourself feeling alone even in a crowd?",
        "How often do you avoid social interactions?"
    ],
    "depressed": [
        "Do you feel persistent sadness or hopelessness?",
        "Do you have trouble sleeping or experience fatigue frequently?",
        "Have you lost interest in activities you once enjoyed?"
    ],
    "anxious": [
        "Do you often feel restless or nervous?",
        "Do you experience frequent worry or fear about everyday situations?",
        "Do you have trouble concentrating due to anxious thoughts?"
    ]
}

# Store temporary assessments
ongoing_assessments = {}  # {user_id: {"category": "lonely", "answers": [...], "timestamp": datetime}}

SESSION_EXPIRY_MINUTES = 10  # Expire sessions after 10 minutes

def cleanup_expired_sessions():
    """Remove expired sessions based on SESSION_EXPIRY_MINUTES."""
    now = datetime.datetime.utcnow()
    expired_users = [
        user_id for user_id, data in ongoing_assessments.items()
        if (now - data["timestamp"]).total_seconds() > SESSION_EXPIRY_MINUTES * 60
    ]
    for user_id in expired_users:
        del ongoing_assessments[user_id]

def calculate_score(answers):
    """Calculate the user's stress level based on their responses."""
    total = sum(answers)
    if total < 5:
        level = "Low Stress"
    elif total < 10:
        level = "Moderate Stress"
    else:
        level = "High Stress"
    return total, level

@assessment_bp.route("/start", methods=["POST"])
def start_assessment():
    """Start the assessment and ask the first question."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized access"}), 401

    # Cleanup expired sessions
    cleanup_expired_sessions()

    # First question
    first_question = "Which of these best describes your current state? (lonely, depressed, anxious)"
    
    # Start a new assessment session
    ongoing_assessments[user_id] = {"category": None, "answers": [], "timestamp": datetime.datetime.utcnow()}

    return jsonify({"question": first_question, "info": "Please type one of: lonely, depressed, anxious"}), 200

@assessment_bp.route("/next", methods=["POST"])
def next_question():
    """Process the user's answer and provide the next question."""
    data = request.json
    user_id = verify_jwt_token(request)
    answer = data.get("answer")

    if not user_id or answer is None:
        return jsonify({"error": "Invalid request. Ensure user is authenticated and answer is provided."}), 400

    # Cleanup expired sessions
    cleanup_expired_sessions()

    # Fetch user session
    if user_id not in ongoing_assessments:
        return jsonify({"error": "Session expired or assessment not started. Please restart."}), 400

    user_data = ongoing_assessments[user_id]

    # If category is not set, determine category based on first answer
    if user_data["category"] is None:
        category = answer.lower()
        if category not in QUESTION_SETS:
            return jsonify({"error": "Invalid category. Choose from lonely, depressed, or anxious."}), 400
        
        user_data["category"] = category
        user_data["answers"] = []
        user_data["timestamp"] = datetime.datetime.utcnow()  # Update session timestamp

        return jsonify({"question": QUESTION_SETS[category][0]}), 200
    
    # Store the user's score (assuming answer is a numeric value from 0-5)
    try:
        score = int(answer)
        if not (0 <= score <= 5):
            return jsonify({"error": "Score must be between 0 and 5."}), 400
        user_data["answers"].append(score)
        user_data["timestamp"] = datetime.datetime.utcnow()  # Update session timestamp
    except ValueError:
        return jsonify({"error": "Invalid response format. Answer should be a number (0-5)."}), 400

    # Check if more questions are left
    category_questions = QUESTION_SETS[user_data["category"]]
    if len(user_data["answers"]) < len(category_questions):
        next_q = category_questions[len(user_data["answers"])]
        return jsonify({"question": next_q}), 200

    # Calculate score when all questions are answered
    score, level = calculate_score(user_data["answers"])

    # Store final result
    result = {
        "user_id": user_id,
        "category": user_data["category"],
        "score": score,
        "level": level,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    # Remove session after completion
    del ongoing_assessments[user_id]

    return jsonify(result), 200
