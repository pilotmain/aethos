# Nexa Web UI Baseline

This UI baseline is the first accepted dark workspace layout:

- left narrow rail
- center chat workspace
- bottom input
- right control panel
- tabs: Job / Memory / System / Keys
- no redesign until functionality is restored

## Current phase

Functionality restoration only.

## Rules

- Do not replace the shell layout.
- Do not create static mock UI.
- Do not remove real API wiring.
- Do not add new visual experiments.
- Fix runtime errors first.
- Reconnect functionality one slice at a time.

## Baseline files (do not remove unless build requires)

- `app/page.tsx` — home shell
- `components/nexa/WorkspaceApp.tsx` — workspace (also re-exported from `components/WorkspaceApp.tsx`)
- `components/nexa/JobInlineCard.tsx` — job card (re-exported from `components/JobInlineCard.tsx`)
- `lib/api.ts`, `lib/config.ts`
- `app/login/page.tsx`

## Styling pipeline (keep stable)

- `app/globals.css`, `app/layout.tsx`, `tailwind.config.ts`, `postcss.config.mjs`
- Do not reintroduce `tailwind.config.js` or `postcss.config.js`
