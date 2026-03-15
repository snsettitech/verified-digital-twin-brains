# Documentation Archive

This directory contains historical documentation, implementation summaries, audit reports, and planning documents that are no longer actively maintained but preserved for reference.

## Directory Structure

```
docs/archive/
├── audits/           # Historical audit reports
├── implementation/   # Completed implementation summaries
├── plans/           # Historical planning documents
├── repo-cleanup/     # Intermediate cleanup working notes
├── proof/           # Verification and proof artifacts
│   ├── logs/        # Proof logs
│   ├── json/        # Proof JSON outputs
│   ├── screenshots/ # Proof screenshots
│   └── html/        # Proof HTML outputs
└── proof_outputs/   # AI improvement proof outputs
```

## Purpose

The documents in this archive represent:

1. **Completed work** - Implementation summaries and completion reports for finished features
2. **Historical audits** - Security, performance, and code audits from past phases
3. **Planning documents** - Plans and specifications for completed or superseded features
4. **Proof artifacts** - Verification outputs, test results, and manual testing evidence
5. **Cleanup working notes** - Intermediate repository-cleanup drafts superseded by root deliverables

## Current Documentation

For current, actively maintained documentation, see:

- `docs/quick-start.md` - Essential setup guide
- `docs/ops/` - Operations runbooks
- `docs/ai/` - AI agent manual
- `AGENTS.md` - Agent coding guidelines
- `CONTRIBUTING.md` - Contribution guidelines

## Adding to Archive

When archiving documents:

1. Move to appropriate subdirectory based on document type
2. Update any internal links to point to new location
3. Ensure no runtime code depends on archived documents
4. Do not archive currently active runbooks or operational docs

## Retention Policy

Archived documents are retained indefinitely for:
- Historical context
- Decision archaeology
- Compliance and audit trails
- Knowledge preservation
