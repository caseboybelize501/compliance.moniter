# ACMP — Original Requirements Specification

> **Autonomous Compliance Monitoring Platform**
> 
> "Continuously monitors infra, code, and data flows against SOC2/HIPAA/GDPR/ISO27001, auto-collects evidence, flags violations, and generates audit-ready packages — turning a 6-month crisis into a weekly report"

---

## The Problem

Compliance audits cost **$50-200k** and **six months of engineering time**, every single year, for the same 200 controls. Access logs, encryption configs, incident records, change management evidence — all collected manually by engineers who have other jobs.

**ACMP Solution:** Connects to your infra and code stack, continuously monitors every control, auto-collects evidence as it happens, and surfaces violations weeks before an auditor would. Audit prep goes from a fire drill to a dashboard export.

---

## System Prompt

Build a continuous compliance monitoring SaaS:

```
Connectors pull from cloud infra + code + identity
  → ControlEngine maps evidence to framework controls
  → ViolationDetector flags gaps
  → EvidenceStore packages audit artifacts
  → ReportGenerator produces auditor-ready output
  → RemediationAgent suggests fixes

Multi-tenant, self-hostable, framework-agnostic.
```

---

## Hard Requirements

### HR-01: Source Bootstrap

Scan environment for credentials:

| Category | Environment Variables |
|----------|----------------------|
| Cloud Infra | `AWS_ACCESS_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `AZURE_CLIENT_ID` |
| Code Repos | `GITHUB_TOKEN`, `GITLAB_TOKEN` |
| Identity | `OKTA_TOKEN`, `AZURE_AD_CLIENT_ID` |
| Ticketing | `JIRA_TOKEN`, `LINEAR_TOKEN` |
| Communications | `SLACK_TOKEN` |

**Probe each source. Write SourceProfile. ≥1 cloud source required. Nothing proceeds until validated.**

### HR-02: Dedup

Evidence keyed by `(control_id + source + artifact_hash)`. **Never re-collect unchanged artifacts.**

### HR-03: Framework Required

≥1 active compliance framework before monitoring starts. **Seed: SOC2 Type II control set included.**

---

## Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | Connect to ≥1 cloud provider (AWS/GCP/Azure) |
| FR-02 | Connect to ≥1 identity provider (Okta/Azure AD/Google) |
| FR-03 | Connect to code repos (GitHub/GitLab) |
| FR-04 | Map collected artifacts to compliance framework controls |
| FR-05 | Detect control violations with severity classification |
| FR-06 | Store timestamped evidence with source provenance |
| FR-07 | Generate auditor-ready evidence packages (PDF + CSV) |
| FR-08 | Alert on new violations via Slack / email / webhook |
| FR-09 | Track remediation of violations to closure |
| FR-10 | Support multiple frameworks per tenant (SOC2+HIPAA etc) |
| FR-11 | Multi-tenant with strict data isolation |
| FR-12 | Continuous monitoring — not point-in-time snapshots |

---

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | All evidence stored encrypted at rest (AES-256) |
| NFR-02 | Audit log of every evidence collection event |
| NFR-03 | Self-hostable — no customer data leaves their network |
| NFR-04 | Evidence collection must not require elevated permissions (read-only IAM) |
| NFR-05 | Framework control mapping is versioned + auditable |
| NFR-06 | API rate limits respected on all source connectors |

---

## Compliance Frameworks (Seed, Extensible)

| Framework | Controls | Notes |
|-----------|----------|-------|
| SOC2 Type II | 64 controls | Across 5 Trust Services Criteria |
| HIPAA | 54 safeguards | PHI scope flags |
| GDPR | 42 controls | Article-mapped |
| ISO27001:2022 | 93 controls | Annex A controls |
| Custom | Tenant-defined | Extensible |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SOURCES              PIPELINE                    OUTPUTS       │
│                                                                 │
│  AWS/GCP/Azure─┐   ┌──────────────────────┐   Dashboard        │
│  GitHub/GitLab─┤   │  ConnectorManager    │   Violation Alerts │
│  Okta/Azure AD─┼──▶│  EvidenceCollector   │──▶ Evidence Pkgs   │
│  Jira/Linear  ─┤   │  ControlEngine       │   Audit Reports    │
│  Slack        ─┘   │  ViolationDetector   │   Remediation Tasks│
│                     │  EvidenceStore       │                    │
│                     │  ReportGenerator     │                    │
│                     │  RemediationAgent    │                    │
│                     └──────────────────────┘                    │
│                           │          │                          │
│                      PostgreSQL    S3/Minio                     │
│                      (controls)    (artifacts)                  │
└─────────────────────────────────────────────────────────────────┘
```

