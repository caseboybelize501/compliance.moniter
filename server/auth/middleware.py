"""
JWT Authentication Middleware for ACMP.

Validates JWT tokens from Keycloak and extracts user/tenant context.
"""
from typing import Optional, Dict, Any, Callable
from functools import wraps

from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from server.auth.keycloak_client import KeycloakAuth, KeycloakAuthError


# HTTP Bearer token security
security = HTTPBearer(auto_error=False)


class AuthContext:
    """
    Authentication context from JWT token.
    """
    
    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[str],
        claims: Dict[str, Any],
        token: str
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles
        self.claims = claims
        self.token = token
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return 'admin' in self.roles or 'acmp-admin' in self.roles
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return bool(self.user_id)


class AuthMiddleware:
    """
    JWT authentication middleware.
    
    Usage:
        auth = AuthMiddleware(keycloak_auth)
        
        @app.get("/protected")
        async def protected_route(auth_context: AuthContext = Depends(auth)):
            return {"user": auth_context.user_id}
    """
    
    def __init__(self, keycloak_auth: KeycloakAuth):
        """
        Initialize auth middleware.
        
        Args:
            keycloak_auth: Keycloak auth client
        """
        self.keycloak_auth = keycloak_auth
    
    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> AuthContext:
        """
        Authenticate request and return auth context.
        
        Args:
            request: FastAPI request
            credentials: Bearer token credentials
            
        Returns:
            AuthContext with user/tenant info
            
        Raises:
            HTTPException: If authentication fails
        """
        # Check for credentials
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = credentials.credentials
        
        try:
            # Validate token
            claims = await self.keycloak_auth.validate_token(token)
            
            # Extract user info
            user_id = claims.get('sub')
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing subject"
                )
            
            # Extract tenant ID
            tenant_id = self.keycloak_auth.extract_tenant_id(claims)
            if not tenant_id:
                # Default tenant for development
                tenant_id = claims.get('tenant_id', 'default')
            
            # Extract roles
            roles = self.keycloak_auth.extract_user_roles(claims)
            
            return AuthContext(
                user_id=user_id,
                tenant_id=tenant_id,
                roles=roles,
                claims=claims,
                token=token
            )
            
        except KeycloakAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )


def require_role(required_role: str) -> Callable:
    """
    Decorator to require specific role for endpoint.
    
    Usage:
        @app.get("/admin")
        @require_role("admin")
        async def admin_route(auth: AuthContext = Depends(AuthMiddleware)):
            return {"message": "Admin access"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, auth: AuthContext, **kwargs):
            if required_role not in auth.roles and not auth.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_role}"
                )
            return await func(*args, auth=auth, **kwargs)
        return wrapper
    return decorator


def require_tenant_match() -> Callable:
    """
    Decorator to ensure tenant in URL matches token tenant.
    
    Usage:
        @app.get("/tenants/{tenant_id}/data")
        @require_tenant_match()
        async def get_tenant_data(tenant_id: str, auth: AuthContext):
            # tenant_id will match auth.tenant_id
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, auth: AuthContext, **kwargs):
            url_tenant_id = kwargs.get('tenant_id')
            if url_tenant_id and url_tenant_id != auth.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: tenant mismatch"
                )
            return await func(*args, auth=auth, **kwargs)
        return wrapper
    return decorator


# Global auth instance (initialized in main.py)
_auth_instance: Optional[AuthMiddleware] = None


def get_auth() -> Optional[AuthMiddleware]:
    """Get global auth instance."""
    return _auth_instance


def init_auth(keycloak_auth: KeycloakAuth) -> AuthMiddleware:
    """
    Initialize global auth instance.
    
    Args:
        keycloak_auth: Keycloak auth client
        
    Returns:
        AuthMiddleware instance
    """
    global _auth_instance
    _auth_instance = AuthMiddleware(keycloak_auth)
    return _auth_instance
