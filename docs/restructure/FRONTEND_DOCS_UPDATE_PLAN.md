# Frontend Documentation Update Plan

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** PLAN ONLY

---

## Overview

This document outlines all documentation updates required for the Clone-for-Experts restructure. Documentation is organized into:

1. **README** - Developer onboarding
2. **USER_GUIDE** - End-user documentation
3. **ONBOARDING_GUIDE** - Expert setup guide
4. **SUPPORT_RUNBOOK_UI** - Troubleshooting guide
5. **In-App Help Text** - Contextual guidance

---

## 1. README Updates

### Current Location: `frontend/README.md`

### Sections to Update

| Section | Current | New Content |
|---------|---------|-------------|
| Title | VT-BRAIN Frontend | Clone-for-Experts Frontend |
| Description | Digital Twin Brain | AI Expert Clone Platform |
| Architecture | N/A | Add section on IA (Studio/Launch/Operate) |
| Routes | N/A | Document new route structure |
| Components | N/A | Link to component inventory |
| Dev Setup | Basic | Add environment variables |

### Proposed README Structure

```markdown
# Clone-for-Experts Frontend

## Overview
Web-only AI expert clone platform for creating, deploying, and operating
conversational AI assistants trained on your expertise.

## Architecture
The application is organized into three primary areas:
- **Studio** - Build and configure your expert clone
- **Launch** - Deploy via share links and website embeds
- **Operate** - Monitor conversations and analytics

## Quick Start
1. Clone the repository
2. Install dependencies: `npm install`
3. Copy `.env.local.example` to `.env.local`
4. Start development server: `npm run dev`

## Environment Variables
See `.env.local.example` for required variables.

## Route Structure
See [FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md](../docs/restructure/FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md)

## Component Library
See [components/ui/](./components/ui/) for shared UI components.

## State Management
See [FRONTEND_STATE_MODEL.md](../docs/restructure/FRONTEND_STATE_MODEL.md)
```

---

## 2. USER_GUIDE Structure

### Proposed Location: `docs/USER_GUIDE.md`

### Full Document Outline

```markdown
# Clone-for-Experts User Guide

## Table of Contents
1. Getting Started
2. Studio: Build Your Expert
3. Launch: Deploy Your Expert
4. Operate: Run Your Expert
5. Settings
6. FAQ
7. Troubleshooting

---

## 1. Getting Started

### Creating Your Account
Step-by-step signup flow with screenshots.

### Creating Your First Expert Clone
Overview of the onboarding wizard.

### Understanding the Dashboard
Navigation overview of Studio/Launch/Operate.

---

## 2. Studio: Build Your Expert

### 2.1 Content
Managing knowledge sources:
- Uploading documents (PDF, DOCX, TXT)
- Adding website URLs
- Recording voice interviews
- Processing status indicators

### 2.2 Identity
Configuring your expert's personality:
- Name and tagline
- Tone settings (professional, friendly, casual, technical)
- Response length preferences
- System instructions (advanced)

### 2.3 Roles
Creating context-specific personas:
- Default role
- Creating new roles
- Role-specific instructions

### 2.4 Quality
Testing your expert clone:
- Running test conversations
- Understanding confidence scores
- Viewing knowledge context
- Iterating on content

---

## 3. Launch: Deploy Your Expert

### 3.1 Share Link
Creating shareable links:
- Generating your link
- Sharing via QR code
- Regenerating links
- Link analytics

### 3.2 Website Embed
Embedding on your website:
- Copying embed code
- Adding allowed domains
- Widget preview
- Installation verification

### 3.3 Branding
Customizing widget appearance:
- Primary color
- Position (bottom-right, bottom-left)
- Button icon
- Custom greeting message

---

## 4. Operate: Run Your Expert

### 4.1 Conversations
Reviewing conversations:
- Conversation list
- Message history
- Exporting conversations

### 4.2 Audience
Understanding your visitors:
- Total visitors
- Returning visitors
- Average messages per session

### 4.3 Analytics
Tracking usage metrics:
- Message volume
- Response rate
- Confidence scores
- Top questions

---

## 5. Settings

### Account Settings
- Profile information
- Password change
- Theme preferences

### Expert Settings
- Accessed via Studio > Identity

### Danger Zone
- Deleting your expert clone
- Exporting your data

---

## 6. FAQ

### Content & Knowledge
Q: What file types can I upload?
A: PDF, DOCX, TXT, and most common document formats.

Q: Can I add YouTube videos?
A: Yes, paste the YouTube URL in the content section.

### Sharing & Embedding
Q: How do I restrict which domains can embed my widget?
A: Add allowed domains in Launch > Website Embed.

### Conversations
Q: Are conversations saved?
A: Yes, all conversations are saved in Operate > Conversations.

---

## 7. Troubleshooting

Common issues and solutions.
See [SUPPORT_RUNBOOK_UI.md](./SUPPORT_RUNBOOK_UI.md) for technical troubleshooting.
```

