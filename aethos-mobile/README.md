# AethOS Mobile (Phase 30)

React Native client for Mission Control, workspaces (RBAC), chat (WebSocket stub), and profile.

## Prerequisites

- Node 18+
- For device builds: Xcode (iOS) / Android SDK. This repo ships **TypeScript sources** only; native `android/` and `ios/` folders are produced by the React Native CLI template.

## Bootstrap native projects (recommended)

From the repo root:

```bash
cd nexa-mobile
npm install
npx react-native init AethOSMobileTmp --version 0.73.11 --skip-install
# Copy generated android/ and ios/ from AethOSMobileTmp into nexa-mobile/, then merge package.json scripts if needed.
rm -rf AethOSMobileTmp
```

Alternatively use [Expo](https://docs.expo.dev/) prebuild after copying the `app/` tree.

## Configure API URL

Point the app at your AethOS API (defaults to `http://localhost:8000`). For a physical device, use your machine's LAN IP.

Set the host in `app/utils/constants.ts` (`API_BASE_URL`, default `http://localhost:8000`), or add a small Metro/Babel env integration later.

Backend requirements:

- `NEXA_SECRET_KEY` set (JWT signing for `POST /api/v1/mobile/auth/login`)
- Optional: `NEXA_RBAC_ENABLED=true` for workspace tagging (same user ids as Telegram)

## Scripts

| Script | Purpose |
|--------|---------|
| `npm run start` | Metro bundler |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run android` / `npm run ios` | Requires native folders |

## WebSocket chat

Connects to `ws(s)://<host>/api/v1/mobile/ws/chat?token=<jwt>`. The server currently echoes JSON; replace with AethOS gateway streaming when wiring production chat.
