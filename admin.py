from flask import Blueprint, jsonify, request
from models import get_database
from bson import ObjectId
from auth import verify_jwt_token

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

@admin_bp.route("/users", methods=["GET"])
def get_all_users():
    """Get all users (admin only)."""
    # Verify admin privileges
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401
    
    # Get the database dynamically when the route is called
    db = get_database()
    users_collection = db["users"]
    
    # Check if user is admin
    current_user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not current_user or not current_user.get("is_admin", False):
        return jsonify({"error": "Forbidden. Admin access required."}), 403
    
    # Get all users
    users = list(users_collection.find({}, {"password": 0}))
    
    # Convert ObjectId to string
    for user in users:
        user["user_id"] = str(user["_id"])
        del user["_id"]
    
    return jsonify({"users": users}), 200