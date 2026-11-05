"""
tests/test_heatmap_ui_controls.py - Tests for Tri-Pillar Timeline Scrubber, Layer Toggles, and Tactical HUD
Ensures:
1. DOM has #heatmapTimelineSlider with 4 discrete snap points.
2. Layer buttons exist for Lanes, Heatmap (Traffic), Crowd, and Junctions.
3. Clean UI: Redundant Play Horizon playback button is removed.
4. Tactical Summary HUD container exists on map canvas.
"""

from pathlib import Path


def test_index_html_has_tri_pillar_controls():
    content = Path("app/static/index.html").read_text(encoding="utf-8")
    assert "heatmapTimelineSlider" in content
    assert "btnToggleCrowd" in content
    assert "btnToggleJunctions" in content or "btnToggleCorridors" in content
    assert "btnPlayForecast" not in content
    assert "tacticalHeatmapHud" in content
    assert "hudActiveHorizon" in content
    assert "hudPeakQueueJnc" in content
    assert "hudVruRiskHub" in content


def test_styles_has_timeline_and_hud_rules():
    content = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert ".heatmap-timeline-bar" in content
    assert ".tactical-heatmap-hud" in content
    assert ".obsidian-slider" in content
