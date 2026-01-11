---
description: Pre-commit code review checklist before pushing to git
---

# Pre-Commit Code Review Workflow

Always complete these steps before committing/pushing code changes.

## 1. Syntax Check
```bash
# Verify Python files compile
python -m py_compile <modified_files>
```

## 2. Import Check  
```bash
# Verify all imports work
cd backend
python -c "import <module_name>"
```

## 3. Lint Check
```bash
# Run flake8 on modified files (max line length 150)
python -m flake8 <modified_files> --max-line-length=150 --ignore=E402
```

## 4. Common Issues to Check
- [ ] No duplicate imports (F811)
- [ ] Imports actually used (F401) - or ignore if needed elsewhere
- [ ] No trailing whitespace (W291, W293)
- [ ] Two blank lines before function definitions (E302, E305)
- [ ] Line length under 150 characters (E501)
- [ ] Two spaces before inline comments (E261)

## 5. Authorization Check (Security)
For any API endpoint:
- [ ] Does it verify user ownership before returning data?
- [ ] Does it use `verify_owner` or `verify_twin_ownership`?
- [ ] Are there any endpoints that expose data without auth?

## 6. Edge Cases
- [ ] Are optional parameters handled correctly?
- [ ] Is there proper error handling with try/except?
- [ ] Are async functions properly awaited?

## 7. Run Tests (if available)
```bash
pytest tests/ -v
```

## 8. Commit with Descriptive Message
```bash
git add <files>
git commit -m "type: descriptive message"
git push
```

> **Note**: If autopep8 is available, you can auto-fix many issues:
> ```bash
> python -m autopep8 --in-place --aggressive --max-line-length=150 <files>
> ```
