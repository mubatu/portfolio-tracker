import jwt
from jwt import PyJWKClient, PyJWTError
from app.core.config import get_settings

settings = get_settings()

# Supabase exposes a standard JWKS endpoint
_jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_jwks_url, cache_keys=True)


def decode_access_token(token: str) -> str | None:
    """Verify a Supabase JWT using the remote JWKS endpoint.

    Returns the user id (``sub`` claim) on success, or ``None`` if
    the token is invalid / expired.
    """
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience="authenticated",
        )
        return payload.get("sub")
    except PyJWTError as e:
        print(f"JWT decode error: {e}")
        return None
