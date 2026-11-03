"""
tests/test_signin_portal_verification.py - Verification for Simplified Sign-in Portal & Security
"""

from pathlib import Path
from traffic_system.core.security import SecurityManager

def test_login_html_low_cognitive_load():
    login_html_path = Path("app/static/login.html")
    assert login_html_path.exists(), "login.html must exist"
    content = login_html_path.read_text(encoding="utf-8")

    assert "auth-tab-switch" not in content, "Tab switcher must be removed to eliminate cognitive load"
    assert "quickfill-pill" not in content, "Quickfill pills must be removed to eliminate cognitive load"
    assert "role-select-grid" not in content, "Role selection cards must be removed to eliminate cognitive load"

    assert 'id="usernameInput"' in content, "Username input must be present"
    assert 'id="passwordInput"' in content, "Password input must be present"
    assert 'id="submitBtn"' in content, "Submit button must be present"
    assert 'isSubmitting' in content, "Fast client debounce double-click guard must be present"

    assert 'Traffic Management' in content, "Traffic Management role handling must be present"
    assert 'Road User' in content, "Road User role handling must be present"
    assert 'window.location.replace("/portal")' in content, "Auto-route to portal must be present"

def test_backend_credentials_and_fast_cache(tmp_path):
    db_file = tmp_path / "users.json"
    mgr = SecurityManager(db_path=db_file)

    ok, msg = mgr.register("a", "Admin@123")
    assert not ok
    assert "between 3 and 32" in msg

    ok, msg = mgr.register("valid_name", "123")
    assert not ok
    assert "at least 6 characters" in msg

    ok, msg, sess_commuter = mgr.login("commuter", "Admin@123")
    assert ok
    assert sess_commuter["role"] == "Road User"
    assert "token" in sess_commuter

    ok, msg, sess_admin = mgr.login("traffic_admin", "Admin@123")
    assert ok
    assert sess_admin["role"] == "Traffic Management"
    assert "token" in sess_admin

    ok_memo, _, sess_memo = mgr.login("traffic_admin", "Admin@123")
    assert ok_memo
    assert sess_memo["token"] == sess_admin["token"]

def test_ui_design_uniformity_and_anti_fluff():
    portal_html = Path("app/static/index.html").read_text(encoding="utf-8")
    login_html = Path("app/static/login.html").read_text(encoding="utf-8")
    styles_css = Path("app/static/styles.css").read_text(encoding="utf-8")

    assert '<body class="theme-light">' not in portal_html, "index.html must not force theme-light"
    assert "--bg-app: #08090d" in styles_css, "styles.css must share unified obsidian background token"
    assert "--bg-app: #08090d" in login_html, "login.html must share unified obsidian background token"
    assert "--bg-surface: #0e1117" in styles_css, "styles.css must share unified surface token"
    assert "--bg-surface: #0e1117" in login_html, "login.html must share unified surface token"

    assert "TRAFFIC MANAGEMENT EARLY WARNING" not in portal_html, "All-caps promotional warning must be removed"
    assert "Dijkstra + TreeSHAP" not in portal_html, "Algorithm badges on card headers must be removed"
    assert "Greenshields Macroscopic" not in portal_html, "AI fluff tags must be removed"
    assert "MUTCD Aligned" not in portal_html, "Decorative card tags must be removed"

if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])
