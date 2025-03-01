from flask import Blueprint, request, jsonify
import datetime

assessment_bp = Blueprint("assessment", __name__, url_prefix="/api/assessment")

# For demonstration, we use a dummy scoring function.
def calculate_score(answers):
    # Assume answers is a list of numeric values
    total = sum(answers)
    if total < 10:
        level = "Low Stress"
    elif total < 20:
        level = "Moderate Stress"
    else:
        level = "High Stress"
    return total, level

@assessment_bp.route("/submit", methods=["POST"])
def submit_assessment():
    data = request.json
    user_id = data.get("user_id")
    answers = data.get("answers")
    if not user_id or not answers or not isinstance(answers, list):
        return jsonify({"error": "Invalid data provided"}), 400
    score, level = calculate_score(answers)
    # Here you might store the assessment in a collection.
    result = {
        "user_id": user_id,
        "score": score,
        "level": level,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    return jsonify(result), 200

@assessment_bp.route("/score", methods=["GET"])
def get_score():
    # For demo, return a static response.
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    result = {
        "user_id": user_id,
        "score": 15,
        "level": "Moderate Stress",
        "last_updated": datetime.datetime.utcnow().isoformat()
    }
    return jsonify(result), 200
