# Coding Standards & Quality Guidelines

Follow these standards for all code in the Verified Digital Twin Brain and VCBrain projects.

## 1. Code Quality Rules

### Python (Backend)
- **Type hints required** on all function signatures
- **Docstrings required** on all public functions/classes
- **PEP 8 compliance** - use `black` formatter
- **Max function length**: 50 lines (break into smaller functions)
- **Max file length**: 500 lines (split into modules)

### TypeScript (Frontend)
- **Explicit types** - avoid `any` unless absolutely necessary
- **Components < 200 lines** - extract sub-components
- **Props interfaces** - define all component props
- **Hooks in separate files** when reusable

## 2. Architecture Patterns

### Strategy Pattern (Specializations)
```python
# ✅ CORRECT: Use specialization interface
spec = get_specialization()
prompt = spec.get_system_prompt(twin)

# ❌ WRONG: Scattered conditionals
if os.getenv("SPECIALIZATION") == "vc":
    prompt = vc_prompt
else:
    prompt = vanilla_prompt
```

### Composition Over Inheritance
```python
# ✅ CORRECT: Compose behaviors
class VCSpecialization(Specialization):
    deal_flow = DealFlowService()
    
# ❌ WRONG: Deep inheritance chains
class VCSpecialization(AdvancedSpecialization(BaseSpecialization)):
```

## 3. File Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Python modules | snake_case | `actions_engine.py` |
| TypeScript components | PascalCase | `Sidebar.tsx` |
| TypeScript hooks | camelCase with `use` | `useSpecialization.ts` |
| CSS modules | kebab-case | `sidebar-styles.module.css` |
| Config files | lowercase | `config.py`, `.env` |

## 4. Git Commit Standards

### Format
```
<type>: <short description>

<body - what and why>
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code restructuring
- `docs:` Documentation
- `test:` Tests
- `chore:` Maintenance

### Examples
```
feat: Add VC Brain specialization module

- Implement Strategy Pattern for specializations
- Add VCSpecialization with deal flow triggers
- Create specialization registry and loader
```

## 5. Testing Requirements

### Required Coverage
- **All new modules**: Unit tests
- **API endpoints**: Integration tests
- **Specializations**: Behavior tests per variant

### Test File Location
```
backend/
├── tests/
│   ├── test_actions_engine.py
│   ├── test_specializations.py
│   └── specializations/
│       └── test_vc.py
```

## 6. Documentation Requirements

### When to Update Docs
- **New module created** → Update CLAUDE.md
- **New API endpoint** → Add to API docs
- **New database table** → Add to schema docs
- **Architecture change** → Update ARCHITECTURE.md

### Inline Comments
```python
# ✅ CORRECT: Explain WHY, not WHAT
# Skip embeddings for very short chunks as they produce poor similarity scores
if len(chunk) < 50:
    continue

# ❌ WRONG: Explains WHAT (obvious from code)
# If chunk length is less than 50, continue
if len(chunk) < 50:
    continue
```

## 7. Security Checklist

Before committing, verify:
- [ ] No secrets in code (use env vars)
- [ ] No PII logged
- [ ] SQL injection protected (parameterized queries)
- [ ] Auth/authorization checked
- [ ] Input validation on all endpoints

## 8. Specialization Development Rules

When adding new specialization:
1. **Create config class** extending `Specialization`
2. **Register in registry.py**
3. **Add tests** in `tests/specializations/`
4. **Document** in CLAUDE.md
5. **Never modify core** - only extend via interfaces
