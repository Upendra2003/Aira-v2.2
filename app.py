from flask import Flask, jsonify
from flask_cors import CORS
import time
import logging
from config import PORT
from models import init_db,initialize_collections
from auth import auth_bp
from chat import chat_bp
from assessment import assessment_bp
from feedback import feedback_bp
from user import user_bp
from admin import admin_bp
from models import mongo,users_collection,chat_history_collection,feedback_collection

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize MongoDB
init_db(app)

# Initialize collections after DB is set up
initialize_collections()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(assessment_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
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
    return jsonify({
        "db_initialized": mongo.db is not None,
        "collections": {
            "users": users_collection is not None,
            "chat_history": chat_history_collection is not None,
            "feedback": feedback_collection is not None,
        }
    })

if __name__ == "__main__":
    app.start_time = time.time()
    logging.info("Starting AIRA Therapist application")
    app.run(debug=True)
