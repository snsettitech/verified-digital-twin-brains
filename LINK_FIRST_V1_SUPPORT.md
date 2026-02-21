# Link-First Persona Compiler v1 Support Matrix

**Version:** v1.0.0  
**Date:** 2026-02-20  
**Status:** Production Ready

---

## Ingestion Mode Support

### Mode A: Export Upload (Supported)

| Format | Extension | Source Type | Parser Used |
|--------|-----------|-------------|-------------|
| LinkedIn Data Export | `.zip`, `.csv` | Export | `export_parsers.py:parse_linkedin_export()` |
| Twitter/X Archive | `.zip`, `.js` | Export | `export_parsers.py:parse_twitter_archive()` |
| PDF Documents | `.pdf` | Document | Existing `ingestion.py` |
| HTML Pages | `.html`, `.htm` | Export | `export_parsers.py:parse_html_content()` |

**Important:** LinkedIn and X/Twitter are ONLY supported via export upload. Direct crawling is NOT supported in v1.

### Mode B: Paste/Import (Supported)

| Input Type | Max Size | Processing |
|------------|----------|------------|
| Plain Text Paste | 100KB | Direct to `process_and_index_text()` |
| DOCX Upload | 50MB | Existing `ingestion.py:ingest_file()` |
| Markdown | 10MB | Direct processing |
| Private Slack/Discord Export | 50MB | `export_parsers.py:parse_slack_export()` |

### Mode C: Web Fetch (Restricted)

| Domain Category | Status | Requirements |
|-----------------|--------|--------------|
| Personal Blogs | ✅ Allowed | robots.txt compliant, allowlisted |
| GitHub README | ✅ Allowed | Public repos only, rate limited |
| Company Websites | ✅ Allowed | robots.txt compliant, allowlisted |
| News Articles | ✅ Allowed | robots.txt compliant, allowlisted |
| **LinkedIn** | ❌ **BLOCKED** | Use Mode A (Export Upload) |
| **X/Twitter** | ❌ **BLOCKED** | Use Mode A (Export Upload) |
| **Facebook** | ❌ **BLOCKED** | Not supported in v1 |
| **Instagram** | ❌ **BLOCKED** | Not supported in v1 |

---

## Domain Allowlist (Mode C)

Default allowed domains for web fetch:

```
github.com
gist.github.com
medium.com
substack.com
*.medium.com
*.substack.com
*.github.io
*.vercel.app
*.netlify.app
```

**Configuration:** Add domains via `LINK_FIRST_ALLOWLIST` env var (comma-separated).

---

## Rate Limits (Mode C)

| Operation | Limit | Window |
|-----------|-------|--------|
| Web Fetch Requests | 1 | per 2 seconds |
| Max Content Size | 5MB | per fetch |
| robots.txt Cache | 1 hour | TTL |
| Total Daily Fetches | 100 | per twin |

---

## Claim Types Supported

| Type | Description | Example |
|------|-------------|---------|
| `preference` | Stated preferences | "I prefer B2B over B2C" |
| `belief` | Core beliefs | "Team quality is most important" |
| `heuristic` | Decision frameworks | "When evaluating, I look at..." |
| `value` | Priority values | "Speed matters more than perfection" |
| `experience` | Past experiences | "In 2020, I learned that..." |
| `boundary` | Hard boundaries | "I don't invest in crypto" |

---

## v1 Limitations & Deferred Features

| Feature | Status | Planned Version |
|---------|--------|-----------------|
| LinkedIn API Integration | ❌ Not in v1 | v2 (if API access granted) |
| X/Twitter API Integration | ❌ Not in v1 | v2 (if API access granted) |
| Contradiction Detection | ⚠️ Deferred | v1.1 |
| Multi-language Claims | ⚠️ English only | v1.1 |
| Automatic Claim Refresh | ⚠️ Manual only | v2 |
| Cross-Source Claim Merge | ⚠️ Not supported | v1.1 |

---

## Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| `LINK_CRAWL_BLOCKED` | robots.txt disallows | Use Mode B (Paste) |
| `LINK_DOMAIN_NOT_ALLOWED` | Domain not in allowlist | Add to allowlist or use Mode A/B |
| `LINK_RATE_LIMITED` | Rate limit hit | Wait and retry |
| `LINK_LINKEDIN_BLOCKED` | LinkedIn crawling blocked | Use LinkedIn Export (Mode A) |
| `LINK_TWITTER_BLOCKED` | Twitter crawling blocked | Use Twitter Archive (Mode A) |
| `LINK_CONTENT_TOO_LARGE` | Content exceeds 5MB | Split into smaller chunks |
| `LINK_PARSE_FAILED` | Could not parse content | Try different format |

---

**End of Support Matrix**
