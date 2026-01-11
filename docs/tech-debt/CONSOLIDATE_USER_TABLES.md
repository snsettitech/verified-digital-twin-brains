# Tech Debt: Consolidate User Tables

**Created:** 2026-01-11  
**Priority:** Medium  
**Effort:** ~2-3 hours  
**Status:** Planned  

---

## Problem Statement

We currently have **two separate user-related tables** that serve overlapping purposes:

### 1. `users` Table (Primary - In Use)
Used by the multi-tenant authentication system via `/auth/sync-user`.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | Primary key, links to auth.users |
| email | text | Required |
| tenant_id | uuid | Links to tenants table (nullable) |
| role | text | User role within tenant |
| invitation_id | uuid | For invited users |
| invited_at | timestamptz | When invitation was accepted |
| last_active_at | timestamptz | Activity tracking |
| created_at | timestamptz | Account creation |

### 2. `user_profiles` Table (Legacy - Not Used in App Code)
Created by the `handle_new_user()` trigger on `auth.users` INSERT.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | Primary key, links to auth.users |
| email | text | Required |
| full_name | text | From OAuth metadata |
| avatar_url | text | From OAuth metadata |
| email_verified | boolean | Default false |
| onboarding_completed | boolean | Default false |
| onboarding_step | integer | Default 0 |
| stripe_customer_id | text | For billing |
| subscription_tier | text | Default 'free' |
| subscription_status | text | Default 'active' |
| last_login_at | timestamptz | Login tracking |
| login_count | integer | Default 0 |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

## Current Issues

1. **Data Duplication**: User data split across two tables
2. **Sync Issues**: As of 2026-01-11, we had 2 records in `users` but only 1 in `user_profiles`
3. **Maintenance Overhead**: Two tables to maintain, potential for drift
4. **Unused Fields**: `user_profiles` has billing/subscription fields not used anywhere
5. **Confusing Architecture**: New developers may not know which table to use

---

## Proposed Solution

### Option A: Merge into `users` (Recommended)

Add useful columns from `user_profiles` to `users`, update trigger, drop `user_profiles`.

**Pros:**
- `users` is already the primary table used by app code
- Maintains multi-tenant architecture
- Single source of truth

**Cons:**
- Need to migrate any existing data from `user_profiles`

### Option B: Merge into `user_profiles`

Add `tenant_id` and other columns to `user_profiles`, update app code.

**Pros:**
- `user_profiles` has more fields already

**Cons:**
- Would require updating all backend code that references `users`
- Higher risk of breaking changes

---

## Implementation Plan (Option A)

### Phase 1: Schema Migration

```sql
-- 1. Add missing columns to users table
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS full_name text,
    ADD COLUMN IF NOT EXISTS avatar_url text,
    ADD COLUMN IF NOT EXISTS onboarding_completed boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS onboarding_step integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS stripe_customer_id text,
    ADD COLUMN IF NOT EXISTS subscription_tier text DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS subscription_status text DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS login_count integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- 2. Migrate existing data from user_profiles to users
UPDATE users u
SET 
    full_name = COALESCE(u.full_name, up.full_name),
    avatar_url = COALESCE(u.avatar_url, up.avatar_url),
    onboarding_completed = COALESCE(up.onboarding_completed, false),
    onboarding_step = COALESCE(up.onboarding_step, 0),
    stripe_customer_id = up.stripe_customer_id,
    subscription_tier = COALESCE(up.subscription_tier, 'free'),
    subscription_status = COALESCE(up.subscription_status, 'active'),
    login_count = COALESCE(up.login_count, 0)
FROM user_profiles up
WHERE u.id = up.id;
```

### Phase 2: Update Trigger Function

```sql
-- Replace handle_new_user to insert into users instead
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $function$
DECLARE
    new_tenant_id uuid;
BEGIN
    -- Create default tenant
    INSERT INTO tenants (owner_id, name)
    VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)) || '''s Workspace')
    RETURNING id INTO new_tenant_id;
    
    -- Create user record
    INSERT INTO users (id, email, full_name, avatar_url, tenant_id)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', ''),
        NEW.raw_user_meta_data->>'avatar_url',
        new_tenant_id
    );
    
    -- Log signup event
    INSERT INTO user_events (user_id, event_type, event_data)
    VALUES (NEW.id, 'signup', jsonb_build_object('provider', NEW.raw_app_meta_data->>'provider'));
    
    RETURN NEW;
END;
$function$;
```

### Phase 3: Update Backend Code

Update `/auth/sync-user` endpoint to handle existing users who already have records (from trigger):

```python
# In routers/auth.py - sync_user function
# Check if user was created by trigger (has record in users)
# If yes, just return existing user
# Remove duplicate tenant creation logic
```

### Phase 4: Cleanup

```sql
-- Drop the legacy table
DROP TABLE IF EXISTS user_profiles;

-- Update RLS policies if needed
```

---

## Files to Update

| File | Changes Needed |
|------|----------------|
| `backend/routers/auth.py` | Update sync_user to not duplicate trigger logic |
| `backend/modules/auth_guard.py` | May need to update user fetching |
| `backend/migrations/` | Add consolidation migration |
| Database trigger | Update `handle_new_user()` |

---

## Testing Checklist

- [ ] Existing users can still log in
- [ ] New OAuth signups work correctly
- [ ] Tenant creation still happens on first signup
- [ ] User profile data (name, avatar) is preserved
- [ ] Subscription fields are accessible
- [ ] No duplicate user/tenant records created
- [ ] RLS policies work correctly

---

## Rollback Plan

1. Keep `user_profiles` table backup before dropping
2. Store original `handle_new_user()` function definition
3. Can recreate table and restore trigger if needed

---

## Related Files

- `backend/database/migrations/migration_fix_oauth_user_creation.sql` - Previous OAuth fix
- `backend/migrations/create_metrics_tables.sql` - Contains user_profiles creation
- `docs/ops/OAUTH_DATABASE_ERROR_FIX.md` - OAuth troubleshooting docs
