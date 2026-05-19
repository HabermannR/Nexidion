from flask import request
from flask_limiter import Limiter


def get_real_ip() -> str:
    """Return the real visitor IP.

    Reads CF-Connecting-IP when running behind Cloudflare so that
    rate limits apply per visitor rather than per Cloudflare egress node.
    Falls back to REMOTE_ADDR for local / non-proxied environments.
    """
    return request.headers.get("CF-Connecting-IP") or request.remote_addr


limiter = Limiter(get_real_ip, default_limits=[])