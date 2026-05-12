"""
CloudDeploy - Task Manager API
A simple Flask REST API for managing tasks, instrumented for observability.
"""
import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from prometheus_flask_exporter import PrometheusMetrics
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Database configuration - read from environment variables
# This is critical: NEVER hardcode credentials. They come from env vars,
# which in production would be injected from AWS Secrets Manager.
if os.getenv('TESTING') == 'true':
    # Use SQLite in-memory for tests (no psycopg2 required)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
else:
    DB_USER = os.getenv('DB_USER', 'clouddeploy')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'devpassword')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'clouddeploy')

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)

# Prometheus metrics - exposes /metrics endpoint automatically
metrics = PrometheusMetrics(app)
metrics.info('app_info', 'CloudDeploy Task API', version='1.0.0')


# ============================================================
# Database Model
# ============================================================
class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================
# Routes
# ============================================================
@app.route('/health', methods=['GET'])
def health():
    """Liveness probe - just confirms the app is running."""
    return jsonify({'status': 'healthy'}), 200


@app.route('/ready', methods=['GET'])
def ready():
    """Readiness probe - confirms the database connection works."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ready'}), 200
    except Exception as e:
        logger.error(f'Database not ready: {e}')
        return jsonify({'status': 'not ready', 'error': str(e)}), 503


@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """List all tasks."""
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks]), 200


@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task."""
    data = request.get_json()

    if not data or 'title' not in data:
        return jsonify({'error': 'title is required'}), 400

    task = Task(
        title=data['title'],
        description=data.get('description'),
        completed=data.get('completed', False)
    )
    db.session.add(task)
    db.session.commit()

    logger.info(f'Created task {task.id}: {task.title}')
    return jsonify(task.to_dict()), 201


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a single task by ID."""
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict()), 200


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update an existing task."""
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'completed' in data:
        task.completed = data['completed']

    db.session.commit()
    logger.info(f'Updated task {task.id}')
    return jsonify(task.to_dict()), 200


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task."""
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    logger.info(f'Deleted task {task_id}')
    return '', 204


# ============================================================
# Initialize database on startup
# ============================================================
with app.app_context():
    try:
        db.create_all()
        logger.info('Database tables initialized')
    except Exception as e:
        logger.warning(f'Could not initialize database on startup: {e}')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
