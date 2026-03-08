"""
Remediation Agent for ACMP.

LLM-powered remediation suggestions.
Supports vLLM (default), Ollama, and OpenAI.
"""
import logging
from typing import Any

import httpx

from server.models.violation import Violation


logger = logging.getLogger(__name__)


class RemediationAgentError(Exception):
    """Base exception for remediation agent errors."""
    pass


class RemediationAgent:
    """
    Generates remediation suggestions using LLM.
    
    Supported providers:
    - vLLM (self-hosted, default)
    - Ollama (self-hosted, CPU-friendly)
    - OpenAI (user-provided API key)
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.provider = self.config.get("llm_provider", "vllm")
        self._http_client: httpx.AsyncClient | None = None
        
        # Provider configuration
        self.api_base = self.config.get(
            "llm_api_base",
            "http://localhost:8001/v1"  # vLLM default
        )
        self.model = self.config.get(
            "llm_model",
            "mistralai/Mistral-7B-Instruct-v0.2"
        )
        self.api_key = self.config.get("openai_api_key", "sk-no-key-required")
        
        # Control-specific remediation templates
        self.remediation_templates = self._load_remediation_templates()
    
    def _load_remediation_templates(self) -> dict[str, str]:
        """Load remediation templates for common controls."""
        return {
            "CC6.1": """
For MFA enforcement issues:
1. Navigate to your identity provider admin console
2. Enable MFA policy for all users
3. Set MFA requirement for admin accounts (critical)
4. Configure MFA methods (TOTP, WebAuthn, SMS fallback)
5. Set grace period for user enrollment (7 days recommended)
6. Monitor enrollment progress in dashboard
7. Escalate non-compliant users to management
""",
            "CC6.5": """
For encryption issues:
1. Identify unencrypted resources (S3 buckets, RDS instances, etc.)
2. Enable default encryption on storage services
3. Rotate existing unencrypted data to encrypted storage
4. Enable KMS key rotation
5. Update IAM policies to require encryption
6. Configure encryption monitoring alerts
""",
            "CC8.1": """
For change management issues:
1. Implement change request workflow
2. Require approval before production changes
3. Document all changes in ticketing system
4. Implement automated change detection
5. Set up change review meetings
6. Maintain change audit trail
""",
            "HIPAA.164.312.a.1": """
For HIPAA access control issues:
1. Implement unique user IDs for all workforce members
2. Enable automatic logoff after inactivity
3. Implement encryption for ePHI access
4. Document access authorization procedures
5. Regular access reviews (quarterly minimum)
6. Maintain access logs for 6 years
""",
        }
    
    async def suggest_remediation(
        self,
        violation: Violation,
        control_def: dict[str, Any] | None = None
    ) -> str:
        """
        Generate remediation suggestion for a violation.
        
        Args:
            violation: Violation to remediate.
            control_def: Optional control definition for context.
            
        Returns:
            Remediation suggestion text.
        """
        # Check for template first
        template = self.remediation_templates.get(violation.control_id)
        if template:
            return self._customize_template(template, violation, control_def)
        
        # Generate using LLM
        return await self._generate_with_llm(violation, control_def)
    
    def _customize_template(
        self,
        template: str,
        violation: Violation,
        control_def: dict[str, Any] | None
    ) -> str:
        """Customize template with violation-specific details."""
        customized = template.strip()
        customized += f"\n\nViolation Context:\n- Control: {violation.control_id}\n"
        customized += f"- Severity: {violation.severity}\n"
        customized += f"- Description: {violation.description}\n"
        
        if control_def:
            customized += f"- Control Name: {control_def.get('name', 'N/A')}\n"
        
        return customized
    
    async def _generate_with_llm(
        self,
        violation: Violation,
        control_def: dict[str, Any] | None
    ) -> str:
        """Generate remediation using LLM."""
        prompt = self._build_remediation_prompt(violation, control_def)
        
        try:
            response = await self._call_llm_api(prompt)
            return response
        except Exception as e:
            logger.error(f"LLM remediation generation failed: {e}")
            return self._get_fallback_remediation(violation)
    
    def _build_remediation_prompt(
        self,
        violation: Violation,
        control_def: dict[str, Any] | None
    ) -> str:
        """Build prompt for LLM."""
        control_name = control_def.get("name", violation.control_id) if control_def else violation.control_id
        
        return f"""You are a compliance remediation expert. Generate specific, actionable remediation steps for the following compliance violation.

Control: {violation.control_id}
Control Name: {control_name}
Severity: {violation.severity}
Description: {violation.description}

Provide:
1. Immediate actions (within 24 hours)
2. Short-term fixes (within 1 week)
3. Long-term improvements (within 1 month)
4. Evidence to collect after remediation

Format as numbered steps with specific technical actions."""
    
    async def _call_llm_api(self, prompt: str) -> str:
        """Call LLM API (vLLM, Ollama, or OpenAI)."""
        client = self._get_http_client()
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a compliance remediation expert. Provide specific, actionable remediation steps."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.3,
        }
        
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.text}")
                raise RemediationAgentError(f"LLM API returned {response.status_code}")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling LLM API: {e}")
            raise RemediationAgentError(f"Failed to call LLM API: {e}")
    
    def _get_fallback_remediation(self, violation: Violation) -> str:
        """Return fallback remediation when LLM fails."""
        return f"""Remediation Steps for {violation.control_id}:

1. REVIEW: Carefully review the control requirements and the specific violation details.

2. ASSESS: Determine the root cause of the compliance gap.

3. PLAN: Create a remediation plan with specific technical actions.

4. IMPLEMENT: Execute the remediation plan.

5. VERIFY: Collect evidence that the remediation was successful.

6. DOCUMENT: Update compliance documentation and close the violation.

For specific guidance, consult the compliance framework documentation or engage a compliance specialist."""
    
    async def generate_fix_steps(self, violation: Violation) -> list[str]:
        """
        Generate structured fix steps for a violation.
        
        Args:
            violation: Violation to remediate.
            
        Returns:
            List of fix steps.
        """
        suggestion = await self.suggest_remediation(violation)
        
        # Parse numbered steps from suggestion
        steps = []
        for line in suggestion.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove numbering
                step = line.lstrip("0123456789.- ").strip()
                if step:
                    steps.append(step)
        
        return steps if steps else ["Review violation details", "Implement fix", "Verify remediation"]
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._http_client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
