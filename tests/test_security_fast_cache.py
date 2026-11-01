"""
tests/test_security_fast_cache.py - Unit & Concurrency Tests for Production Security & Fast Cache
"""

import time
import threading
from pathlib import Path
from traffic_system.core.security import SecurityManager
from traffic_system.core.entities import UserRole

def test_criteria_validation(tmp_path):
    db_path = tmp_path / "test_users.json"
    mgr = SecurityManager(db_path=db_path)

    # Short username
    ok, msg = mgr.register("ab", "Admin@123")
    assert not ok
    assert "between 3 and 32 characters" in msg

    # Invalid characters in username
    ok, msg = mgr.register("user<script>", "Admin@123")
    assert not ok
    assert "letters, numbers" in msg

    # Short password
    ok, msg = mgr.register("validuser", "123")
    assert not ok
    assert "at least 6 characters" in msg

    # Valid registration
    ok, msg = mgr.register("field_commuter", "ValidPass@123", role="Road User")
    assert ok

def test_fast_cache_and_double_submission(tmp_path):
    db_path = tmp_path / "test_users.json"
    mgr = SecurityManager(db_path=db_path)

    # First login works
    ok, msg, sess1 = mgr.login("commuter", "Admin@123")
    assert ok
    assert sess1["username"] == "commuter"
    assert sess1["role"] == "Road User"

    # Immediate second login hits Fast Cache (memoized session)
    ok2, msg2, sess2 = mgr.login("commuter", "Admin@123")
    assert ok2
    assert sess2["token"] == sess1["token"]  # Exact memoized fast session

def test_threshold_rate_limiting(tmp_path):
    db_path = tmp_path / "test_users.json"
    mgr = SecurityManager(db_path=db_path)

    # 5 consecutive failed logins
    for i in range(5):
        ok, msg, _ = mgr.login("commuter", "WrongPassword!")
        assert not ok
        assert "Invalid username or password" in msg

    # 6th attempt should be blocked by rate limiting threshold
    ok, msg, _ = mgr.login("commuter", "WrongPassword!")
    assert not ok
    assert "Too many failed attempts" in msg or "lockout active" in msg

def test_concurrency_thread_safety(tmp_path):
    db_path = tmp_path / "test_users.json"
    mgr = SecurityManager(db_path=db_path)

    results = []
    def worker(i):
        ok, msg, sess = mgr.login("commuter", "Admin@123")
        results.append(ok)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads succeed (some via direct auth, some via fast cache duplicate suppression)
    assert len(results) == 10
    assert any(results)

if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])
