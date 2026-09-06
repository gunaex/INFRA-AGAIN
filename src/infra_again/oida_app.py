"""Private, single-owner design perimeter for the OIDA integration.

Provider execution is intentionally unavailable through this entrypoint until
an approval-bound execution contract is wired. The standalone API is unchanged.
"""

import os
import re
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InfraIdentityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, public_key, issuer: str, owner_subject: str):
        super().__init__(app)
        self.public_key = public_key
        self.issuer = issuer
        self.owner_subject = owner_subject

    async def dispatch(self, request, call_next):
        if request.url.path != "/health":
            raw = request.headers.get("authorization", "")
            try:
                if not raw.startswith("Bearer ") or len(raw) > 16400:
                    raise ValueError()
                claims = jwt.decode(raw[7:], self.public_key, algorithms=["RS256"],
                    issuer=self.issuer, audience="again-ecosystem-identity",
                    options={"require": ["sub", "iat", "exp", "iss", "aud"]})
                if (claims["sub"] != self.owner_subject
                        or claims.get("mustChangePassword", False) is not False
                        or type(claims["iat"]) is not int or type(claims["exp"]) is not int
                        or not 0 < claims["exp"] - claims["iat"] <= 3600):
                    raise ValueError()
            except (jwt.PyJWTError, ValueError, TypeError):
                return JSONResponse({"detail": "Owner identity required"}, status_code=401)
            path = request.url.path
            if "/_test/" in path:
                return JSONResponse({"detail": "Test routes unavailable"}, status_code=404)
            design_write = request.method == "POST" and (
                path == "/api/v1/designs" or path == "/api/v1/capabilities/compare"
                or re.fullmatch(r"/api/v1/designs/[A-Za-z0-9_-]+/(generate|simulate|accept|request-change|update-flow|implementation-plan)", path)
                or re.fullmatch(r"/api/v1/implementation-plans/[A-Za-z0-9_-]+/(approve|request-change)", path)
            )
            if request.method not in {"GET", "HEAD"} and not design_write:
                return JSONResponse({"detail": "Execution and provider changes require an approval-bound gateway"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def create_app():
    # The existing modules use relative evidence locations. Require an explicit
    # dedicated working directory before their import-time database bootstrap.
    data_dir = os.environ.get("OIDA_INFRA_DATA_DIR", "")
    issuer = os.environ.get("OIDA_SSO_ISSUER", "")
    owner = os.environ.get("OIDA_INFRA_OWNER_SUBJECT", "")
    if not data_dir or not Path(data_dir).is_absolute() or Path(data_dir).resolve() != Path.cwd():
        raise ValueError("Start Infra in its explicit dedicated data directory")
    if Path(data_dir).resolve() in {Path("/"), Path.home()}:
        raise ValueError("A dedicated application directory is required")
    expected_db = Path.cwd() / ".ai" / "infra-again.db"
    if Path(os.environ.get("INFRA_AGAIN_DB", str(expected_db))).resolve() != expected_db:
        raise ValueError("All Infra state must use the dedicated application database")
    if not issuer or not owner:
        raise ValueError("Explicit issuer and owner subject are required")
    public_path = Path(os.environ.get("OIDA_SSO_PUBLIC_KEY_FILE", ""))
    try:
        if not public_path.is_absolute():
            raise ValueError()
        key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError()
    except (ValueError, OSError):
        raise ValueError("An explicit RSA public key is required") from None
    from .api import app
    app.add_middleware(InfraIdentityMiddleware, public_key=key, issuer=issuer, owner_subject=owner)
    return app
