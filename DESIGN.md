# Design System

## Direction

A quiet research workbench. Light neutral surfaces carry the daily workflow; a dark graph canvas is reserved for topology exploration. The interface uses progressive disclosure to reveal explanations, evidence, and processing records without crowding the primary task.

## Color

- Canvas: `oklch(97.5% 0.006 255)`
- Surface: `oklch(99% 0.004 255)`
- Ink: `oklch(24% 0.025 250)`
- Muted ink: `oklch(50% 0.02 250)`
- Line: `oklch(89% 0.012 250)`
- Primary: `oklch(52% 0.18 266)`
- Success: `oklch(55% 0.12 158)`
- Warning: `oklch(68% 0.14 72)`
- Change: `oklch(62% 0.15 35)`

Accent colors are reserved for actions, selections, state, and data comparison.

## Typography

Use the native system sans stack with PingFang SC and Microsoft YaHei fallbacks. Product headings use a compact fixed scale. Numbers use tabular figures. Long descriptions stay under 70 characters per line where practical.

## Layout

- Desktop application shell: 224 px navigation, flexible content.
- Core workspaces: object list, primary canvas, contextual technical inspector.
- Use dividers and spacing for grouping; cards only frame actionable, independently selectable objects.
- Base spacing scale: 4, 8, 12, 16, 24, 32, 48 px.

## Components

- Buttons and inputs use Ant Design primitives with restrained overrides.
- Evidence Inspector uses three tabs: explanation, evidence, processing record.
- Status is always expressed with text plus color.
- Loading uses skeletons; empty states explain the next available action.
- Motion lasts 150-250 ms, communicates selection or state, and respects reduced motion.
