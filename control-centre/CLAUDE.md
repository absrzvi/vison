# CLAUDE.md — control-centre

React 18 SPA. Vite bundler. JavaScript (no TypeScript). Deployed as a static bundle served by the cloud-backend or a reverse proxy.

## Stack

- React 18 (hooks only — no class components)
- React Router v6 (`createBrowserRouter`, `useNavigate`, `useParams`)
- Leaflet + react-leaflet for the fleet map
- Plain CSS modules + global CSS custom properties — no Tailwind, no inline styles, no hardcoded hex
- `src/ws/` — WebSocket/SSE client connecting to the cloud-backend SSE stream
- `src/mock/` — mock data for offline/dev work; never imported in production paths

## Commands

```bash
cd control-centre
npm run dev          # dev server on :5173
npm run build        # production bundle → dist/
npm run lint         # eslint
```

No test runner is configured yet. When adding tests, use Vitest (already a Vite project).

## File Conventions

- Components: `src/components/<feature>/<ComponentName>.jsx` + matching `.css`
- Hooks: `src/hooks/use<Name>.js`
- Constants: `src/constants/<name>.js`
- Context: `src/context/<Name>Context.jsx`

## What NOT to Touch

- `dist/` — generated; never edit
- `node_modules/` — never edit
- `src/mock/` — only edit if you're adding mock data for a new feature; never wire mock imports into real component trees
- Do not add TypeScript to this package without a story — it would require a tsconfig + type definitions for all existing JSX

## Key Patterns

Every component that fetches data must handle three states: loading, error, and populated. SSE data flows through `src/ws/` into React context (`src/context/`) — do not fetch directly from components.

CSS custom properties live in `src/index.css`. Adding a new colour means adding a `--var` there, not a hex literal anywhere in component CSS.
