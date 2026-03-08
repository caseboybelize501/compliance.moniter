"""
Keycloak Authentication Client for ACMP.

OIDC authentication with Keycloak identity provider.
"""
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import jwt, JoseError
import httpx


class KeycloakAuthError(Exception):
    """Base exception for Keycloak authentication errors."""
    pass


class KeycloakAuth:
    """
    Keycloak OIDC authentication client.
    
    Features:
    - OAuth2/OIDC authentication
    - JWT token validation
    - Token refresh
    - Role-based access control
    - Multi-tenant support via claims
    """
    
    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        """
        Initialize Keycloak auth client.
        
        Args:
            server_url: Keycloak server URL (e.g., http://localhost:8080)
            realm: Realm name
            client_id: Client ID
            client_secret: Client secret (for confidential clients)
            redirect_uri: Redirect URI for OAuth2 flow
        """
        self.server_url = server_url.rstrip('/')
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        # Build OIDC endpoints
        self.issuer = f"{self.server_url}/realms/{self.realm}"
        self.authorization_endpoint = f"{self.issuer}/protocol/openid-connect/auth"
        self.token_endpoint = f"{self.issuer}/protocol/openid-connect/token"
        self.userinfo_endpoint = f"{self.issuer}/protocol/openid-connect/userinfo"
        self.jwks_uri = f"{self.issuer}/protocol/openid-connect/certs"
        
        # HTTP client for token operations
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Token cache
        self._token_cache: Dict[str, Dict] = {}
    
    def _get_oauth_client(self) -> AsyncOAuth2Client:
        """Get OAuth2 client instance."""
        return AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            authorize_url=self.authorization_endpoint,
            token_url=self.token_endpoint,
            redirect_uri=self.redirect_uri,
            scope=['openid', 'profile', 'email']
        )
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get authorization URL for OAuth2 flow.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        oauth = self._get_oauth_client()
        return oauth.create_authorization_url(state=state)[0]
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code
            
        Returns:
            Token response with access_token, refresh_token, etc.
        """
        oauth = self._get_oauth_client()
        
        try:
            token = await oauth.fetch_token(code=code)
            return token
        except Exception as e:
            raise KeycloakAuthError(f"Failed to exchange code for token: {e}")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New token response
        """
        oauth = self._get_oauth_client()
        
        try:
            token = await oauth.refresh_token(refresh_token=refresh_token)
            return token
        except Exception as e:
            raise KeycloakAuthError(f"Failed to refresh token: {e}")
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and return claims.
        
        Args:
            token: JWT access token
            
        Returns:
            Decoded token claims
        """
        try:
            # Fetch JWKS from Keycloak
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri)
                response.raise_for_status()
                jwks = response.json()
            
            # Decode and validate JWT
            claims = jwt.decode(
                token,
                key=jwks,
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_iat': True,
                    'verify_iss': True,
                },
                issuer=self.issuer
            )
            
            return claims
            
        except JoseError as e:
            raise KeycloakAuthError(f"Invalid token: {e}")
        except httpx.HTTPError as e:
            raise KeycloakAuthError(f"Failed to fetch JWKS: {e}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user info from Keycloak.
        
        Args:
            access_token: Access token
            
        Returns:
            User info dictionary
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.userinfo_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise KeycloakAuthError(f"Failed to get user info: {e}")
    
    async def introspect_token(self, token: str) -> Dict[str, Any]:
        """
        Introspect token to check if it's still active.
        
        Args:
            token: Token to introspect
            
        Returns:
            Token introspection response
        """
        introspect_url = f"{self.issuer}/protocol/openid-connect/token/introspect"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    introspect_url,
                    data={'token': token},
                    auth=(self.client_id, self.client_secret)
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise KeycloakAuthError(f"Failed to introspect token: {e}")
    
    def extract_tenant_id(self, claims: Dict[str, Any]) -> Optional[str]:
        """
        Extract tenant ID from token claims.
        
        Looks for tenant_id in custom claims or realm_access roles.
        
        Args:
            claims: Decoded token claims
            
        Returns:
            Tenant ID or None
        """
        # Check for custom tenant_id claim
        if 'tenant_id' in claims:
            return claims['tenant_id']
        
        # Check for tenant in realm_access roles
        realm_access = claims.get('realm_access', {})
        roles = realm_access.get('roles', [])
        
        for role in roles:
            if role.startswith('tenant_'):
                return role.replace('tenant_', '')
        
        return None
    
    def extract_user_roles(self, claims: Dict[str, Any]) -> list[str]:
        """
        Extract user roles from token claims.
        
        Args:
            claims: Decoded token claims
            
        Returns:
            List of role names
        """
        roles = []
        
        # Realm roles
        realm_access = claims.get('realm_access', {})
        roles.extend(realm_access.get('roles', []))
        
        # Client roles (if any)
        resource_access = claims.get('resource_access', {})
        client_roles = resource_access.get(self.client_id, {}).get('roles', [])
        roles.extend(client_roles)
        
        return roles
    
    def has_role(self, claims: Dict[str, Any], required_role: str) -> bool:
        """
        Check if user has required role.
        
        Args:
            claims: Decoded token claims
            required_role: Required role name
            
        Returns:
            True if user has role
        """
        roles = self.extract_user_roles(claims)
        return required_role in roles
    
    async def logout(self, refresh_token: str) -> None:
        """
        Logout user (invalidate refresh token).
        
        Args:
            refresh_token: Refresh token to invalidate
        """
        logout_url = f"{self.issuer}/protocol/openid-connect/logout"
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    logout_url,
                    data={'refresh_token': refresh_token},
                    auth=(self.client_id, self.client_secret)
                )
        except httpx.HTTPError:
            pass  # Ignore logout errors
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Keycloak health.
        
        Returns:
            Health status
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server_url}/health/ready",
                    timeout=5.0
                )
                response.raise_for_status()
                return {
                    'status': 'healthy',
                    'server': self.server_url,
                    'realm': self.realm
                }
        except httpx.HTTPError:
            return {
                'status': 'unhealthy',
                'server': self.server_url,
                'realm': self.realm
            }
