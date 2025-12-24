---
description: How to create a new specialization module (e.g., VC Brain, Legal Brain)
---

# Creating a New Specialization

Follow these steps to add a new specialization variant to the platform.

## Prerequisites
- Understand the Strategy Pattern used in `backend/modules/specializations/`
- Review existing specializations (vanilla, vc) for patterns

## Steps

### 1. Create Specialization Config

```bash
cd backend/modules/specializations
mkdir <name>
touch <name>/__init__.py <name>/config.py
```

Create `config.py`:
```python
from ..base import Specialization

class <Name>Specialization(Specialization):
    name = "<name>"
    display_name = "<Display Name>"
    
    def get_system_prompt(self, twin):
        return """Your specialized prompt here..."""
    
    def get_default_triggers(self):
        return []  # Add relevant triggers
    
    def get_sidebar_config(self):
        return {"sections": []}  # Define sidebar structure
    
    def get_feature_flags(self):
        return {**super().get_feature_flags()}
```

### 2. Register Specialization

Edit `backend/modules/specializations/registry.py`:
```python
from .<name>.config import <Name>Specialization

_REGISTRY: Dict[str, Type[Specialization]] = {
    # ... existing
    "<name>": <Name>Specialization,
}
```

### 3. Create Tests

Create `backend/tests/specializations/test_<name>.py`:
```python
import pytest
from modules.specializations.<name>.config import <Name>Specialization

def test_system_prompt():
    spec = <Name>Specialization()
    prompt = spec.get_system_prompt({})
    assert "<key term>" in prompt

def test_feature_flags():
    spec = <Name>Specialization()
    flags = spec.get_feature_flags()
    assert flags["actions_engine"] == True
```

### 4. Update Documentation

- Add to CLAUDE.md under "Specializations" section
- Update ROADMAP.md if this is a new phase

### 5. Test Locally

```bash
# Run with new specialization
SPECIALIZATION=<name> python main.py

# Run tests
SPECIALIZATION=<name> pytest tests/specializations/test_<name>.py
```

### 6. Environment Variables

Create `.env.<name>` for specialization-specific config:
```
SPECIALIZATION=<name>
SUPABASE_URL=<specialization-specific-url>
PINECONE_INDEX=<name>-index
```

## Checklist Before PR

- [ ] Config class implements all abstract methods
- [ ] Registered in registry.py
- [ ] Tests pass: `pytest tests/specializations/test_<name>.py`
- [ ] CLAUDE.md updated
- [ ] No modifications to core modules (only extensions)
- [ ] Code follows CODING_STANDARDS.md
