import os

from flask import request
from flask_limiter import Limiter

# ---------------------------------------------------------------------------
# Rate-limiter storage
# ---------------------------------------------------------------------------
# RATELIMIT_STORAGE_URI must be set to a Redis (or Memcached) URL in
# production so that limits are shared across all gunicorn workers/processes.
# Example .env value:  RATELIMIT_STORAGE_URI=redis://localhost:6379/0
#
# Falling back to "memory://" is safe for single-process dev/test, but MUST
# NOT be used in production: each worker keeps its own counter, so the
# effective limit becomes limit × num_workers.
_storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")


def get_real_ip() -> str:
    """Return the real visitor IP.

    Reads CF-Connecting-IP when running behind Cloudflare so that
    rate limits apply per visitor rather than per Cloudflare egress node.
    Falls back to REMOTE_ADDR for local / non-proxied environments.
    """
    return request.headers.get("CF-Connecting-IP") or request.remote_addr


limiter = Limiter(get_real_ip, storage_uri=_storage_uri, default_limits=[])