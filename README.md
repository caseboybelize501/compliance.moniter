# ACMP — Autonomous Compliance Monitoring Platform

Continuously monitors infra, code, and data flows against SOC2/HIPAA/GDPR/ISO27001,
auto-collects evidence, flags violations, and generates audit-ready packages.

## Quickstart

### 1. Clone and configure

```bash
git clone <repository-url>
cd compliance.moniter
cp .env.example .env
```

### 2. Generate required secrets

```bash
# Generate encryption key (32-byte Fernet key)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add these to your `.env` file.

### 3. Configure minimum sources

At minimum, add one cloud provider to `.env`:

```bash
# AWS (recommended)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### 4. Start all services

```bash
docker-compose up -d
```

### 5. Verify sources connected

```bash
curl http://localhost:8000/api/integrations
```

### 6. View first control matrix

```bash
curl http://localhost:8000/api/controls?framework=soc2
```

Controls will populate in ~5 minutes after first evidence collection.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Connectors → Engine → API → Dashboard                          │
│     │           │                                               │
│     ▼           ▼                                               │
│  PostgreSQL   Minio (S3)                                        │
│  (metadata)   (artifacts)                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Minimum IAM Permissions (AWS)

Attach the **SecurityAudit** managed policy (AWS-managed, read-only).

Or use this custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:List*",
        "iam:Get*",
        "cloudtrail:Describe*",
        "config:Describe*",
        "s3:Get*",
        "s3:List*",
        "rds:Describe*"
      ],
      "Resource": "*"
    }
  ]
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/controls` | GET | Control matrix, filter by `?framework=soc2&status=fail` |
| `/api/violations` | GET | Active violations, filter by `?severity=high&status=open` |
| `/api/evidence/:id` | GET | Artifact metadata |
| `/api/evidence/:id/download` | GET | Download artifact |
| `/api/reports` | POST | Generate audit package |
| `/api/reports/:id/download` | GET | Download PDF/CSV/ZIP |
| `/api/frameworks` | POST | Add custom framework |
| `/api/integrations` | GET | Source connection status |

## Add a Framework

SOC2, HIPAA, GDPR, and ISO27001 are seeded by default.

Add custom frameworks:

```bash
curl -X POST http://localhost:8000/api/frameworks \
  -H "Content-Type: application/json" \
  -d '{"name": "Custom Framework", "controls": [...]}'
```

## Generate Audit Package

```bash
curl -X POST http://localhost:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "framework_id": "soc2",
    "period_start": "2024-01-01",
    "period_end": "2024-03-31",
    "format": "zip"
  }'
```

## Troubleshooting

### Sources not connecting

1. Verify credentials in `.env`
2. Check logs: `docker-compose logs api`
3. Verify network access to source APIs

### Evidence not collecting

1. Check worker logs: `docker-compose logs worker`
2. Verify Redis is running: `docker-compose ps redis`

## License

Proprietary. All rights reserved.
