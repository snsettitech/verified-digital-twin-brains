# Twin Naming Guidelines

**Version**: 1.0  
**Date**: 2026-02-11  
**Status**: Phase 1 Complete  

---

## Overview

This document defines naming conventions for Digital Twins following the creator-advisor platform architecture pattern.

**Namespace Format**: `creator_{creator_id}_twin_{twin_name}`

**Example**: `creator_sainath.no.1_twin_executive_coach`

---

## Naming Principles

### 1. Descriptive Over Cryptic

✅ **GOOD**: `executive_coach`, `sales_assistant`, `technical_writer`  
❌ **BAD**: `twin1`, `bot_a`, `assistant_123`

### 2. Role-Based Naming

Use the twin's primary role or function:

| Role | Good Name | Bad Name |
|------|-----------|----------|
| Executive Coach | `executive_coach` | `coach` |
| Sales Assistant | `sales_assistant` | `sales_bot` |
| Technical Writer | `technical_writer` | `writer_v2` |
| Customer Support | `customer_support` | `support` |
| Personal Assistant | `personal_assistant` | `pa` |

### 3. Consistent Separator

Use **underscores** (`_`) as separators:

✅ `customer_support_agent`  
❌ `customer-support-agent`  
❌ `customerSupportAgent`

### 4. Short but Clear

Aim for 2-4 words maximum:

✅ `executive_coach`, `sales_assistant`, `content_strategist`  
❌ `executive_leadership_coach_for_tech_ceos`  
❌ `sales`

---

## Naming Patterns by Use Case

### Personal Twins

For individuals creating twins of themselves:

| Pattern | Example | When to Use |
|---------|---------|-------------|
| `{role}` | `executive_coach` | Single primary role |
| `{role}_{specialization}` | `executive_coach_tech` | Specialized role |
| `{domain}_coach` | `leadership_coach` | Domain-specific |

**Examples**:
- `executive_coach` - General executive coaching
- `executive_coach_tech` - Tech industry executive coaching
- `leadership_coach` - Leadership development focus
- `career_coach` - Career transition coaching
- `wellness_coach` - Health and wellness coaching

### Business Twins

For business applications:

| Pattern | Example | When to Use |
|---------|---------|-------------|
| `{function}_assistant` | `sales_assistant` | Support role |
| `{function}_agent` | `support_agent` | Autonomous agent |
| `{department}_lead` | `marketing_lead` | Department head |

**Examples**:
- `sales_assistant` - Sales support and CRM
- `customer_support` - Customer service
- `marketing_strategist` - Marketing planning
- `hr_assistant` - Human resources support
- `technical_writer` - Documentation creation

### Content Twins

For content creation:

| Pattern | Example | When to Use |
|---------|---------|-------------|
| `{medium}_creator` | `video_creator` | Content creation |
| `{medium}_writer` | `blog_writer` | Written content |
| `{domain}_expert` | `finance_expert` | Domain expertise |

**Examples**:
- `blog_writer` - Blog post creation
- `social_media_manager` - Social content
- `video_script_writer` - Video scripts
- `research_analyst` - Research and analysis
- `finance_expert` - Financial advice

### Specialized Twins

For specific domains:

| Domain | Examples |
|--------|----------|
| **Legal** | `legal_researcher`, `contract_reviewer` |
| **Medical** | `medical_researcher`, `health_advisor` |
| **Technical** | `code_reviewer`, `devops_assistant` |
| **Education** | `tutor_math`, `curriculum_designer` |
| **Creative** | `story_writer`, `brand_strategist` |

---

## Reserved Names

These names are reserved for system use:

| Reserved Name | Purpose |
|---------------|---------|
| `default` | System default namespace |
| `system` | Internal system operations |
| `admin` | Administrative functions |
| `test` | Testing environments |
| `temp` | Temporary data |

**Note**: Using reserved names will result in validation errors.

---

## Validation Rules

### Automatic Validation

All twin names are validated against these rules:

```python
VALID_TWIN_NAME = r'^[a-z][a-z0-9_]{2,63}$'
```

**Rules**:
1. **Lowercase only**: `executive_coach` not `Executive_Coach`
2. **Start with letter**: `coach_1` not `1_coach`
3. **Alphanumeric + underscore**: `exec_coach_v2` 
4. **Length**: 3-64 characters
5. **No consecutive underscores**: `exec_coach` not `exec__coach`
6. **No trailing underscore**: `coach` not `coach_`

### Reserved Word Check

Names cannot match reserved words:

```python
RESERVED_NAMES = {'default', 'system', 'admin', 'test', 'temp', 'null'}
```

### Uniqueness

Twin names must be unique within a creator's namespace:

✅ Different creators can have `executive_coach`  
❌ Same creator cannot have two `executive_coach` twins

---

## Migration from Legacy Names

### Legacy UUID Namespaces

**Before**: `5698a809-87a5-4169-ab9b-c4a6222ae2dd`

