from fastapi import Header, HTTPException, Request

from .settings import settings


SESSION_KEY = 'admin_logged_in'


def is_session_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def login_user(request: Request) -> None:
    request.session[SESSION_KEY] = True
    request.session['admin_username'] = settings.admin_username


def logout_user(request: Request) -> None:
    request.session.clear()


def verify_credentials(username: str, password: str) -> bool:
    return username == settings.admin_username and password == settings.admin_password


def require_api_auth(
    request: Request,
    x_admin_token: str | None = Header(default=None),
) -> None:
    if is_session_authenticated(request):
        return
    if settings.admin_token and x_admin_token == settings.admin_token:
        return
    raise HTTPException(status_code=401, detail='Unauthorized')
