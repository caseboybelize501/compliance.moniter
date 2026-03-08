# Database Migration Guide

## Overview

ACMP uses Alembic for database schema migrations with async PostgreSQL (asyncpg).

## Setup

### 1. Ensure Database is Running

```bash
# Start PostgreSQL
docker-compose up -d postgres
```

### 2. Set Environment Variable

```bash
export DATABASE_URL="postgresql+asyncpg://acmp:acmp_secret@localhost:5432/acmp"
```

## Running Migrations

### Upgrade to Latest

```bash
cd server/db/alembic
alembic upgrade head
```

### Downgrade One Version

```bash
alembic downgrade -1
```

### Downgrade to Specific Revision

```bash
alembic downgrade <revision_id>
```

### Check Current Version

```bash
alembic current
```

### Show Migration History

```bash
alembic history
```

## Creating New Migrations

### Autogenerate from Models

```bash
# Make changes to models in server/db/models/
# Then run:
cd server/db/alembic
alembic revision --autogenerate -m "Description of changes"
```

### Review Generated Migration

Always review the generated migration file in `versions/`:

```bash
# Check the generated file
cat versions/<timestamp>_<description>.py

# Look for:
# - Correct table/column names
# - Correct data types
# - Proper foreign keys
# - Indexes where needed
```

### Manual Migration

For complex migrations, write manually:

```bash
alembic revision -m "Manual migration description"
```

Then edit the generated file in `versions/`.

## Common Operations

### Create Initial Schema (Fresh Install)

```bash
# Start with clean database
docker-compose down -v postgres
docker-compose up -d postgres

# Wait for postgres to be ready
sleep 5

# Run migrations
cd server/db/alembic
alembic upgrade head
```

### Seed Initial Data

After migrations, seed frameworks:

```python
# Run in Python
from server.db.session import AsyncSessionLocal, init_db
from server.db.models import Framework

async def seed():
    async with AsyncSessionLocal() as session:
        # Add seed frameworks
        frameworks = [
            Framework(id="soc2", name="SOC 2 Type II", version="1.0.0"),
            Framework(id="hipaa", name="HIPAA", version="1.0.0"),
            Framework(id="gdpr", name="GDPR", version="1.0.0"),
            Framework(id="iso27001", name="ISO 27001:2022", version="1.0.0"),
        ]
        session.add_all(frameworks)
        await session.commit()

import asyncio
asyncio.run(seed())
```

### View Schema

```bash
# Connect to database
docker-compose exec postgres psql -U acmp -d acmp

# List tables
\dt

# Describe table
\d tenants
\d controls
\d violations
```

## Troubleshooting

### Migration Fails

1. Check database is running:
```bash
docker-compose ps postgres
```

2. Check connection:
```bash
docker-compose exec postgres psql -U acmp -d acmp -c "SELECT 1"
```

3. Check migration file for syntax errors:
```bash
python -m py_compile server/db/alembic/versions/<file>.py
```

### Autogenerate Detects No Changes

If models changed but alembic detects nothing:

1. Ensure models are imported in `env.py`
2. Check `target_metadata = Base.metadata`
3. Try manual migration instead

### Rollback Failed Migration

```bash
# Downgrade to before failed migration
alembic downgrade <previous_revision>

# Fix the migration file
# Then upgrade again
alembic upgrade head
```

## Migration Best Practices

1. **Never modify existing migrations** - Create new ones
2. **Test downgrades** - Always test `downgrade()` function
3. **Review autogenerate** - Don't trust it blindly
4. **Add data migrations** - For reference data changes
5. **Keep migrations small** - One logical change per migration
6. **Test on staging** - Before applying to production

## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| tenants | Customer organizations |
| frameworks | Compliance frameworks (SOC2, HIPAA, etc.) |
| framework_versions | Framework version history |
| controls | Individual controls within frameworks |
| control_results | Control evaluation results |
| source_profiles | Connected data sources |
| evidence_artifacts | Collected evidence |
| violations | Detected compliance violations |
| audit_logs | Audit trail |
| alembic_version | Migration version tracking |

### Key Relationships

```
tenants 1--* source_profiles
tenants 1--* evidence_artifacts
tenants 1--* control_results
tenants 1--* violations
tenants 1--* audit_logs

frameworks 1--* controls
frameworks 1--* framework_versions

controls 1--* control_results
controls 1--* violations

source_profiles 1--* evidence_artifacts
```

## Performance Considerations

### Indexes

Key indexes created by migrations:

- `ix_tenants_created_at` - Tenant listing
- `ix_evidence_artifacts_hash` - Dedup lookups
- `ix_evidence_tenant_control` - Evidence queries
- `ix_violations_tenant_status` - Violation filtering
- `ix_audit_tenant_created` - Audit queries

### Connection Pooling

Configured in `server/db/session.py`:

- Pool size: 10
- Max overflow: 20
- Pool timeout: 30s
- Pool recycle: 1800s (30 min)

## Security

### Row-Level Security

Multi-tenant isolation enforced by:

1. `tenant_id` column on all tenant-scoped tables
2. Foreign key with `ON DELETE CASCADE`
3. Application-level filtering (never trust client input)

### Audit Logging

All sensitive operations logged to `audit_logs`:

- User authentication events
- Evidence collection
- Violation changes
- Configuration changes

---

For questions, see PRODUCTION_READINESS_PLAN.md Phase 1.
