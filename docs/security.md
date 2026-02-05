# Security Checklist

> Security requirements and validation for the Digital Brain MVP.

## Authentication & Authorization

### JWT Validation
- [ ] **JWT signature validation**: Verify using Supabase's public key
- [ ] **JWT expiration check**: Reject expired tokens
- [ ] **JWT issuer validation**: Confirm issuer matches Supabase project
- [ ] **Token refresh**: Handle token refresh flow correctly

### Multi-Tenant Isolation
- [ ] **tenant_id from JWT only**: Never accept tenant_id from request body
- [ ] **RLS policies active**: All tables have row level security enabled
- [ ] **RLS default deny**: Policies deny by default, explicitly allow
- [ ] **Service role key restricted**: Only used in background jobs, never in user requests
- [ ] **Cross-tenant test**: Automated tests verify tenant isolation

### Pinecone Isolation
- [ ] **Namespace required**: All queries include namespace
- [ ] **Namespace format**: `{tenant_id}:{twin_id}` enforced
- [ ] **No namespace bypass**: Cannot query without namespace filter

---

## Database Security

### Row Level Security Policies

| Table | SELECT | INSERT | UPDATE | DELETE |
|-------|--------|--------|--------|--------|
| tenants | Own tenant | ❌ | Own tenant | ❌ |
| users | Own tenant | On signup | Own user | ❌ |
| twins | Own tenant | Own tenant | Own twin | Own twin |
| documents | Own tenant | Own tenant | Own doc | Own doc |
| conversations | Own tenant | Own tenant | ❌ | ❌ |
| messages | Own tenant | Own tenant | ❌ | ❌ |
| graph_nodes | Own tenant | Own tenant | Own nodes | Own nodes |
| graph_edges | Own tenant | Own tenant | Own edges | Own edges |
| memory_candidates | Own tenant | Own tenant | Own tenant | Own tenant |
| escalations | Own tenant | Own tenant | Own tenant | Own tenant |

### Policy Examples
```sql
-- Example: twins table
CREATE POLICY "select_own_tenant_twins" ON twins
FOR SELECT USING (tenant_id = auth.jwt() ->> 'tenant_id');

CREATE POLICY "insert_own_tenant_twins" ON twins
FOR INSERT WITH CHECK (
    tenant_id = auth.jwt() ->> 'tenant_id'
    AND owner_id = auth.uid()
);
```

### Service Role Key Usage
```
✅ Allowed:
- User sync trigger from auth.users
- Background processing jobs
- Admin dashboard (internal only)

❌ Forbidden:
- Any user-facing API endpoint
- Frontend application
- Public-facing services
```

---

## API Security

### Input Validation
- [ ] **Pydantic models**: All inputs validated via Pydantic
- [ ] **Max lengths**: String fields have max length limits
- [ ] **UUID validation**: All ID fields validated as UUIDs
- [ ] **Enum validation**: Status fields use enums

### Rate Limiting
- [ ] **Auth endpoints**: 10 requests/minute per IP
- [ ] **Chat endpoint**: 30 requests/minute per user
- [ ] **Upload endpoint**: 10 requests/minute per user
- [ ] **Global limit**: 1000 requests/minute per IP

### CORS Configuration
```python
CORS_ORIGINS = [
    "https://digitalbrain.app",       # Production
    "https://*.vercel.app",           # Preview deploys
    "http://localhost:3000",           # Local dev
]
```

### Headers
- [ ] **Content-Security-Policy**: Set appropriately
- [ ] **X-Content-Type-Options**: nosniff
- [ ] **X-Frame-Options**: DENY
- [ ] **Strict-Transport-Security**: max-age=31536000

---

## LLM Security

### Prompt Injection Prevention
- [ ] **System/user separation**: Clear delineation in prompts
- [ ] **Input sanitization**: Remove potential injection patterns
- [ ] **Output validation**: Validate structured outputs match schema

### Data Leakage Prevention
- [ ] **No cross-tenant context**: Context only from user's twin
- [ ] **PII handling**: Minimize PII in prompts
- [ ] **Logging**: Don't log sensitive content

### Cost Protection
- [ ] **Token limits**: Max tokens per request
- [ ] **Rate limits**: Max requests per user/day
- [ ] **Cost alerts**: Monitor API costs

---

## Data Protection

### At Rest
- [ ] **Database encryption**: Supabase manages encryption at rest
- [ ] **Backup encryption**: Automated encrypted backups

### In Transit
- [ ] **HTTPS only**: All connections use TLS 1.2+
- [ ] **No HTTP redirects**: Force HTTPS
- [ ] **Certificate validation**: All external calls validate certs

### Access Logging
- [ ] **API access logs**: All requests logged
- [ ] **Auth events**: Login/logout logged
- [ ] **Data access**: DB queries logged (production: sample only)

---

## Secrets Management

### Required Secrets
| Secret | Where Used | Rotation |
|--------|------------|----------|
| SUPABASE_URL | Backend | N/A |
| SUPABASE_ANON_KEY | Frontend/Backend | N/A |
| SUPABASE_SERVICE_ROLE_KEY | Backend (restricted) | N/A |
| OPENAI_API_KEY | Backend | 90 days |
| PINECONE_API_KEY | Backend | 90 days |
| LANGFUSE_SECRET_KEY | Backend | 90 days |

### Secret Storage
- [ ] **Environment variables**: Never in code
- [ ] **Vercel secrets**: Frontend environment
- [ ] **Render secrets**: Backend environment
- [ ] **No .env in git**: .env in .gitignore

---

## Security Testing

### Automated Tests
```python
# test_security.py

def test_cross_tenant_access_blocked():
    """Verify user A cannot access user B's data"""
    twin_a = create_twin(auth_header(tenant="A"))
    
    response = client.get(f"/api/twins/{twin_a.id}", 
        headers=auth_header(tenant="B"))
    assert response.status_code == 404

def test_unauthenticated_access_blocked():
    """Verify all endpoints require auth"""
    endpoints = ["/api/twins", "/api/auth/me"]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401

def test_rls_prevents_direct_access():
    """Verify RLS works even with direct DB access"""
    with supabase_client(anon_key) as client:
        client.set_auth(user_a_token)
        
        # Try to access user B's data directly
        result = client.from_("twins").select("*").eq("id", twin_b_id).execute()
        assert len(result.data) == 0
```

### Manual Security Audit
- [ ] Review all RLS policies
- [ ] Test service role key restrictions
- [ ] Verify CORS configuration
- [ ] Check for exposed secrets
- [ ] Validate rate limiting

---

## Incident Response

### Security Incidents
1. **Detection**: Monitor logs for suspicious activity
2. **Containment**: Revoke affected tokens/keys
3. **Investigation**: Analyze logs and impact
4. **Recovery**: Patch vulnerability, restore service
5. **Documentation**: Post-mortem and lessons learned

### Key Actions
- [ ] Incident response runbook documented
- [ ] Key rotation procedure documented
- [ ] User notification template ready
- [ ] Recovery backup tested
