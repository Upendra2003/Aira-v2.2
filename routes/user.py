from flask import Blueprint, request, jsonify, send_file
from database.models import get_database
from bson import ObjectId
from werkzeug.security import generate_password_hash
from routes.auth import verify_jwt_token
from dotenv import load_dotenv
import os
import logging
import uuid
from werkzeug.utils import secure_filename
from io import BytesIO
import gridfs

load_dotenv()
logger = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__, url_prefix="/api/user")
DEFAULT_PROFILE_PHOTO = os.getenv("PROFILE_PIC")

# Configure upload settings
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@user_bp.route("/profile", methods=["GET"])
def get_profile():
    """Retrieve user profile safely."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    try:
        db = get_database()
        users_collection = db["users"]
        user = users_collection.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except Exception as e:
        logger.error(f"Database error while retrieving profile: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500

    if not user:
        return jsonify({"error": "User not found"}), 404

    user["user_id"] = str(user["_id"])
    user["profile_photo"] = user.get("profile_photo", DEFAULT_PROFILE_PHOTO)
    del user["_id"]

    logger.info(f"Profile retrieved for user {user_id}")
    return jsonify({"profile": user}), 200

@user_bp.route("/update", methods=["PUT"])
def update_profile():
    """Update user profile safely."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    # Handle form data for file uploads
    new_username = request.form.get("username")
    new_email = request.form.get("email")
    new_password = request.form.get("password")
    
    # Check if data is sent as JSON instead of form data
    if not new_username and not new_email and request.is_json:
        data = request.json
        new_username = data.get("username")
        new_email = data.get("email")
        new_password = data.get("password")

    if not new_username or not new_email:
        return jsonify({"error": "Username and email are required."}), 400

    try:
        db = get_database()
        users_collection = db["users"]
        
        # Check if email already exists
        existing_user = users_collection.find_one({"email": new_email, "_id": {"$ne": ObjectId(user_id)}})
        if existing_user:
            return jsonify({"error": "Email is already in use."}), 400

        update_data = {
            "username": new_username,
            "email": new_email
        }
        
        # Handle password update
        if new_password:
            update_data["password"] = generate_password_hash(new_password)
        
        # Handle file upload for profile photo
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename and allowed_file(file.filename):
                # Initialize GridFS
                fs = gridfs.GridFS(db)
                
                # Get file content and metadata
                filename = secure_filename(file.filename)
                content_type = file.content_type
                
                # Store the file in GridFS
                file_id = fs.put(
                    file.read(),
                    filename=filename,
                    content_type=content_type,
                    user_id=user_id
                )
                
                # Store the file_id in the user document
                update_data["profile_photo"] = str(file_id)
                update_data["profile_photo_type"] = content_type
                logger.info(f"Uploaded profile photo for user {user_id}: {filename}")

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    except Exception as e:
        logger.error(f"Database error while updating profile: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500

    if result.modified_count == 0:
        return jsonify({"message": "No changes made or user not found."}), 400

    logger.info(f"Profile updated for user {user_id}")
    return jsonify({"message": "Profile updated successfully"}), 200

@user_bp.route("/upload-photo", methods=["POST"])
def upload_profile_photo():
    """Upload a profile photo separately."""
    user_id = verify_jwt_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    if 'profile_photo' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['profile_photo']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    if file and allowed_file(file.filename):
        try:
            db = get_database()
            # Initialize GridFS
            fs = gridfs.GridFS(db)
            
            # Get file content and metadata
            filename = secure_filename(file.filename)
            content_type = file.content_type
            
            # Store the file in GridFS
            file_id = fs.put(
                file.read(),
                filename=filename,
                content_type=content_type,
                user_id=user_id
            )
            
            # Update the user's profile photo in the database
            users_collection = db["users"]
            
            # Store file_id reference and content type
            result = users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "profile_photo": str(file_id),
                    "profile_photo_type": content_type
                }}
            )
            
            if result.modified_count == 0:
                return jsonify({"error": "Failed to update profile photo or user not found"}), 400
                
            logger.info(f"Profile photo uploaded for user {user_id}")
            return jsonify({
                "message": "Profile photo uploaded successfully",
                "profile_photo": str(file_id)
            }), 200
            
        except Exception as e:
            logger.error(f"Error uploading profile photo: {e}")
            return jsonify({"error": "Error uploading file", "details": str(e)}), 500
    
    return jsonify({"error": "File type not allowed"}), 400

@user_bp.route("/photo/<file_id>")
def get_profile_photo(file_id):
    """Retrieve a profile photo from GridFS by its ID."""
    try:
        db = get_database()
        fs = gridfs.GridFS(db)
        
        # Check if file exists
        if not fs.exists(ObjectId(file_id)):
            return jsonify({"error": "File not found"}), 404
            
        # Get the file from GridFS
        file_data = fs.get(ObjectId(file_id))
        
        # Create a BytesIO object from the file data
        file_stream = BytesIO(file_data.read())
        
        # Return the file with the correct content type
        return send_file(
            file_stream,
            mimetype=file_data.content_type,
            as_attachment=False,
            download_name=file_data.filename
        )
    
    except Exception as e:
        logger.error(f"Error retrieving profile photo: {e}")
        return jsonify({"error": "Error retrieving file", "details": str(e)}), 500