### Source Bootstrap Details

| Source | Validation |
|--------|------------|
| AWS | `boto3 → sts:GetCallerIdentity → list regions + services` → verify read-only: SecurityAudit or custom least-priv |
| GCP | `google-auth → cloudresourcemanager.projects.list` |
| Azure | `MSAL → subscriptions/list` |
| GitHub | `GET /user + /orgs → repo list + webhook setup` |
| Okta | `GET /api/v1/users` (read-only token) |
| Jira | `GET /rest/api/3/myself → project list` |
| Slack | `auth.test → channel list` (evidence of comms controls) |

**Register:** `{ source, type, scope, read_only: bool, confirmed }`  
**Write SourceProfile → unlock pipeline**

---

## Module Dependencies

| Module | Depends On | Depended On By |
|--------|------------|----------------|
| `connector_manager` | source credentials, httpx | evidence_collector |
| `evidence_collector` | connector_manager | control_engine |
| `control_engine` | evidence_collector, framework_registry | violation_detector, report_generator |
| `framework_registry` | PostgreSQL, seed data | control_engine |
| `violation_detector` | control_engine, rules_engine | alert_dispatcher, remediation_agent |
| `evidence_store` | S3/Minio, PostgreSQL | report_generator, control_engine |
| `alert_dispatcher` | violation_detector | [external: Slack/email/webhook] |
| `remediation_agent` | violation_detector, LLM | [API + workers] |
| `report_generator` | control_engine, evidence_store | [API] |
| `api_server` | all engine modules | [dashboard] |
| `workers` | all engine modules, Celery | [cron + events] |

---

## Files Per Module

### connectors/

| File | Purpose |
|------|---------|
| `base.py` | abstract Connector + EvidenceArtifact types |
| `aws.py` | boto3: IAM, CloudTrail, Config, S3, RDS |
| `gcp.py` | google-api: IAM, audit logs, GCS, KMS |
| `azure.py` | MSAL + Graph: RBAC, policy, key vault |
| `github.py` | repos, branch protection, secret scanning |
| `gitlab.py` | projects, protected branches, CI config |
| `okta.py` | users, groups, MFA status, sessions |
| `azure_ad.py` | users, conditional access, MFA enforcement |
| `jira.py` | issues: change tickets, incident records |
| `slack.py` | channels, retention policy, DLP config |
| `connector_manager.py` | registry + SourceProfile + delta sync |

### engine/

| File | Purpose |
|------|---------|
| `evidence_collector.py` | orchestrate per-control artifact fetch |
| `control_engine.py` | map artifacts → controls → pass/fail |
| `framework_registry.py` | load/version frameworks + control defs |
| `violation_detector.py` | evaluate controls → severity + evidence |
| `rules_engine.py` | pluggable rule evaluation per control type |
| `evidence_store.py` | S3 upload + PostgreSQL metadata + encrypt |
| `alert_dispatcher.py` | Slack/email/webhook on new violations |
| `remediation_agent.py` | LLM: violation → suggested fix steps |
| `report_generator.py` | control matrix → PDF + CSV audit package |

### frameworks/

| File | Purpose |
|------|---------|
| `soc2.json` | 64 controls, TSC mappings, evidence types |
| `hipaa.json` | 54 safeguards, PHI scope flags |
| `gdpr.json` | 42 controls, DPA article references |
| `iso27001.json` | 93 Annex A controls |
| `loader.py` | parse + validate + version framework files |

### server/

| Path | Purpose |
|------|---------|
| `main.py` | FastAPI application |
| `api/controls.py` | GET control matrix + per-control status |
| `api/violations.py` | GET active violations + history |
| `api/evidence.py` | GET artifacts, GET audit package download |
| `api/remediation.py` | GET suggestions, POST acknowledge/complete |
| `api/frameworks.py` | CRUD frameworks + custom controls |
| `api/integrations.py` | source status + manual sync trigger |
| `api/reports.py` | POST generate, GET download |
| `api/alerts.py` | GET alert history + POST snooze |
| `api/auth.py` | JWT + API key + tenant scope |
| `models/control.py` | Control + EvidenceArtifact + ControlResult |
| `models/violation.py` | Violation + Severity + RemediationStatus |
| `models/framework.py` | Framework + FrameworkVersion schema |
| `models/tenant.py` | Tenant + subscription + source config |
| `workers/collection_worker.py` | Celery: per-source evidence collection |
| `workers/evaluation_worker.py` | Celery: control re-evaluation on new ev |
| `workers/report_worker.py` | Celery: async report generation |
| `workers/alert_worker.py` | Celery: violation → dispatch |

