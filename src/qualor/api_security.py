"""Process-local controller protections; no external authentication or paid execution."""

import hmac
from ipaddress import ip_address

from fastapi import Request

from qualor.workspace.service import ProductFailure


def require_local_origin(request: Request) -> None:
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    if (
        not local
        or request.headers.get("origin") not in request.app.state.settings.qualor_allowed_origins
    ):
        raise ProductFailure("ACTION_FORBIDDEN", 403)


def require_action(request: Request) -> None:
    if request.app.state.settings.qualor_security_mode == "HOSTED_DEMO":
        supplied = request.headers.getlist("x-qualor-action-token")
        if len(supplied) != 1 or not request.app.state.hosted_action_capabilities.validate(
            supplied[0]
        ):
            raise ProductFailure("ACTION_FORBIDDEN", 403)
        return
    require_local_origin(request)
    supplied = request.headers.get("x-qualor-action-token", "")
    expected = request.app.state.action_token
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ProductFailure("ACTION_FORBIDDEN", 403)


def require_hosted_proxy(request: Request) -> None:
    """Authenticate the origin hop; browser session enforcement belongs to the edge."""
    expected = request.app.state.settings.qualor_origin_auth
    supplied = request.headers.getlist("x-qualor-origin-auth")
    if (
        expected is None
        or len(supplied) != 1
        or len(supplied[0]) > 1024
        or not hmac.compare_digest(
            supplied[0].encode(), expected.get_secret_value().encode()
        )
    ):
        raise ProductFailure("ACTION_FORBIDDEN", 403)
