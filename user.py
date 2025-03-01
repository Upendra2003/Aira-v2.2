from flask import Blueprint, request, jsonify
from models import get_database, initialize_collections
from bson import ObjectId
from auth import verify_jwt_token

user_bp = Blueprint("user", __name__, url_prefix="/api/user")

@user_bp.route("/profile", methods=["GET"])
def get_profile():
    """Retrieve user profile safely."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    # Get the database dynamically when the route is called
    db = get_database()
    users_collection = db["users"]

    user = users_collection.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        return jsonify({"error": "User not found"}), 404

    user["user_id"] = str(user["_id"])
    del user["_id"]

    return jsonify({"profile": user}), 200

@user_bp.route("/update", methods=["PUT"])
def update_profile():
    """Update user profile safely."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.json
    new_username = data.get("username")
    new_email = data.get("email")
    new_password = data.get("password")

    if not new_username or not new_email:
        return jsonify({"error": "Username and email are required."}), 400

    # Get the database dynamically when the route is called
    db = get_database()
    users_collection = db["users"]

    existing_user = users_collection.find_one({"email": new_email, "_id": {"$ne": ObjectId(user_id)}})
    if existing_user:
        return jsonify({"error": "Email is already in use."}), 400

    # Prepare update document
    update_data = {"username": new_username, "email": new_email}
    
    # If password is provided, hash it and add to update
    if new_password:
        from werkzeug.security import generate_password_hash
        hashed_password = generate_password_hash(new_password)
        update_data["password"] = hashed_password

    # Update the user document
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        return jsonify({"error": "No changes made or user not found."}), 400

    return jsonify({"message": "Profile updated successfully"}), 200
