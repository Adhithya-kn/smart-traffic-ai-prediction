# Design System & UI Specifications: Obsidian Luxury Standard

## 1. Aesthetic Mandates & Anti-AI-Slop Rules

- **FORBIDDEN:**
  - AI-generated generic card templates with uniform purple/violet neon glows.
  - Flat, unstyled cards without specular lighting or spatial depth.
  - Low-contrast gray text on dark gray surfaces.
  - Monolithic single-column scrolling layouts.
- **MANDATORY:**
  - **Palette:** Deep neutral obsidian core (`#07080a`), card background (`#0e1117`), border highlight (`rgba(255, 255, 255, 0.08)`).
  - **Specular Top Edge:** `inset 0 1px 0 0 rgba(255, 255, 255, 0.16)`.
  - **Glassmorphism:** Frosted blur `backdrop-filter: blur(16px)`.
  - **Spring Physics:** `cubic-bezier(0.16, 1, 0.3, 1)` for transitions.
  - **Tactile Feedback:** Buttons depress with `transform: scale(0.97)` on click.
  - **Status Accents:**
    - Severe: Crimson Coral (`#f43f5e`, glow `rgba(244, 63, 94, 0.25)`)
    - High: Amber Flame (`#f59e0b`, glow `rgba(245, 158, 11, 0.25)`)
    - Moderate: Cyan Emerald (`#06b6d4`, glow `rgba(6, 182, 212, 0.25)`)
    - Low: Vivid Mint (`#10b981`, glow `rgba(16, 185, 129, 0.25)`)

---

## 2. Design Tokens

```css
:root {
  --bg-app: #07080a;
  --bg-surface: #0e1117;
  --bg-surface-elevated: #161b22;
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-specular: rgba(255, 255, 255, 0.16);
  --text-primary: #f0f6fc;
  --text-secondary: #8b949e;
  --text-muted: #484f58;
  --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
  --font-mono: "SF Mono", "JetBrains Mono", Menlo, monospace;
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --shadow-ambient: 0 12px 36px rgba(0, 0, 0, 0.6);
  --transition-spring: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
```