**After**: `creator_sainath.no.1_twin_executive_coach`

### Migration Strategy

When migrating existing twins:

1. **Identify purpose**: Analyze the twin's content to determine role
2. **Choose semantic name**: Use guidelines above
3. **Map in database**: Update Supabase `twins` table
4. **Migrate vectors**: Use migration scripts
5. **Update references**: Update any hardcoded namespace references

### Migration Examples

| Legacy UUID | Semantic Name | Rationale |
|-------------|---------------|-----------|
| `5698a809-...` | `executive_coach` | Coaching content identified |
| `d080d547-...` | `sales_assistant` | Sales training materials |
| `eeeed554-...` | `content_creator` | Content strategy focus |
| `ad1eeace-...` | `technical_writer` | Technical documentation |

---

## Best Practices

### 1. Plan Before Creating

Before creating a twin, ask:
- What is the primary role?
- What domain does it serve?
- Will I need multiple similar twins?

### 2. Use Hierarchical Naming

If you need multiple related twins:

```
creator_sainath.no.1_twin_coach_executive
creator_sainath.no.1_twin_coach_career
creator_sainath.no.1_twin_coach_leadership
```

Not:
```
creator_sainath.no.1_twin_exec_coach
creator_sainath.no.1_twin_career_help
creator_sainath.no.1_twin_lead_guru
```

### 3. Versioning (If Needed)

For iterations of the same twin:

```
creator_sainath.no.1_twin_sales_assistant_v2
```

**Note**: Prefer creating new twins over versioning when possible.

### 4. Document Your Names

Keep a registry of your twin names:

```yaml
twins:
  executive_coach:
    purpose: "Executive coaching for tech leaders"
    created: "2026-02-11"
    sources: ["coaching_transcripts", "leadership_articles"]
    
  sales_assistant:
    purpose: "Sales enablement and CRM support"
    created: "2026-02-11"
    sources: ["sales_playbooks", "crm_data"]
```

---

## Examples by Creator Type

### Individual Creator (sainath.no.1)

| Twin Name | Purpose |
|-----------|---------|
| `executive_coach` | Personal brand as coach |
| `content_strategist` | Content creation twin |
| `speaker_prep` | Keynote preparation |

### Business Account (acme_corp)

| Twin Name | Purpose |
|-----------|---------|
| `customer_support` | 24/7 customer service |
| `sales_assistant` | Sales team support |
| `hr_onboarding` | Employee onboarding |
| `it_helpdesk` | Internal IT support |

### Educational Institution (uni_edu)

| Twin Name | Purpose |
|-----------|---------|
| `admissions_counselor` | Student admissions |
| `career_advisor` | Career services |
| `tutor_math` | Math tutoring |
| `research_assistant` | Research support |

---

## API Usage

### Creating a Twin with Semantic Name

```python
POST /twins
{
  "name": "executive_coach",
  "creator_id": "sainath.no.1",
  "description": "Executive coaching for tech leaders",
  "specialization": "leadership"
}
```

### Resulting Namespace

```
creator_sainath.no.1_twin_executive_coach
```

### Querying

```python
POST /advisor/search
{
  "query": "How to handle team conflict?",
  "creator_id": "sainath.no.1",
  "twin_id": "executive_coach",
  "top_k": 10
}
```

---

## Validation API

### Check Name Availability

```python
GET /twins/validate-name?name=executive_coach&creator_id=sainath.no.1

Response:
{
  "valid": true,
  "available": true,
  "suggested_namespace": "creator_sainath.no.1_twin_executive_coach"
}
```

### Validation Errors

```python
GET /twins/validate-name?name=Exec_Coach&creator_id=sainath.no.1

Response:
{
  "valid": false,
  "error": "Name must be lowercase",
  "suggestion": "executive_coach"
}
```

---

## Quick Reference

### Do's ✅

- Use descriptive, role-based names
- Keep it short (2-4 words)
- Use underscores for separation
- Start with a letter
- Plan your naming scheme ahead

### Don'ts ❌

- Use UUIDs or random strings
- Use camelCase or PascalCase
- Use hyphens or spaces
- Start with numbers
- Use reserved words
- Create overly long names

---

## FAQ

**Q: Can I rename a twin after creation?**  
A: Yes, but it requires migrating all vectors to the new namespace. Use the migration script.

**Q: What if I have multiple twins with similar roles?**  
A: Use hierarchical naming: `coach_executive`, `coach_career`, `coach_leadership`

**Q: Can I use numbers in names?**  
A: Yes, but not at the start: `coach_v2` is OK, `2_coach` is not.

**Q: What about special characters?**  
A: Only underscores allowed. No hyphens, spaces, or other characters.

**Q: How long can names be?**  
A: 3-64 characters. Aim for 20 or less for readability.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-11 | Initial guidelines after Phase 1 migration |

---

**Questions?** See `PRODUCTION_MIGRATION_GUIDE.md` or contact the platform team.
