# Social media automation

Nexa can **post** and **read** on selected platforms behind explicit flags and credentials. This is **operator-controlled** automation — always respect each platform’s Terms of Service and rate limits.

## Feature matrix

| Platform | Post | Read / search | Notes |
|----------|------|-----------------|-------|
| **Twitter / X** | OAuth 1.0a user keys | Bearer token (`recent` search, user tweets) | Write uses four OAuth1 env vars; read uses `TWITTER_BEARER_TOKEN`. |
| **LinkedIn** | UGC Posts API | — | Text share only; needs person URN. |
| **Facebook Page** | Graph `/{page-id}/feed` | — | Page access token + page id. |
| **Instagram** | Graph `/{ig-user-id}/media` → `media_publish` | — | **Phase 24** — feed **photo**, **video** (public `https` URL), or **carousel** (multiple image URLs). Requires Business/Creator IG account linked to a Facebook Page, and a Page access token with `instagram_content_publish` (or equivalent). Image/video URLs must be **publicly fetchable** by Meta. |
| **TikTok** | Content Posting API **Direct Post** (`/v2/post/publish/video/init/` + chunked PUT) | — | **Phase 24** — API downloads the first `media_urls` entry (must be **https**), then uploads via `FILE_UPLOAD`. Scope: `video.upload` (and publish as required by your app). Unaudited apps are often limited to `TIKTOK_PRIVACY_LEVEL=SELF_ONLY`. |

## Configuration

See `app/core/config.py`. Typical env (all optional until enabled):

- **`NEXA_SOCIAL_ENABLED`** — master switch (default `false`).
- **`NEXA_TWITTER_ENABLED`**, **`NEXA_LINKEDIN_ENABLED`**, **`NEXA_FACEBOOK_ENABLED`**, **`NEXA_INSTAGRAM_ENABLED`**, **`NEXA_TIKTOK_ENABLED`** — per network.
- **Twitter**: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` (post); `TWITTER_BEARER_TOKEN` (read/search).
- **LinkedIn**: `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN` (`urn:li:person:…`).
- **Facebook**: `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`.
- **Instagram**: `INSTAGRAM_BUSINESS_ACCOUNT_ID` (IG user id), `INSTAGRAM_PAGE_ACCESS_TOKEN` optional — if unset, **`FACEBOOK_PAGE_ACCESS_TOKEN`** is used (same Page token pattern as Meta docs).
- **TikTok**: `TIKTOK_ACCESS_TOKEN`, optional `TIKTOK_OPEN_ID`, **`TIKTOK_PRIVACY_LEVEL`** (`SELF_ONLY`, `PUBLIC_TO_EVERYONE`, … — must match creator options from TikTok).
- **`NEXA_SOCIAL_RATE_LIMIT_PER_HOUR`** — minimum spacing between orchestrated calls (default `50`/hour).
- **`NEXA_SOCIAL_MAX_MEDIA_SIZE_MB`** — max download size for TikTok path (and safety cap); Instagram uses publicly hosted URLs only.

Outbound hosts used by these clients should appear in **`NEXA_NETWORK_ALLOWED_HOSTS`** when egress is allowlisted (defaults include `graph.facebook.com`, `graph.instagram.com`, `open.tiktokapis.com`, `open-upload.tiktokapis.com`). For **TikTok**, the video file is downloaded from whatever host you put in `media_urls[0]` — add that **CDN hostname** to the allowlist or use **`NEXA_NETWORK_EGRESS_MODE=open`** only in trusted dev environments.

## REST API

Prefix: **`/api/v1/social`**.

Authentication: **`Authorization: Bearer <NEXA_CRON_API_TOKEN>`** (same as cron / browser / scraping).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/post` | JSON `{ "platform": "twitter"|…, "content": "…", "media_urls?": ["https://…"], "reply_to?": "tweet_id" }` |
| GET | `/posts/{platform}/{user_id}` | Recent tweets (Twitter numeric user id) |
| GET | `/search/{platform}?q=…&limit=…` | Recent search (Twitter; API tier may limit) |

### Instagram `POST /post`

- **`platform`**: `"instagram"`
- **`content`**: caption (and TikTok title).
- **`media_urls`**: one public **https** image URL (single photo); one **https** video URL for feed video (`.mp4`/`.mov` hint or rely on URL); **multiple** URLs for a **carousel** (images only in this implementation).

### TikTok `POST /post`

- **`platform`**: `"tiktok"`
- **`content`**: caption / title (maps to TikTok `post_info.title`).
- **`media_urls`**: **required** — first entry must be an **https** URL to a video file Nexa can download (subject to egress allowlist and `NEXA_SOCIAL_MAX_MEDIA_SIZE_MB`).

Returns **503** when `NEXA_SOCIAL_ENABLED=false`.

## Telegram

- **`/tweet <message>`** — posts to Twitter/X when Twitter + social flags and OAuth1 keys are set.
- **`/search_tweets <query>`** — recent search (Bearer).

## Safety

- Keep tokens out of logs and git; use env / secret stores only.
- Rate limiting is **best-effort** in-process; platform quotas still apply.
- Do not use automation for spam or policy-violating behavior.