---

## 3. ONBOARDING_GUIDE (Web-Only)

### Proposed Location: `docs/ONBOARDING_GUIDE.md`

### Full Document Outline

```markdown
# Expert Onboarding Guide

Welcome to Clone-for-Experts! This guide walks you through creating
your first AI expert clone from start to finish.

---

## Before You Begin

You'll need:
- An email address for your account
- Some content representing your expertise (documents, website, etc.)
- 15-30 minutes to complete setup

---

## Step 1: Create Your Account

1. Visit [app URL]
2. Click "Sign Up"
3. Enter your email and create a password
4. Verify your email (check inbox)
5. Complete your profile

---

## Step 2: Start the Onboarding Wizard

After signup, you'll be guided through the onboarding wizard.

### 2.1 Name Your Expert
- Choose a name that represents you or your brand
- Add a brief tagline (e.g., "Product Expert at Acme Corp")

### 2.2 Add Your First Content
Choose at least one content source:

**Option A: Upload Documents**
- Click "Upload Files"
- Select PDF, DOCX, or TXT files
- Wait for processing (usually 1-2 minutes)

**Option B: Add Website URL**
- Paste a URL containing your expertise
- We'll extract and index the content

**Option C: Record an Interview**
- Click "Start Interview"
- Speak about your expertise
- We'll transcribe and index your responses

---

## Step 3: Set Your Personality

Configure how your expert clone communicates:

### Tone
- **Professional** - Formal, business-appropriate
- **Friendly** - Warm and approachable
- **Casual** - Relaxed and conversational
- **Technical** - Detailed and precise

### Response Length
- **Concise** - Brief, to-the-point answers
- **Balanced** - Standard-length responses
- **Detailed** - Comprehensive explanations

---

## Step 4: Test Your Expert

Before going live, test your expert clone:

1. Go to Studio > Quality
2. Type a test question
3. Review the response
4. Check the confidence score
5. Iterate on content if needed

### Tips for Better Responses
- Add more content for topics with low confidence
- Use specific, clear questions for testing
- Review which sources were used

---

## Step 5: Launch

Ready to share your expert with the world!

### Option A: Share Link
1. Go to Launch > Share Link
2. Click "Generate Link"
3. Copy and share the URL

### Option B: Website Embed
1. Go to Launch > Website Embed
2. Copy the embed code
3. Paste into your website's HTML
4. Add your domain to the allowed list

---

## What's Next?

After launching:
1. Monitor conversations in Operate > Conversations
2. Track usage in Operate > Analytics
3. Add more content to improve responses
4. Customize branding in Launch > Branding

---

## Need Help?

- Check the [User Guide](./USER_GUIDE.md)
- Review [Troubleshooting](./SUPPORT_RUNBOOK_UI.md)
- Contact support at [support email]
```

---

## 4. SUPPORT_RUNBOOK_UI

### Proposed Location: `docs/SUPPORT_RUNBOOK_UI.md`

### Full Document Outline

```markdown
# UI Support Runbook

Technical troubleshooting guide for Clone-for-Experts frontend issues.

---

## Correlation ID Usage

Every API error includes a correlation ID for debugging.

### Finding the Correlation ID
1. When an error occurs, look for "Ref:" in the error message
2. Copy the correlation ID (e.g., `abc-123-def-456`)
3. Use in backend log search: `grep "abc-123-def-456" logs`

### Backend Log Command
```bash
# Search Render logs
render logs --service vtb-backend | grep "CORRELATION_ID"

