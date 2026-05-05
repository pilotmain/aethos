/** Client-side X-User-Id rules (keep aligned with app/services/web_user_id.py). */

export const WEB_USER_ID_INVALID_MSG =
  "Invalid user id. Use an AethOS channel id: tg_<digits>, web_<label>, local_<label>, em_<hex>, " +
  "slack_<id>, sms_<digits>, wa_<digits>, or am_<hex>. Do not paste a Telegram bot token.";

export const WEB_USER_ID_FIELD_HELP =
  "Examples: tg_123456789 (Telegram), em_abcd1234… (email channel), slack_U01ABC (Slack), " +
  "sms_15551234567, wa_123456789012345, am_abcd1234… (Apple Messages), web_mydevice / local_dev.";

const _TG = /^tg_[0-9]{3,20}$/;
const _WEB = /^web_[A-Za-z0-9_-]{1,64}$/;
const _LOCAL = /^local_[A-Za-z0-9_-]{1,64}$/;
const _EM = /^em_[a-f0-9]{8,32}$/;
const _WA = /^wa_[0-9]{4,20}$/;
const _SMS = /^sms_[0-9]{4,20}$/;
const _AM = /^am_[a-f0-9]{8,32}$/;
const _SLACK = /^slack_[A-Za-z0-9]{1,64}$/;

const MAX = 80;

/**
 * Return true if the value is a valid AethOS web user id (trimmed, no colons,
 * matches an accepted channel prefix pattern — same rules as the API).
 */
export function isValidAethosWebUserId(raw: string): boolean {
  const s = raw;
  if (!s || s !== s.trim() || s.length > MAX) return false;
  if (/\s/.test(s) || s.includes(":")) return false;
  if (
    !(
      _TG.test(s) ||
      _WEB.test(s) ||
      _LOCAL.test(s) ||
      _EM.test(s) ||
      _WA.test(s) ||
      _SMS.test(s) ||
      _AM.test(s) ||
      _SLACK.test(s)
    )
  )
    return false;
  return true;
}

/** @deprecated Use ``isValidAethosWebUserId``. */
export const isValidNexaWebUserId = isValidAethosWebUserId;

/**
 * If the value is invalid, return a short reason; if valid or empty, return null.
 * Leading/trailing whitespace counts as invalid with a specific message.
 */
export function describeAethosWebUserIdProblem(raw: string): string | null {
  if (raw !== raw.trim()) return "Remove leading or trailing spaces.";
  const s = raw.trim();
  if (!s) return null;
  if (s.length > MAX) return `User id must be at most ${MAX} characters.`;
  if (/\s/.test(s)) return "User id cannot contain spaces.";
  if (s.includes(":"))
    return "User id cannot contain ':' (for example, do not paste a Telegram bot token).";
  if (isValidAethosWebUserId(s)) return null;
  return WEB_USER_ID_INVALID_MSG;
}

/** @deprecated Use ``describeAethosWebUserIdProblem``. */
export const describeNexaWebUserIdProblem = describeAethosWebUserIdProblem;

/** Message for required-but-empty user id after submit. */
export const USER_ID_REQUIRED_MSG = "Enter your AethOS user id.";
