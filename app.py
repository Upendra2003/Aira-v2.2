from flask import Flask, jsonify
from flask_cors import CORS
import time
import logging
from config import PORT
from database.models import init_db, mongo
# Import blueprints after DB initialization
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize MongoDB and collections - store the result
db_initialized = init_db(app)

# Only import blueprints after DB is initialized
if db_initialized:
    from routes.auth import auth_bp
    from routes.chat import chat_bp
    from routes.assessment import assessment_bp
    from routes.feedback import feedback_bp
    from routes.user import user_bp
    # from routes.admin import admin_bp
    
    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(user_bp)
    # app.register_blueprint(admin_bp)
    # app.register_blueprint(model_api_bp)
    

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": time.time()
    })

@app.route("/memory", methods=["GET"])
def memory_usage():
    import os
    import psutil
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return jsonify({
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
    })

@app.route("/debug/db", methods=["GET"])
def debug_db():
    from database.models import users_collection, chat_history_collection, feedback_collection, question_collection
    return jsonify({
        "db_initialized": mongo.db is not None,
        "collections": {
            "users": users_collection is not None,
            "chat_history": chat_history_collection is not None,
            "feedback": feedback_collection is not None,
            "questions": question_collection is not None
        }
    })

if __name__ == "__main__":
    app.start_time = time.time()
    logging.info("Starting AIRA Therapist application")
    app.run(debug=True)