# Search local logs
cat backend/logs/*.log | grep "CORRELATION_ID"
```

---

## Common Error Patterns

### ERR-001: "Failed to load sources"

**Symptom:** Content page shows error state

**Possible Causes:**
1. Backend not responding
2. Twin ID invalid
3. Auth token expired

**Debugging Steps:**
1. Check backend health: `GET /health`
2. Verify twin exists: `GET /twins/{twin_id}`
3. Check browser console for 401/403
4. Verify Supabase auth token

**Resolution:**
- If 401: User needs to re-login
- If 404: Twin was deleted, redirect to onboarding
- If 500: Check backend logs with correlation ID

---

### ERR-002: "Chat message failed"

**Symptom:** Message shows error in chat interface

**Possible Causes:**
1. Streaming connection dropped
2. OpenAI rate limit
3. No knowledge for query

**Debugging Steps:**
1. Check network tab for WebSocket/SSE errors
2. Look for `429 Too Many Requests`
3. Check if twin has any sources

**Resolution:**
- Retry the message
- Check OpenAI status page
- Add more content if confidence is low

---

### ERR-003: "Share link invalid"

**Symptom:** Visitor sees "This link is not valid"

**Possible Causes:**
1. Token was regenerated
2. Twin was deleted
3. Sharing was disabled

**Debugging Steps:**
1. Check `GET /twins/{twin_id}/share-link`
2. Verify twin exists and is active
3. Check widget_settings in twin record

**Resolution:**
- Generate new share link
- Verify twin is active

---

### ERR-004: "Widget not loading"

**Symptom:** Embedded widget doesn't appear

**Possible Causes:**
1. Domain not in allowed list
2. Script blocked by CSP
3. Wrong embed code

**Debugging Steps:**
1. Check browser console for CSP errors
2. Verify domain in allowed_domains
3. Test embed code format

**Resolution:**
- Add domain to allowed list
- Check Content-Security-Policy headers
- Regenerate embed code

---

## Status Banner Messages

| Banner | Meaning | User Action |
|--------|---------|-------------|
| "Syncing..." | Background data refresh | Wait |
| "Offline" | No internet connection | Check network |
| "Reconnecting..." | Lost connection, retrying | Wait |
| "Connection lost" | Failed to reconnect | Refresh page |
| "Update available" | New version deployed | Refresh page |

---

## Browser Compatibility

| Browser | Minimum Version | Known Issues |
|---------|-----------------|--------------|
| Chrome | 90+ | None |
| Firefox | 88+ | None |
| Safari | 14+ | SSE may need polyfill |
| Edge | 90+ | None |

---

## Performance Issues

### Slow Page Load

**Debugging:**
1. Check Network tab for slow requests
2. Look for large bundle sizes
3. Check for blocking scripts

**Common Fixes:**
- Clear browser cache
- Check backend response times
- Verify CDN status

### Chat Lag

**Debugging:**
1. Check SSE connection in Network tab
2. Look for buffering issues
3. Verify streaming endpoint

**Common Fixes:**
- Switch to different network
- Check backend streaming health

---

## Escalation Path

1. **Level 1:** User self-service (this runbook)
2. **Level 2:** Support team (correlation ID lookup)
3. **Level 3:** Engineering (backend logs + code review)

---

## Log Locations

| Log Type | Location | Access |
|----------|----------|--------|
| Frontend console | Browser DevTools | F12 |
| Backend logs | Render Dashboard | Team access |
| Supabase logs | Supabase Dashboard | Admin access |
| Pinecone logs | Pinecone Console | Admin access |
```

---

## 5. In-App Help Text Plan

### Empty State Copy

| Page | Title | Description |
|------|-------|-------------|
| Content | "No knowledge sources yet" | "Add documents, URLs, or interview recordings to train your expert." |
| Roles | "No roles defined" | "Roles let you customize responses for different contexts like sales or support." |
| Quality | "Ready to test" | "Ask your expert clone a question to see how it responds." |
| Share | "Create your share link" | "Generate a link to share your expert with anyone." |
| Conversations | "No conversations yet" | "Conversations will appear here once visitors start chatting." |
| Analytics | "No analytics yet" | "Usage data will appear after your first conversation." |

### Tooltip Text

| Element | Tooltip |
|---------|---------|
| Confidence Score | "How certain the response is based on your content (0-1)" |
| Verification Badge | "Response verified against your knowledge sources" |
| Processing Status | "Content is being indexed into your expert's knowledge" |
| Share Token | "Unique identifier for this share link" |
| Allowed Domains | "Only these domains can embed your widget" |

### Info Panels

| Page | Panel Content |
|------|---------------|
| Content | "Tip: Add diverse content for better coverage. Mix documents, websites, and interviews." |
| Identity | "Your expert's personality affects how it communicates. Choose a tone that matches your brand." |
| Embed | "Copy this code into your website's HTML, usually just before the closing </body> tag." |

---

## Documentation File Locations

| Document | Current Location | New Location (if changed) |
|----------|------------------|---------------------------|
| README | `frontend/README.md` | Keep |
| USER_GUIDE | N/A (create new) | `docs/USER_GUIDE.md` |
| ONBOARDING_GUIDE | N/A (create new) | `docs/ONBOARDING_GUIDE.md` |
| SUPPORT_RUNBOOK_UI | N/A (create new) | `docs/SUPPORT_RUNBOOK_UI.md` |
| Component Inventory | N/A (created) | `docs/restructure/FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md` |
| UX Spec | N/A (created) | `docs/restructure/FRONTEND_UX_REDESIGN_SPEC.md` |
| State Model | N/A (created) | `docs/restructure/FRONTEND_STATE_MODEL.md` |

---

## Implementation Priority

### Phase 1: Technical Docs (For Developers)
1. ✅ FRONTEND_ROUTE_AND_COMPONENT_INVENTORY.md
2. ✅ FRONTEND_UX_REDESIGN_SPEC.md
3. ✅ FRONTEND_STATE_MODEL.md
4. Update frontend/README.md

### Phase 2: User Docs (For End Users)
1. Create docs/USER_GUIDE.md
2. Create docs/ONBOARDING_GUIDE.md

### Phase 3: Support Docs
1. Create docs/SUPPORT_RUNBOOK_UI.md

### Phase 4: In-App Text
1. Update EmptyState copy
2. Add tooltips
3. Add info panels
