---
name: Surakshanet Light
colors:
  surface: '#FAF8F6'
  surface-dim: '#ECE8E4'
  surface-bright: '#FFFFFF'
  surface-container-lowest: '#FFFFFF'
  surface-container-low: '#F8F6F4'
  surface-container: '#F2EEEA'
  surface-container-high: '#EAE4DE'
  surface-container-highest: '#E2DBD4'
  on-surface: '#1E293B'
  on-surface-variant: '#475569'
  inverse-surface: '#0F172A'
  inverse-on-surface: '#F8FAFC'
  outline: '#94A3B8'
  outline-variant: '#E2E8F0'
  surface-tint: '#0D9488'
  primary: '#0D9488'
  on-primary: '#FFFFFF'
  primary-container: '#CCFBF1'
  on-primary-container: '#115E59'
  inverse-primary: '#5EEAD4'
  secondary: '#0284C7'
  on-secondary: '#FFFFFF'
  secondary-container: '#E0F2FE'
  on-secondary-container: '#0369A1'
  tertiary: '#16A34A'
  on-tertiary: '#FFFFFF'
  tertiary-container: '#DCFCE7'
  on-tertiary-container: '#15803D'
  error: '#DC2626'
  on-error: '#FFFFFF'
  error-container: '#FEE2E2'
  on-error-container: '#991B1B'
  primary-fixed: '#99F6E4'
  primary-fixed-dim: '#5EEAD4'
  on-primary-fixed: '#042F2E'
  on-primary-fixed-variant: '#115E59'
  secondary-fixed: '#BAE6FD'
  secondary-fixed-dim: '#7DD3FC'
  on-secondary-fixed: '#082F49'
  on-secondary-fixed-variant: '#0369A1'
  tertiary-fixed: '#BBF7D0'
  tertiary-fixed-dim: '#86EFAC'
  on-tertiary-fixed: '#052E16'
  on-tertiary-fixed-variant: '#15803D'
  background: '#FAF8F6'
  on-background: '#1E293B'
  surface-variant: '#F1F5F9'
typography:
  display-lg:
    fontFamily: Syne
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Syne
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-caps:
    fontFamily: Space Grotesk
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-desktop: 24px
  sidebar-width: 240px
  panel-width: 380px
---

# Surakshanet Light Theme Design System
**Intelligent Traffic Operations & Digital Twin Command Center**

---

## Brand & Style
The design system is engineered for high-performance traffic management centers and municipal smart city operations. It adopts a **Crisp Light Digital Twin / Modern Operations** aesthetic, combining municipal clarity with high-contrast mission-critical telemetry.

The user interface prioritizes clarity, data density without visual fatigue, and instant comprehension. The light theme uses soft oyster-white foundations (`#FAF8F6`) and pure white card surfaces (`#FFFFFF`) framed by precise slate borders (`#E2E8F0`), allowing critical operational status signals (Green for Active Flow, Amber for Caution/Spillback, Crimson for Emergency Corridor Pre-emption) to stand out immediately. Secondary overlays employ subtle frosted glassmorphism for floating map ribbons.

---

## Colors
The palette is built on a clean, high-luminance light foundation accented by Sovereign Teal and clear semantic signaling.

- **Primary & Surface:** Base canvas is `#FAF8F6`, cards are `#FFFFFF`, and containers use `#F1F5F9`.
- **Primary Brand:** Sovereign Teal (`#0D9488`) represents active AI intelligence, MARL optimization, and primary controls.
- **Secondary Accent:** Sky Blue (`#0284C7`) represents network telemetry, edge device metrics, and live data streaming.
- **Tertiary Flow:** Emerald Green (`#16A34A`) signifies Level of Service A/B, active corridor green wave, and optimal operations.
- **Alert Hierarchy:**
  - **Warning Amber (`#D97706`):** Moderate congestion, approaching capacity, spillback threshold warnings.
  - **Critical Crimson (`#DC2626`):** Emergency vehicle pre-emption, collision alerts, conflict monitors.
- **Text & Borders:** Deep slate (`#0F172A`) for primary headings and metric values, slate (`#475569`) for labels, slate (`#94A3B8`) for muted metadata, and `#E2E8F0` for structural borders.

---

## Typography
The system utilizes a tri-font pairing for maximum operational efficiency:
- **Syne:** Modern, authoritative display font used for page titles, brand markers, and primary modal headers.
- **Space Grotesk / Inter:** Clear, geometric sans-serif for body text, form controls, navigation items, and buttons.
- **JetBrains Mono:** Monospace font for telemetry streams, PCU counts, TraCI simulation step counters, coordinates, and latency indicators to eliminate visual jitter during real-time updates.

---

## Layout & Spacing
The layout follows an **Operations Grid & Map-Centric** model:
- **Sidebar:** Fixed 240px persistent navigation rail on the left with distinct functional groupings (Operations, Insights, System, Admin).
- **Header:** 56px sticky top bar with global search, emergency override action, and real-time clock.
- **Rhythm:** 4px base spacing unit with 16px card padding and 24px desktop margins.
- **Map Viewport:** 100% full-bleed GIS map with floating frosted-glass metric ribbons and docked telemetry feeds.

---

## Elevation & Depth
Depth is created through clean boundary contrast and ambient light scattering:
- **Base Canvas:** `#FAF8F6` flat background.
- **Card Surfaces:** Pure white `#FFFFFF` with `1px solid #E2E8F0` border and soft ambient shadow (`0 1px 3px rgba(0, 0, 0, 0.04)`).
- **Floating Ribbons:** Frosted white `rgba(255, 255, 255, 0.95)` with `backdrop-filter: blur(12px)` and elevated shadow.
- **Hover States:** Subtle border illumination and soft 4px lift.

---

## Components
- **Top Metric Ribbon:** Floating cards over the map showing active vehicles, average speed, network LOS, throughput, and active alerts.
- **Agent Telemetry Stream:** High-contrast light terminal box with monospace event rows logging MARL actions, rewards, and phase adjustments.
- **Emergency Priority Corridor:** Dual-state action trigger switching from crimson stand-by to active green wave with vehicle tracking and signal countdowns.
- **Forecasting & Spillback Gauge:** Semicircular SVG risk meter with green-to-red gradient and actual vs. predicted PCU chart.
- **VMS LED Gantries:** Highway variable message sign simulation with live typing and LED dot-matrix display.
