# YouTube HTTP 403 / 429 Fix Guide

> [!IMPORTANT]
> This document consolidates the research and multi-layer fix for YouTube bot detection issues.

## 🔴 The Problem
YouTube blocks automated requests with **HTTP 403 (Forbidden)** or **HTTP 429 (Too Many Requests)** when it detects "non-human" traffic patterns.

## ✅ The Fix: 3-Layer Fallback
The system uses a robust retrieval chain to bypass these blocks:

### Layer 1: Official Transcript API (Fastest)
- **Method**: Uses `youtube-transcript-api`.
- **Why**: Bypasses player restrictions, works in ~1s.
- **Limitation**: Only works if video has public captions.

### Layer 2: Multi-Client Audio Emulation
- **Method**: Emulates multiple player clients: `android`, `web`, `ios`.
- **Implementation**:
  ```python
  'player_client': ['android', 'web', 'ios'],
  'player_skip': ['webpage', 'configs', 'js']
  ```
- **Why**: Harder for YouTube to block all signatures simultaneously.

### Layer 3: Exponential Backoff Retry
- **Method**: Up to 5 retries with increasing delays.
- **Schedule**: 2s → 4s → 8s → 16s → 32s.
- **Why**: Allows IP reputation to recover from transient rate limits.

---

## 🛠 Troubleshooting for Users

### "HTTP 403" after 5 retries
This usually means the video has intrinsic restrictions that emulation cannot bypass:
- **Age-restricted** (18+)
- **Region-blocked**
- **Private/Deleted**

**Workarounds**:
1. **Use a public educational video** (TED-Ed, Khan Academy).
2. **Set `YOUTUBE_PROXY`** in the backend `.env` to route through a residential IP.

### "HTTP 429" (Too Many Requests)
- Wait 5-10 minutes.
- The system will automatically retry, but persistent 429s indicate the server IP is flagged.

---

## ⚙️ Configuration
| Variable | Description |
| :--- | :--- |
| `YOUTUBE_MAX_RETRIES` | Default: 5 |
| `YOUTUBE_PROXY` | Optional proxy URL |
| `YOUTUBE_COOKIES_FILE` | Path to `cookies.txt` (not recommended for containers) |
