"""
tests/test_api_security.py - Security, Privilege Escalation Defense & Endpoint Protection Tests
"""

import pytest
from traffic_system.core.security import SecurityManager, sanitize_user
from traffic_system.core.entities import UserRole


def test_public_registration_privilege_escalation_blocked(tmp_path):
    db_file = tmp_path / "users_sec.json"
    mgr = SecurityManager(db_path=db_file)

    # Public user attempts to register as administrator
    ok, msg = mgr.register("hacker_admin", "Admin@123", role="Traffic Management", is_admin_invoker=False)
    assert ok is True

    # User MUST be downgraded to Road User
    user = mgr.users.get("hacker_admin")
    assert user is not None
    assert user["role"] == UserRole.ROAD_USER.value
    assert user["role"] != UserRole.TRAFFIC_MANAGEMENT.value


def test_admin_invoker_can_provision_manager(tmp_path):
    db_file = tmp_path / "users_admin.json"
    mgr = SecurityManager(db_path=db_file)

    ok, msg = mgr.register("legit_admin", "Admin@123", role="Traffic Management", is_admin_invoker=True)
    assert ok is True
    user = mgr.users.get("legit_admin")
    assert user["role"] == UserRole.TRAFFIC_MANAGEMENT.value


def test_sanitize_user_strips_sensitive_fields():
    raw_user = {
        "username": "test_user",
        "password_hash": "abcdef1234567890",
        "salt": "1234567890abcdef",
        "role": "Road User",
        "created_at": 12345678.9
    }
    clean = sanitize_user(raw_user)
    assert "password_hash" not in clean
    assert "salt" not in clean
    assert clean["username"] == "test_user"
    assert clean["role"] == "Road User"


def test_session_logout_revocation(tmp_path):
    db_file = tmp_path / "users_sess.json"
    mgr = SecurityManager(db_path=db_file)
    mgr.register("test_sess", "Admin@123")
    ok, _, sess = mgr.login("test_sess", "Admin@123")
    assert ok is True
    token = sess["token"]

    user_info = mgr.get_user_by_token(token)
    assert user_info is not None

    mgr.logout(token)
    assert mgr.get_user_by_token(token) is None