### dashboard/src/pages/

| File | Purpose |
|------|---------|
| `ControlMatrix.jsx` | framework view: all controls + pass/fail |
| `ViolationFeed.jsx` | active violations + severity + age |
| `EvidenceViewer.jsx` | per-control artifact browser |
| `AuditPackage.jsx` | generate + download audit report |
| `RemediationBoard.jsx` | violations → tasks → completion tracking |
| `Integrations.jsx` | source health + collection cadence |

---

## Task Scheduler (Celery Beat)

| Schedule | Task | Target |
|----------|------|--------|
| Every 15 min | `collect_evidence_delta` | all active sources |
| Every 1 hr | `evaluate_all_controls` | per tenant |
| Every 6 hr | `scan_iam_permissions` | AWS/GCP/Azure |
| Every 24 hr | `scan_encryption_config` | all infra sources |
| Every 24 hr | `scan_branch_protection` | GitHub/GitLab |
| Every 24 hr | `scan_mfa_compliance` | Okta/Azure AD |
| Every 7 days | `generate_scheduled_reports` | tenants with auto-report |
| On violation | `dispatch_alert` | immediate, async |
| On new evidence | `re_evaluate_control` | affected control only |

### Priority Queues (Celery)

| Queue | Priority | Tasks |
|-------|----------|-------|
| `high` | 10 | violation alerts, on-demand report generation |
| `default` | 5 | scheduled evidence collection, control evaluation |
| `low` | 1 | historical re-evaluation, cross-control correlation |

### Rate Limiting (per connector, enforced in base.py)

| Connector | Rate Limit |
|-----------|------------|
| AWS | 10 req/s (respect AWS API rate limits) |
| GitHub | 5000 req/hr authenticated (track X-RateLimit headers) |
| Okta | 600 req/min (org-level limit) |

---

## Test Requirements

### Unit Tests

| Test | Assertions |
|------|------------|
| `test_evidence_store.py` | → assert artifact stored + encrypted + retrievable<br>→ assert dedup: identical artifact_hash → no duplicate<br>→ assert metadata: source, control_id, timestamp present |
| `test_control_engine.py` | → assert SOC2 CC6.1 maps to MFA artifact from Okta connector<br>→ assert PASS when MFA enabled for all users<br>→ assert FAIL + severity=HIGH when MFA missing for admin |
| `test_violation_detector.py` | → assert violation created on control FAIL<br>→ assert no duplicate violation for same control in 1hr window<br>→ assert severity escalation: 3+ related violations → CRITICAL |
| `test_framework_registry.py` | → assert SOC2 seed loads with 64 controls<br>→ assert version bump on framework edit<br>→ assert custom control appends without replacing seed |
| `test_rules_engine.py` | → assert each rule type evaluates deterministically<br>→ assert unknown rule type raises FrameworkError |

### Integration Tests

| Test | Mock | Assertion |
|------|------|-----------|
| `test_aws_connector.py` | mock boto3 | assert IAM evidence |
| `test_github_connector.py` | mock GitHub API | assert branch rules |
| `test_okta_connector.py` | mock Okta | assert MFA artifact |
| `test_full_pipeline.py` | seed source | collect → eval → violate |

### API Tests

| Test | Endpoint | Assertion |
|------|----------|-----------|
| `test_controls_api.py` | GET /controls | returns matrix |
| `test_violations_api.py` | GET /violations | filters by severity |
| `test_evidence_api.py` | GET /evidence/:id | returns artifact |
| `test_reports_api.py` | POST /reports | job_id → poll → PDF |
| `test_auth.py` | auth endpoints | invalid token → 401, wrong tenant→403 |

### Coverage Target

**≥ 80% line coverage** on `engine/` and `connectors/`

### Mocking Strategy

- All external APIs mocked via pytest fixtures
- **NO live cloud credentials in test suite**

---

## Self-Repair Loop

### Trigger Conditions

| Code | Condition |
|------|-----------|
| T1 | test failure after code generation |
| T2 | import error in generated module |
| T3 | type mismatch between module interfaces |
| T4 | missing method called by dependent module |
| T5 | connector returns unexpected schema from live API |

### Repair Loop (max 3 iterations before human escalation)

