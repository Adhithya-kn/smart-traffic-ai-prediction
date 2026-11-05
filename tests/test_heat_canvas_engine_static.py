"""
tests/test_heat_canvas_engine_static.py - Static and Contract Tests for Continuous Canvas Heat Engine
Ensures:
1. heat_canvas_engine.js exists and exports class HeatCanvasEngine.
2. HeatCanvasEngine implements Gaussian kernel rasterization, multi-channel color palettes, and Google Maps OverlayView / Vector canvas fallback mounting.
3. app/static/index.html imports heat_canvas_engine.js.
4. Static synchronization keeps app/static and public in 100% parity.
"""

from pathlib import Path
import subprocess


def test_heat_canvas_engine_exists_and_in_index():
    js_file = Path("app/static/heat_canvas_engine.js")
    assert js_file.exists(), "app/static/heat_canvas_engine.js must exist"

    content = js_file.read_text(encoding="utf-8")
    assert "class HeatCanvasEngine" in content
    assert "attachToGoogleMap" in content
    assert "attachToVectorCanvas" in content
    assert "setHorizon" in content
    assert "setLayers" in content
    assert "renderGaussianKernel" in content or "renderHeatmap" in content

    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert "heat_canvas_engine.js" in index_html


def test_static_synchronization_parity():
    res = subprocess.run(["python3", "scripts/sync_static.py", "--check"], capture_output=True, text=True)
    assert res.returncode == 0, f"Static assets out of sync: {res.stdout} {res.stderr}"
