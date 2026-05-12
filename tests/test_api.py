"""
Unit tests for the CloudDeploy Task API.
Uses SQLite in-memory database for fast, isolated tests.
"""
import os
# Override DB URI BEFORE importing the app so SQLAlchemy doesn't try to load psycopg2
os.environ['TESTING'] = 'true'

import pytest
from app.main import app, db


@pytest.fixture
def client():
    """Create a test client with an in-memory SQLite database."""
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True

    # Rebind SQLAlchemy to the new URI
    with app.app_context():
        db.engine.dispose()

    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield client
        db.session.remove()
        db.drop_all()


def test_health_endpoint(client):
    """The /health endpoint should always return 200."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'


def test_create_task(client):
    """POST /api/tasks should create a new task."""
    response = client.post('/api/tasks', json={
        'title': 'Write resume',
        'description': 'Update for cloud roles'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Write resume'
    assert data['completed'] is False
    assert 'id' in data


def test_create_task_without_title_fails(client):
    """Creating a task without a title should return 400."""
    response = client.post('/api/tasks', json={'description': 'no title'})
    assert response.status_code == 400


def test_list_tasks(client):
    """GET /api/tasks should return all tasks."""
    client.post('/api/tasks', json={'title': 'Task 1'})
    client.post('/api/tasks', json={'title': 'Task 2'})

    response = client.get('/api/tasks')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2


def test_get_single_task(client):
    """GET /api/tasks/<id> should return one task."""
    create_resp = client.post('/api/tasks', json={'title': 'Find a job'})
    task_id = create_resp.get_json()['id']

    response = client.get(f'/api/tasks/{task_id}')
    assert response.status_code == 200
    assert response.get_json()['title'] == 'Find a job'


def test_get_nonexistent_task_returns_404(client):
    """GET /api/tasks/<bad_id> should return 404."""
    response = client.get('/api/tasks/9999')
    assert response.status_code == 404


def test_update_task(client):
    """PUT /api/tasks/<id> should update the task."""
    create_resp = client.post('/api/tasks', json={'title': 'Original'})
    task_id = create_resp.get_json()['id']

    response = client.put(f'/api/tasks/{task_id}', json={
        'title': 'Updated',
        'completed': True
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated'
    assert data['completed'] is True


def test_delete_task(client):
    """DELETE /api/tasks/<id> should remove the task."""
    create_resp = client.post('/api/tasks', json={'title': 'Delete me'})
    task_id = create_resp.get_json()['id']

    response = client.delete(f'/api/tasks/{task_id}')
    assert response.status_code == 204

    # Verify it's gone
    get_resp = client.get(f'/api/tasks/{task_id}')
    assert get_resp.status_code == 404


def test_metrics_endpoint_exists(client):
    """The /metrics endpoint should be exposed for Prometheus."""
    response = client.get('/metrics')
    assert response.status_code == 200
    # Should contain Prometheus exposition format
    assert b'flask_http_request' in response.data
