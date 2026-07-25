import pytest
import sys
from pathlib import Path

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
import auth

def override_get_current_user():
    return {
        "id": "test_user_123",
        "email": "test@test.com",
        "username": "testuser",
        "created_at": "2026-07-26 00:00:00"
    }

# Apply the override to the main app instance so all TestClients get it
app.dependency_overrides[auth.get_current_user] = override_get_current_user
