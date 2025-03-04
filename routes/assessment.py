from flask import Blueprint, request, jsonify
import datetime
from routes.auth import verify_jwt_token
from database.models import question_collection  #Import question_collection

assessment_bp = Blueprint("assessment", __name__, url_prefix="/api/assessment")

# Store temporary assessments
ongoing_assessments = {}  # {user_id: {"category": "lonely", "question_ids": [], "answers": [], "timestamp": datetime}}

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

def calculate_score(answers, question_ids):
    """Calculate the user's score based on their responses."""
    total_score = 0
    for question_id, answer in zip(question_ids, answers):
        # Fetch the question from the database to get scores
        question = question_collection.find_one({"_id": question_id})
        if not question:
            print(f"Warning: Question not found in DB: {question_id}") #Log this, don't expose to user.
            continue  #Skip this question if it's not in the DB (error handling)

        try:
            score = question['scores'][int(answer)] # Access the score based on the answer index
            total_score += score
        except (IndexError, ValueError) as e:
            print(f"Error calculating score for question {question_id}: {e}")
            continue #Skip this question

    #Determine the stress Level
    if total_score < 5:
        level = "Low Stress"
    elif total_score < 10:
        level = "Moderate Stress"
    else:
        level = "High Stress"
    return total_score, level

@assessment_bp.route("/start", methods=["POST"])
def start_assessment():
    """Start the assessment and ask the first question."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized access"}), 401

    # Verify question_collection is available
    if question_collection is None:
        return jsonify({"error": "Database error: question_collection is not initialized."}), 500

    # Cleanup expired sessions
    cleanup_expired_sessions()

    # First question
    first_question = "Which of these best describes your current state? (lonely, depressed, anxious)"

    # Start a new assessment session
    ongoing_assessments[user_id] = {"category": None, "question_ids": [], "answers": [], "timestamp": datetime.datetime.utcnow()}

    return jsonify({"question": first_question, "info": "Please type one of: Anger, Anxiety, Body Image, Depression, Finances, General Wellbeing, Grief, Guilt, Loneliness, Motivation, Relationships, Resilience, Self-Esteem, Sleep, Social Support, Spirituality, Stress, Substance Use, Trauma, Work/School."}), 200

@assessment_bp.route("/next", methods=["POST"])
def next_question():
    """Process the user's answer and provide the next question."""
    data = request.json
    user_id = verify_jwt_token(request)
    answer = data.get("answer")

    if not user_id or answer is None:
        return jsonify({"error": "Invalid request. Ensure user is authenticated and answer is provided."}), 400

    # Verify question_collection is available
    if question_collection is None:
        return jsonify({"error": "Database connection error: question_collection is not initialized."}), 500

    # Cleanup expired sessions
    cleanup_expired_sessions()

    # Fetch user session
    if user_id not in ongoing_assessments:
        return jsonify({"error": "Session expired or assessment not started. Please restart."}), 400

    user_data = ongoing_assessments[user_id]

    # If category is not set, determine category based on first answer
    if user_data["category"] is None:
        category = answer.lower()
        # print(category)

        # Validate Category
        try:
            valid_categories = question_collection.distinct("category")
            valid_categories_lower = [cat.lower() for cat in valid_categories]
        except Exception as e:
            print(f"Error fetching distinct categories: {e}")
            return jsonify({"error": "Error fetching categories from the database."}), 500


        if category not in valid_categories_lower:
            return jsonify({"error": f"Invalid category. Choose from: {', '.join(valid_categories)}."}), 400
        
        original_category = valid_categories[valid_categories_lower.index(category)]
        user_data["category"] = original_category
        user_data["question_ids"] = []
        user_data["answers"] = []
        user_data["timestamp"] = datetime.datetime.utcnow()  # Update session timestamp

        # Get the first question from the database for this category
        first_question_doc = question_collection.find_one({"category": original_category})  # Assuming you want the first one in the DB
        if not first_question_doc:
            return jsonify({"error": "No questions found for this category in the database."}), 500 #Server error

        user_data["question_ids"].append(first_question_doc["_id"])
        return jsonify({"question": first_question_doc["question_text"], "options": first_question_doc.get("options")}), 200 #Include options



    # Store the user's answer (as index of selected option)
    try:
       score = int(answer)
       # Find the last question asked
       last_question_id = user_data["question_ids"][-1]
       last_question = question_collection.find_one({"_id": last_question_id})

       if not last_question or 'options' not in last_question:
          return jsonify({"error": "Invalid question or options not found."}), 500

       if not (0 <= score < len(last_question['options'])): # Check if score is a valid index for the options
           return jsonify({"error": "Response must be a valid option index."}), 400

       user_data["answers"].append(score) #Store the index to the selected option
       user_data["timestamp"] = datetime.datetime.utcnow()  # Update session timestamp

    except ValueError:
        return jsonify({"error": "Invalid response format. Answer should be the index of your choice (0-n)."}), 400

    # Determine and fetch the next question
    category = user_data["category"]
    asked_question_ids = user_data["question_ids"]

    # Fetch a random question from the database excluding already asked question
    next_question_doc = question_collection.find_one({"category": category, "_id": {"$nin": asked_question_ids}}) #Excludes already asked question
    if not next_question_doc:
        # No more questions
        score, level = calculate_score(user_data["answers"], user_data["question_ids"])

        # Store final result
        result = {
            "user_id": user_id,
            "category": user_data["category"],
            "mental_score": score,
            "level": level,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        # Remove session after completion
        del ongoing_assessments[user_id]

        return jsonify(result), 200

    # Append the question ID and return the question
    user_data["question_ids"].append(next_question_doc["_id"])
    return jsonify({"question": next_question_doc["question_text"], "options": next_question_doc.get("options")}), 200

@assessment_bp.route("/categories", methods=["GET"])
def get_categories():
    """Get all available assessment categories."""
    try:
        if question_collection is None:
            return jsonify({"error": "Database connection error: question_collection is not initialized."}), 500
            
        valid_categories = question_collection.distinct("category")
        return jsonify({
            "categories": valid_categories,
            "count": len(valid_categories)
        }), 200
    except Exception as e:
        print(f"Error fetching distinct categories: {e}")
        return jsonify({"error": "Error fetching categories from the database."}), 500