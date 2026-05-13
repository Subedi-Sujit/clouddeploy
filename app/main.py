

"""
CloudDeploy - Task Manager API
A simple Flask REST API for managing tasks, instrumented for observability.
"""

import os
import logging
from datetime import datetime

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from prometheus_flask_exporter import PrometheusMetrics


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
if os.getenv("TESTING") == "true":
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
else:
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        db_host = os.getenv("DB_HOST", "localhost")

        # Cheap AWS demo mode: avoid RDS, use SQLite inside container
        if db_host in ["localhost", "127.0.0.1"]:
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/clouddeploy.db"
        else:
            db_user = os.getenv("DB_USER", "clouddeploy")
            db_password = os.getenv("DB_PASSWORD", "devpassword")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "clouddeploy")

            app.config["SQLALCHEMY_DATABASE_URI"] = (
                f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

metrics = PrometheusMetrics(app)
metrics.info("app_info", "CloudDeploy Task API", version="1.0.0")


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


with app.app_context():
    db.create_all()
    logger.info("Database tables initialized")


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "CloudDeploy Task API",
        "status": "running",
        "endpoints": ["/health", "/ready", "/api/tasks", "/metrics"]
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/ready", methods=["GET"])
def ready():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        return jsonify({"status": "not ready", "error": str(e)}), 503


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return jsonify([task.to_dict() for task in tasks]), 200


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()

    if not data or "title" not in data:
        return jsonify({"error": "title is required"}), 400

    task = Task(
        title=data["title"],
        description=data.get("description"),
        completed=data.get("completed", False),
    )

    db.session.add(task)
    db.session.commit()

    logger.info(f"Created task {task.id}: {task.title}")
    return jsonify(task.to_dict()), 201


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict()), 200


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if "title" in data:
        task.title = data["title"]
    if "description" in data:
        task.description = data["description"]
    if "completed" in data:
        task.completed = data["completed"]

    db.session.commit()

    logger.info(f"Updated task {task.id}")
    return jsonify(task.to_dict()), 200


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    logger.info(f"Deleted task {task_id}")
    return "", 204

import socket
import os

@app.route("/debug")
def debug():
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid()
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)





