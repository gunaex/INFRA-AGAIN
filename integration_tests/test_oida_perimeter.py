import time
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from infra_again.oida_app import InfraIdentityMiddleware


def test_owner_design_access_without_provider_execution():
    app = FastAPI()

    @app.get("/api/v1/designs")
    def designs():
        return {"designs": []}

    @app.post("/api/v1/designs")
    def create_design():
        return {"created": True}

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app.add_middleware(InfraIdentityMiddleware, public_key=key.public_key(),
                       issuer="test-account", owner_subject="owner-account")
    client = TestClient(app)
    assert client.get("/api/v1/designs", headers={"X-Actor": "owner-account"}).status_code == 401
    now = int(time.time())
    claims = {"sub": "owner-account", "iss": "test-account", "aud": "again-ecosystem-identity",
              "iat": now, "exp": now + 300}
    client.headers["Authorization"] = "Bearer " + jwt.encode(claims, key, algorithm="RS256")
    assert client.get("/api/v1/designs").status_code == 200
    assert client.post("/api/v1/designs").status_code == 200
    for path in ["/api/v1/runners/register", "/api/v1/sandbox/execute", "/api/v1/execution-packages/p/execute",
                 "/api/v1/runs/r/apply", "/api/v1/catalog/sync"]:
        assert client.post(path).status_code == 403
    assert client.get("/api/v1/_test/instrumentation").status_code == 404
    for update in [{"sub": "other-owner"}, {"mustChangePassword": True}, {"exp": now + 7200}]:
        client.headers["Authorization"] = "Bearer " + jwt.encode({**claims, **update}, key, algorithm="RS256")
        assert client.get("/api/v1/designs").status_code == 401


def test_real_factory_bootstraps_only_in_dedicated_test_directory(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source)
    environment["OIDA_INFRA_DATA_DIR"] = str(tmp_path)
    environment["INFRA_AGAIN_DB"] = str(tmp_path / ".ai" / "infra-again.db")
    script = textwrap.dedent('''
        import os, time
        from pathlib import Path
        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from fastapi.testclient import TestClient
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = Path.cwd() / "test-public.pem"
        public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                          serialization.PublicFormat.SubjectPublicKeyInfo))
        os.environ["OIDA_SSO_PUBLIC_KEY_FILE"] = str(public)
        os.environ["OIDA_SSO_ISSUER"] = "test-account"
        os.environ["OIDA_INFRA_OWNER_SUBJECT"] = "test-owner"
        from infra_again.oida_app import create_app
        with TestClient(create_app()) as client:
            assert client.get("/api/v1/designs").status_code == 401
            now = int(time.time())
            token = jwt.encode({"sub": "test-owner", "iss": "test-account",
                "aud": "again-ecosystem-identity", "iat": now, "exp": now + 300}, key, algorithm="RS256")
            client.headers["Authorization"] = "Bearer " + token
            assert client.get("/api/v1/designs").status_code == 200
            assert client.post("/api/v1/designs?name=Isolated-test").status_code == 200
            assert client.post("/api/v1/sandbox/execute").status_code == 403
            assert client.get("/api/v1/capabilities").status_code == 200
    ''')
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".ai" / "infra-again.db").is_file()
