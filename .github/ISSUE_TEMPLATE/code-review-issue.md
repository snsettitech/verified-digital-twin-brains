name: Code Review Issue
description: Track code review feedback and improvements
title: "[CODE REVIEW] "
labels: ["code-review", "feedback"]
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        # Code Review Issue Template
        Use this to track code review feedback and follow-up items.

  - type: dropdown
    id: issue-type
    attributes:
      label: Issue Type
      description: What type of code review issue is this?
      options:
        - 🔴 Critical Issue (Blocking)
        - 🟡 Warning (Should Fix)
        - 💡 Suggestion (Consider)
        - 📚 Documentation Update
        - ⚡ Performance Optimization
        - 🔒 Security Concern
      default: 0

  - type: dropdown
    id: category
    attributes:
      label: Category
      description: What category does this fall under?
      options:
        - Security / Multi-Tenancy
        - Authentication / Authorization
        - Code Quality
        - Testing
        - Documentation
        - Performance
        - Architecture
        - Database
        - Other
      default: 0

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Describe the issue or feedback
      placeholder: |
        Provide clear description of the issue.
        Include:
        - What the problem is
        - Why it matters
        - Where it is in the code
      validations:
        required: true

  - type: textarea
    id: context
    attributes:
      label: Context / Evidence
      description: Provide specific examples, line numbers, or code snippets
      placeholder: |
        Link to specific file/line:
        - File: `backend/routers/chat.py`
        - Line: 42-50
        
        Code example:
        ```python
        # Current code
        result = supabase.table("data").select("*").execute()
        ```

  - type: textarea
    id: recommendation
    attributes:
      label: Recommendation / Solution
      description: Suggest how to fix or improve this
      placeholder: |
        Here's the recommended approach:
        
        ```python
        # Improved code
        result = (supabase.table("data")
            .select("*")
            .eq("tenant_id", user["tenant_id"])
            .execute())
        ```
        
        Reference: `docs/ai/agent-manual.md`

  - type: checkbox
    id: blocking
    attributes:
      label: This issue blocks PR merge
      description: Check if this issue must be fixed before merging

  - type: textarea
    id: related-prs
    attributes:
      label: Related PRs / Issues
      description: Link any related PRs or issues
      placeholder: |
        - Related PR: #123
        - Fixes issue: #456
        - Follow-up to: #789

  - type: dropdown
    id: priority
    attributes:
      label: Priority
      description: How urgent is this?
      options:
        - 🔴 Critical (Fix immediately)
        - 🟠 High (Fix in this sprint)
        - 🟡 Medium (Fix in next sprint)
        - 🟢 Low (Nice to have)
      default: 2

  - type: dropdown
    id: effort
    attributes:
      label: Estimated Effort
      description: How much work is needed to fix?
      options:
        - "⚡ Quick (< 15 min)"
        - "🔧 Simple (15-60 min)"
        - "💼 Medium (1-4 hours)"
        - "🏗️ Complex (> 4 hours)"
      default: 1

  - type: textarea
    id: success-criteria
    attributes:
      label: Success Criteria
      description: How will we know this is fixed?
      placeholder: |
        This issue is resolved when:
        - [ ] Code change is made
        - [ ] Tests are added
        - [ ] Documentation is updated
        - [ ] Manual verification complete

  - type: textarea
    id: additional-notes
    attributes:
      label: Additional Notes
      description: Any other context or information
      placeholder: |
        - Discussed in: Team standup on 2026-02-04
        - Relates to: Multi-tenant security initiative
        - Reference docs: docs/CODE_REVIEW_GUIDELINES.md
