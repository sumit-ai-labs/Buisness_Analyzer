# Design System Specification — Business Disruption Intelligence Platform

## 1. Visual Language & Principles
- **Aesthetic**: Serious operational intelligence / control-center platform.
- **Surface System**: Mixed light + dark.
  - Fog-white canvas (`#f7f7f8`) for base page views.
  - Pure white cards (`#ffffff`) with subtle hairline border (`#d9d9de`) and restrained shadows.
  - Dark obsidian product panels (`#212126`) with inset highlights for technical inspection, AI decision center, and status cards.
- **Accent Color**: Electric Violet (`#6c47ff`) used with restraint (active navigation, primary action buttons, key indicators).
- **Secondary Accent**: Cyan Spark (`#5de3ff`) for technical metadata and LLM insights.

## 2. Core Color Tokens
| Name | Hex | Usage |
|------|-----|-------|
| Void Black | `#131316` | Primary headers, high-contrast text |
| Fog White | `#f7f7f8` | Page canvas, main background |
| Pure White | `#ffffff` | Primary cards, table background |
| Graphite | `#5e5f6e` | Secondary body text, table headers |
| Ash | `#747686` | Minor labels, placeholder text |
| Hairline | `#d9d9de` | Subtle borders, dividers |
| Mist | `#eeeef0` | Meter backgrounds, hovered states |
| Stone | `#9394a1` | Muted dark-panel text |
| Obsidian Card | `#212126` | Technical/AI panels, status panels |
| Dark Surface | `#2f3037` | Inset dark cards, input surfaces in dark panels |
| Slate Mid | `#696a78` | Dark mode borders |
| Electric Violet | `#6c47ff` | Active nav, primary buttons, focal accent |
| Violet Soft | `#615cf6` | Hover state for primary buttons |
| Cyan Spark | `#5de3ff` | Technical tags, LLM extraction markers |

## 3. Typography
- **Primary Body & Titles**: Geist (`sans-serif` fallback)
- **UI Labels & Controls**: Inter
- **Technical & Scores**: Söhne Mono (`JetBrains Mono`, `monospace` fallback)
- **Scale**:
  - Page title: 32px / 700
  - Section title: 20px / 600
  - Subsection: 18px / 600
  - Body: 14px / 400
  - Metadata: 12px / 500
  - Technical labels: 11px / 600

## 4. Spacing Scale (4px Base)
`4px`, `8px`, `12px`, `16px`, `20px`, `24px`, `32px`, `40px`, `48px`, `64px`, `80px`

## 5. Radii Scale
- Buttons & inputs: `6px`
- Small cards: `8px`
- Default cards & panels: `16px`
- Badges, pills, tags: `9999px`

## 6. Verification Statuses
- **HIGH**: Score ≥ 80 (Subtle positive green/emerald)
- **MODERATE**: 60 ≤ Score < 80 (Neutral electric violet)
- **LOW**: 35 ≤ Score < 60 (Warm amber)
- **UNCONFIRMED**: Score < 35 (Muted amber warning, gated)
*(Never use "TRUE" or "FAKE")*
