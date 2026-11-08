/**
 * app/static/heat_canvas_engine.js - High-Performance Continuous Gaussian Heat Engine
 * 
 * Implements:
 * 1. Smooth 2D Gaussian Kernel Density Estimation (KDE) rasterization on an offscreen canvas buffer.
 * 2. Multi-channel rendering:
 *    - Traffic Flow: Emerald -> Amber -> Orange -> Crimson
 *    - Pedestrian Crowd: Electric Cyan -> Deep Indigo -> Magenta
 * 3. Mounts seamlessly to Google Maps (via custom google.maps.OverlayView)
 *    and the offline Obsidian Vector Fallback Canvas.
 * 
 * Completely eliminates the deprecated Google Maps HeatmapLayer and disjoint Circle discs.
 */

class HeatCanvasEngine {
  constructor(options = {}) {
    this.options = Object.assign({
      radius: 36,
      opacity: 0.72,
      blur: 0.85
    }, options);

    this.gMap = null;
    this.vectorCanvas = null;
    this.overlayView = null;
    this.canvas = document.createElement("canvas");
    this.canvas.className = "heat-canvas-overlay";
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });

    this.data = null;
    this.activeHorizon = 0;
    this.activeLayers = {
      traffic: true,
      crowd: true,
      junctions: true
    };

    // Precomputed gradient palettes (256-entry RGBA LUTs)
    this.palettes = {
      traffic: this._createGradientPalette([
        { stop: 0.00, color: "rgba(16, 185, 129, 0.0)" },
        { stop: 0.20, color: "rgba(16, 185, 129, 0.45)" }, // Low: Emerald
        { stop: 0.50, color: "rgba(245, 158, 11, 0.65)" }, // Moderate: Amber
        { stop: 0.75, color: "rgba(249, 115, 22, 0.82)" }, // High: Orange
        { stop: 1.00, color: "rgba(239, 68, 68, 0.95)" }   // Severe: Crimson
      ]),
      crowd: this._createGradientPalette([
        { stop: 0.00, color: "rgba(6, 182, 212, 0.0)" },
        { stop: 0.25, color: "rgba(6, 182, 212, 0.50)" },  // Free: Cyan
        { stop: 0.55, color: "rgba(99, 102, 241, 0.72)" },  // Moderate: Indigo
        { stop: 0.80, color: "rgba(168, 85, 247, 0.86)" },  // High: Purple
        { stop: 1.00, color: "rgba(236, 72, 153, 0.95)" }   // Severe: Magenta
      ])
    };

    // Precomputed radial Gaussian brush stamp
    this.brush = this._createGaussianBrush(this.options.radius);
    this._animFrame = null;
  }

  _createGradientPalette(stops) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 1;
    const ctx = canvas.getContext("2d");
    const grad = ctx.createLinearGradient(0, 0, 256, 0);
    stops.forEach(s => grad.addColorStop(s.stop, s.color));
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 256, 1);
    return ctx.getImageData(0, 0, 256, 1).data;
  }

  _createGaussianBrush(radius) {
    const size = radius * 2;
    const brush = document.createElement("canvas");
    brush.width = size;
    brush.height = size;
    const bCtx = brush.getContext("2d");

    const radGrad = bCtx.createRadialGradient(radius, radius, 0, radius, radius, radius);
    radGrad.addColorStop(0, "rgba(0,0,0,1.0)");
    radGrad.addColorStop(0.35, "rgba(0,0,0,0.65)");
    radGrad.addColorStop(0.70, "rgba(0,0,0,0.22)");
    radGrad.addColorStop(1.0, "rgba(0,0,0,0.0)");

    bCtx.fillStyle = radGrad;
    bCtx.beginPath();
    bCtx.arc(radius, radius, radius, 0, Math.PI * 2);
    bCtx.fill();
    return brush;
  }

  attachToGoogleMap(gMap) {
    if (!gMap || !window.google || !window.google.maps) return;
    this.gMap = gMap;

    const engine = this;
    const Overlay = function() {};
    Overlay.prototype = new window.google.maps.OverlayView();

    Overlay.prototype.onAdd = function() {
      const panes = this.getPanes();
      engine.canvas.style.position = "absolute";
      engine.canvas.style.pointerEvents = "none";
      engine.canvas.style.zIndex = "10";
      panes.overlayLayer.appendChild(engine.canvas);
    };

    Overlay.prototype.draw = function() {
      const projection = this.getProjection();
      if (!projection) return;

      const bounds = engine.gMap.getBounds();
      if (!bounds) return;

      const sw = projection.fromLatLngToDivPixel(bounds.getSouthWest());
      const ne = projection.fromLatLngToDivPixel(bounds.getNorthEast());

      const left = Math.min(sw.x, ne.x);
      const top = Math.min(sw.y, ne.y);
      const width = Math.abs(ne.x - sw.x);
      const height = Math.abs(sw.y - ne.y);

      engine.canvas.style.left = `${left}px`;
      engine.canvas.style.top = `${top}px`;
      engine.canvas.width = Math.max(10, width);
      engine.canvas.height = Math.max(10, height);

      engine._currentOrigin = { left, top };
      engine.renderHeatmap();
    };

    Overlay.prototype.onRemove = function() {
      if (engine.canvas.parentElement) {
        engine.canvas.parentElement.removeChild(engine.canvas);
      }
    };

    this.overlayView = new Overlay();
    this.overlayView.setMap(gMap);
  }

  attachToVectorCanvas(vectorCanvas) {
    if (!vectorCanvas) return;
    this.vectorCanvas = vectorCanvas;
    this.canvas.width = vectorCanvas.width || 900;
    this.canvas.height = vectorCanvas.height || 520;
    this._currentOrigin = { left: 0, top: 0 };
    this.renderHeatmap();
  }

  setData(payload) {
    this.data = payload;
    if (payload && typeof payload.horizon_minutes === "number") {
      this.activeHorizon = payload.horizon_minutes;
    }
    this.renderHeatmap();
  }

  setHorizon(minutes) {
    this.activeHorizon = Math.max(0, Math.min(60, Number(minutes) || 0));
    this.renderHeatmap();
  }

  setLayers(layerToggles) {
    this.activeLayers = Object.assign(this.activeLayers, layerToggles);
    this.renderHeatmap();
  }

  clear() {
    if (this.ctx && this.canvas) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  renderGaussianKernel(ctx, x, y, radius, intensity, channel = "traffic") {
    ctx.globalAlpha = Math.min(1.0, Math.max(0.1, intensity));
    const size = radius * 2;
    ctx.drawImage(this.brush, x - radius, y - radius, size, size);
  }

  renderHeatmap() {
    if (!this.canvas || !this.ctx || !this.data) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    if (w <= 0 || h <= 0) return;

    this.clear();

    // 1. Offscreen alpha accumulation buffer
    const alphaCanvas = document.createElement("canvas");
    alphaCanvas.width = w;
    alphaCanvas.height = h;
    const alphaCtx = alphaCanvas.getContext("2d");

    // 2. Render Traffic Layer
    if (this.activeLayers.traffic && Array.isArray(this.data.traffic_layer)) {
      this.data.traffic_layer.forEach(corridor => {
        const segs = corridor.sub_segments || [];
        segs.forEach(pt => {
          const screenPt = this._projectLatLng(pt.lat, pt.lng);
          if (screenPt && screenPt.x >= -50 && screenPt.x <= w + 50 && screenPt.y >= -50 && screenPt.y <= h + 50) {
            const rad = Math.round(this.options.radius * (0.8 + pt.weight * 0.5));
            this.renderGaussianKernel(alphaCtx, screenPt.x, screenPt.y, rad, pt.weight, "traffic");
          }
        });
      });
    }

    // 3. Colorize Traffic Layer onto visible canvas
    if (this.activeLayers.traffic) {
      this._applyColorPalette(alphaCtx, this.palettes.traffic, w, h);
    }

    // 4. Render Crowd Layer on separate alpha pass
    if (this.activeLayers.crowd && Array.isArray(this.data.crowd_layer)) {
      alphaCtx.clearRect(0, 0, w, h);
      this.data.crowd_layer.forEach(hub => {
        const screenPt = this._projectLatLng(hub.lat, hub.lng);
        if (screenPt && screenPt.x >= -60 && screenPt.x <= w + 60 && screenPt.y >= -60 && screenPt.y <= h + 60) {
          const rad = Math.round(this.options.radius * 1.4);
          this.renderGaussianKernel(alphaCtx, screenPt.x, screenPt.y, rad, hub.weight || 0.65, "crowd");
        }
      });
      this._applyColorPalette(alphaCtx, this.palettes.crowd, w, h);
    }

    // 5. Draw concentric radar alert pulse rings around Jam Hotspots
    if (Array.isArray(this.data.junction_layer)) {
      const now = Date.now();
      const pulseT = (now % 2200) / 2200.0;

      this.data.junction_layer.forEach(j => {
        if (!j.is_jam_hotspot) return;
        const pt = this._projectLatLng(j.lat, j.lng);
        if (!pt || pt.x < -50 || pt.x > w + 50 || pt.y < -50 || pt.y > h + 50) return;

        const isSevere = (j.alert_level === "JAM_ALERT" || (j.hcm_los && j.hcm_los.includes("LOS F")));
        const baseRgb = isSevere ? "239, 68, 68" : "249, 115, 22";

        // Draw 2 expanding concentric shockwave rings
        for (let ring = 0; ring < 2; ring++) {
          const phase = (pulseT + ring * 0.5) % 1.0;
          const radius = Math.round(12 + phase * 38);
          const alpha = (1.0 - phase) * (isSevere ? 0.72 : 0.50);

          this.ctx.save();
          this.ctx.beginPath();
          this.ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
          this.ctx.strokeStyle = `rgba(${baseRgb}, ${alpha})`;
          this.ctx.lineWidth = isSevere ? 2.6 : 1.8;
          this.ctx.shadowColor = `rgba(${baseRgb}, 0.8)`;
          this.ctx.shadowBlur = 8;
          this.ctx.stroke();
          this.ctx.restore();
        }
      });
    }
  }

  _projectLatLng(lat, lng) {
    if (this.gMap && this.overlayView && window.google && window.google.maps) {
      const projection = this.overlayView.getProjection();
      if (!projection) return null;
      const divPt = projection.fromLatLngToDivPixel(new window.google.maps.LatLng(lat, lng));
      if (!divPt || !this._currentOrigin) return null;
      return {
        x: divPt.x - this._currentOrigin.left,
        y: divPt.y - this._currentOrigin.top
      };
    } else if (this.vectorCanvas) {
      // Offline Vector Fallback projection (Normalized Bengaluru bounding box)
      const minLat = 12.80, maxLat = 13.10;
      const minLng = 77.48, maxLng = 77.78;
      const x = ((lng - minLng) / (maxLng - minLng)) * this.canvas.width;
      const y = (1.0 - ((lat - minLat) / (maxLat - minLat))) * this.canvas.height;
      return { x, y };
    }
    return null;
  }

  _applyColorPalette(sourceCtx, paletteData, width, height) {
    const imgData = sourceCtx.getImageData(0, 0, width, height);
    const pixels = imgData.data;
    const len = pixels.length;

    for (let i = 0; i < len; i += 4) {
      const alpha = pixels[i + 3];
      if (alpha > 4) {
        const palIdx = alpha * 4;
        pixels[i] = paletteData[palIdx];         // R
        pixels[i + 1] = paletteData[palIdx + 1]; // G
        pixels[i + 2] = paletteData[palIdx + 2]; // B
        pixels[i + 3] = Math.round(paletteData[palIdx + 3] * this.options.opacity); // A
      }
    }

    // Blend onto main canvas
    const tempCanvas = document.createElement("canvas");
    tempCanvas.width = width;
    tempCanvas.height = height;
    tempCanvas.getContext("2d").putImageData(imgData, 0, 0);
    this.ctx.drawImage(tempCanvas, 0, 0);
  }
}

window.HeatCanvasEngine = HeatCanvasEngine;
