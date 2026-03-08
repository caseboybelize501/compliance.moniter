-- ACMP Database Initialization Script

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'starter',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Frameworks table
CREATE TABLE IF NOT EXISTS frameworks (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(20) NOT NULL,
    is_custom BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Controls table
CREATE TABLE IF NOT EXISTS controls (
    id VARCHAR(50) PRIMARY KEY,
    framework_id VARCHAR(50) REFERENCES frameworks(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    evidence_types JSONB,
    rule_type VARCHAR(50),
    rule_config JSONB,
    severity VARCHAR(20) DEFAULT 'MEDIUM',
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Source profiles table
CREATE TABLE IF NOT EXISTS source_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    scope JSONB,
    read_only BOOLEAN DEFAULT TRUE,
    validated BOOLEAN DEFAULT FALSE,
    last_sync TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(20) DEFAULT 'pending',
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Evidence metadata table
CREATE TABLE IF NOT EXISTS evidence_meta (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    control_id VARCHAR(50) REFERENCES controls(id),
    source_id UUID REFERENCES source_profiles(id),
    artifact_hash VARCHAR(64) NOT NULL,
    s3_key VARCHAR(500),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(control_id, source_id, artifact_hash)
);

-- Control results table
CREATE TABLE IF NOT EXISTS control_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    control_id VARCHAR(50) REFERENCES controls(id),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    evidence_count INTEGER DEFAULT 0,
    confidence VARCHAR(20),
    details JSONB,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Violations table
CREATE TABLE IF NOT EXISTS violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    control_id VARCHAR(50) REFERENCES controls(id),
    control_result_id UUID REFERENCES control_results(id),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'OPEN',
    remediation_suggestion TEXT,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE,
    closure_reason TEXT
);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_evidence_meta_control ON evidence_meta(control_id);
CREATE INDEX IF NOT EXISTS idx_evidence_meta_tenant ON evidence_meta(tenant_id);
CREATE INDEX IF NOT EXISTS idx_control_results_control ON control_results(control_id);
CREATE INDEX IF NOT EXISTS idx_control_results_tenant ON control_results(tenant_id);
CREATE INDEX IF NOT EXISTS idx_violations_control ON violations(control_id);
CREATE INDEX IF NOT EXISTS idx_violations_tenant ON violations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_violations_status ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_severity ON violations(severity);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_source_profiles_tenant ON source_profiles(tenant_id);

-- Insert seed frameworks
INSERT INTO frameworks (id, name, version, is_custom) VALUES
    ('soc2', 'SOC 2 Type II', '1.0.0', FALSE),
    ('hipaa', 'HIPAA', '1.0.0', FALSE),
    ('gdpr', 'GDPR', '1.0.0', FALSE),
    ('iso27001', 'ISO 27001:2022', '1.0.0', FALSE)
ON CONFLICT (id) DO NOTHING;