1. **DETECT** — run pytest → capture failing test + traceback
2. **LOCALIZE** — identify file + function + line from traceback
3. **CONTEXT** — load: failing file + test + interface contract from `models/` (Pydantic schemas as ground truth)
4. **REPAIR** — LLM prompt: *"File: {path}\nError: {traceback}\nInterface contract: {schema}\nFix only the failing function. Return full corrected file. No explanation."*
5. **APPLY** — overwrite file with LLM output
6. **VERIFY** — re-run failing test only
7. **REGRESS** — run full test suite — no new failures allowed
8. **LOOP** — if still failing → iteration + 1; if iteration = 3 → write `REPAIR_FAILED.md` + halt

### Interface Contracts (Ground Truth)

**All Pydantic models in `server/models/` are written FIRST and treated as immutable during repair.** The repair loop fixes implementations to match contracts — never the reverse.

### Repair Scope Limits

- → Only modify the single file identified in traceback
- → Never modify: `models/`, `frameworks/*.json`, `base.py`
- → If fix requires changing a contract → escalate, do not modify

---

## Pricing

| Tier | Price | Features |
|------|-------|----------|
| **Starter** | $800/mo | 1 framework, 2 cloud sources, 5 users |
| **Growth** | $4,000/mo | all frameworks, all sources, 20 users |
| **Scale** | $10,000/mo | unlimited, custom controls, SSO, audit SLA |

**Metered:** evidence artifacts stored + audit reports generated

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Connectors** | boto3, google-api-python-client, MSAL, PyGithub |
| **Engine** | Python, pydantic, reportlab (PDF), openpyxl (CSV) |
| **LLM** | configurable: OpenAI / Anthropic / local (remediation) |
| **Storage** | PostgreSQL + Minio (S3-compatible, self-hosted) |
| **Encryption** | cryptography (Fernet AES-256 for evidence at rest) |
| **Queue** | Celery + Redis |
| **Frontend** | React, Recharts, react-pdf-viewer |
| **Infra** | Docker Compose, fully self-hosted |

---

## Required Files

- `docker-compose.yml`
- `.env.example`
- `README.md`

### README.md Spec

```markdown
# ACMP — Autonomous Compliance Monitoring Platform

## Quickstart
cp .env.example .env   # add AWS_ACCESS_KEY + GITHUB_TOKEN min
docker-compose up -d
GET /api/integrations → confirm sources connected
GET /api/controls     → first control matrix (populates in ~5min)

## Minimum IAM Permissions (AWS)
Attach: SecurityAudit managed policy (read-only, AWS-managed)
Or custom: iam:List*, cloudtrail:Describe*, config:Get*

## Add a Framework
SOC2 + HIPAA seeded. POST /api/frameworks with custom JSON spec

## Generate Audit Package
POST /api/reports { framework_id, period_start, period_end }
Returns: PDF evidence summary + CSV control matrix + artifact ZIP
```

---

## Key API Contracts

### GET /api/controls?framework=soc2&status=fail

```json
{
  "controls": [
    {
      "id": "CC6.1",
      "name": "Logical Access - Authentication",
      "status": "FAIL",
      "severity": "HIGH",
      "evidence_count": 5,
      "last_evaluated_at": "2024-01-15T10:30:00Z",
      "violation_id": "v_abc123"
    }
  ]
}
```

### GET /api/violations?severity=high&status=open

```json
{
  "violations": [
    {
      "id": "v_abc123",
      "control_id": "CC6.1",
      "description": "MFA not enabled for 3 admin users",
      "severity": "HIGH",
      "opened_at": "2024-01-15T10:30:00Z",
      "age_days": 5,
      "remediation_suggestion": "Enable MFA for all admin users..."
    }
  ]
}
```

### POST /api/reports

**Request:**
```json
{
  "framework_id": "soc2",
  "period_start": "2024-01-01",
  "period_end": "2024-03-31",
  "format": "pdf|csv|zip"
}
```

**Response:**
```json
{
  "report_id": "rpt_xyz789",
  "status": "generating",
  "estimated_s": 30
}
```

### GET /api/reports/:id/download

→ binary file (PDF/CSV/ZIP)

### POST /api/remediation/:violation_id/complete

**Request:**
```json
{
  "evidence_note": "MFA enabled for all admins",
  "artifact_url": "https://..."
}
```

**Response:**
```json
{
  "stored": true,
  "control_re_evaluated": true
}
```

---

## Document Control

| Version | Date | Description |
|---------|------|-------------|
| 1.0 | Original | Initial requirements specification |

---

**This document serves as the ground truth for ACMP development. All implementations must align with these requirements.**
