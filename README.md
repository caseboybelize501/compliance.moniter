# ACMP — Autonomous Compliance Monitoring Platform

> **Open Source First** - All core dependencies are open source. Proprietary APIs (OpenAI, Okta, Slack) are optional and user-provided.

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
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add these to your `.env` file.

### 3. Choose your stack

**Basic (PostgreSQL + Minio + Redis):**
```bash
docker-compose up -d
```

**With Local LLM (vLLM - requires NVIDIA GPU):**
```bash
docker-compose --profile llm up -d
```

**With Keycloak Authentication:**
```bash
docker-compose --profile auth up -d
```

**CPU-Only LLM (Ollama instead of vLLM):**
```bash
docker-compose --profile ollama up -d
```

**Full Stack:**
```bash
docker-compose --profile llm --profile auth --profile monitoring up -d
```

### 4. Configure your sources

Add at least one cloud provider to `.env`:

```bash
# AWS (read-only SecurityAudit policy)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### 5. Verify API

```bash
curl http://localhost:8000/health
```

### 6. View control matrix

```bash
curl http://localhost:8000/api/controls?framework=soc2
```

## Architecture

### Core Stack (Open Source)

```
┌─────────────────────────────────────────────────────────────────┐
│  Connectors → Engine → API → Dashboard                          │
│     │           │                                               │
│     ▼           ▼                                               │
│  PostgreSQL   Minio (S3)                                        │
│  (metadata)   (artifacts)                                       │
│                                                                 │
│  Redis (Celery)  vLLM/Ollama (LLM)  Keycloak (Auth)            │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Options

| Component | Default | Alternatives |
|-----------|---------|--------------|
| **Database** | PostgreSQL | Supabase |
| **LLM** | vLLM (self-hosted) | Ollama, OpenAI (user key) |
| **Auth** | Keycloak | Direct JWT, Okta, Azure AD |
| **Messaging** | WhatsApp (Twilio) | Slack, Teams |
| **Storage** | Minio | AWS S3, GCP GCS |

## Proprietary APIs (Optional, User-Provided)

All proprietary services are **opt-in**. Users provide their own credentials:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| **OpenAI** | LLM for remediation suggestions | $5 trial credits |
| **Twilio** | WhatsApp/SMS alerts | Free trial available |
| **Slack** | Slack alerts | Free tier |
| **Okta** | Identity evidence (optional) | Free developer org |

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

## Troubleshooting

### vLLM not starting (GPU issues)

If you don't have an NVIDIA GPU, use Ollama instead:

```bash
# Stop vLLM
docker-compose --profile llm down

# Start Ollama
docker-compose --profile ollama up -d
```

Update `.env`:
```bash
LLM_PROVIDER=ollama
LLM_API_BASE=http://localhost:11434/v1
```

### Sources not connecting

1. Verify credentials in `.env`
2. Check logs: `docker-compose logs api`
3. Verify network access to source APIs

### Evidence not collecting

1. Check worker logs: `docker-compose logs worker`
2. Verify Redis is running: `docker-compose ps redis`

## License

Proprietary. All rights reserved.
