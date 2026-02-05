name: Bug Report
description: Report a bug found during code review or testing
title: "[BUG] "
labels: ["bug", "needs-investigation"]
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        # Bug Report Template
        Report bugs found during development, testing, or code review.

  - type: dropdown
    id: severity
    attributes:
      label: Severity
      description: How critical is this bug?
      options:
        - 🔴 Critical (System broken / Data loss)
        - 🟠 High (Major feature broken)
        - 🟡 Medium (Feature partially broken)
        - 🟢 Low (Minor issue / Workaround exists)
      default: 2

  - type: dropdown
    id: area
    attributes:
      label: Area Affected
      description: Which area is affected?
      options:
        - Backend API
        - Frontend UI
        - Database / Data
        - Authentication
        - Chat / AI
        - Knowledge Management
        - Performance
        - Infrastructure / DevOps
        - CI/CD
        - Other
      default: 0

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Clearly describe the bug
      placeholder: |
        What is the bug?
        What did you expect?
        What actually happened?
      validations:
        required: true

  - type: textarea
    id: steps-to-reproduce
    attributes:
      label: Steps to Reproduce
      description: Provide step-by-step instructions
      placeholder: |
        1. Navigate to page X
        2. Click button Y
        3. Enter value Z
        4. Observe unexpected behavior
      validations:
        required: true

  - type: textarea
    id: expected-behavior
    attributes:
      label: Expected Behavior
      description: What should happen instead?
      placeholder: |
        The system should...

  - type: textarea
    id: actual-behavior
    attributes:
      label: Actual Behavior
      description: What actually happens?
      placeholder: |
        Instead, the system...

  - type: textarea
    id: error-logs
    attributes:
      label: Error Logs / Stack Trace
      description: Include relevant error logs or stack traces
      placeholder: |
        ```
        Error: [error message]
        at [function] ([file]:[line])
        ```

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: Describe the environment where bug occurs
      placeholder: |
        - OS: Windows 11 / MacOS / Linux
        - Browser: Chrome 120
        - Backend: Python 3.12
        - Frontend: Node 20
        - Deployed on: Render / Vercel / Local

  - type: textarea
    id: screenshots
    attributes:
      label: Screenshots / Video
      description: Add screenshots or screen recording if helpful
      placeholder: |
        ![Screenshot](url)

  - type: textarea
    id: workaround
    attributes:
      label: Workaround (if any)
      description: Is there a workaround for this issue?
      placeholder: |
        If you found a workaround, describe it here.
        This helps other users while waiting for a fix.

  - type: textarea
    id: related-issues
    attributes:
      label: Related Issues / PRs
      description: Link any related issues or PRs
      placeholder: |
        - Related to issue #123
        - Caused by PR #456
        - Might fix #789

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: I've checked if this bug already exists
          required: true
        - label: I've provided clear reproduction steps
          required: true
        - label: I've included relevant error logs
        - label: I've identified the affected area

---

name: Feature Request
description: Request a new feature or enhancement
title: "[FEATURE] "
labels: ["enhancement", "feature-request"]
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        # Feature Request Template
        Suggest a new feature or enhancement to improve the system.

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Describe the feature or enhancement
      placeholder: |
        What would you like to add or improve?
        Why is this needed?
      validations:
        required: true

  - type: textarea
    id: use-case
    attributes:
      label: Use Case / Motivation
      description: Explain the use case and why this is important
      placeholder: |
        Currently, users/system needs to...
        With this feature, we could...
      validations:
        required: true

  - type: textarea
    id: proposed-solution
    attributes:
      label: Proposed Solution
      description: How would you solve this?
      placeholder: |
        Describe your proposed approach or implementation.

  - type: textarea
    id: alternatives
    attributes:
      label: Alternative Approaches
      description: Are there other ways to solve this?
      placeholder: |
        We could also...
        However, this approach is better because...

  - type: dropdown
    id: priority
    attributes:
      label: Priority
      description: How important is this feature?
      options:
        - 🔴 Critical (Blocks other work)
        - 🟠 High (Important for roadmap)
        - 🟡 Medium (Nice to have)
        - 🟢 Low (Would be good someday)
      default: 2

  - type: dropdown
    id: effort
    attributes:
      label: Estimated Effort
      description: How much work would this take?
      options:
        - "⚡ Quick (< 1 day)"
        - "🔧 Small (1-3 days)"
        - "💼 Medium (1-2 weeks)"
        - "🏗️ Large (> 2 weeks)"
      default: 1

  - type: textarea
    id: related-issues
    attributes:
      label: Related Issues / Features
      description: Link any related issues or features
      placeholder: |
        - Related to issue #123
        - Complements feature #456
        - Blocks feature #789
