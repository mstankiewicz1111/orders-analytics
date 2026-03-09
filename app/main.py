import csv
import io
import math
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .auth import is_session_authenticated, login_user, logout_user, require_api_auth, verify_credentials
from .db import get_db
from .repositories import count_table_rows, get_all_table_rows, get_last_sync_runs, get_table_rows
from .settings import settings
from .sync_service import sync_all

app = FastAPI(title='Wassyl stock panel')
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site='lax', https_only=False)
templates = Jinja2Templates(directory='app/templates')


SORT_LABELS = {
    'id': 'ID',
    'symbol_kolor': 'symbol-kolor',
    'm1': 'stan dyspozycyjny (M1)',
    'rezerwacje': 'rezerwacje',
}


def build_url(base: str, **params) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, '', [])}
    query = urlencode(clean)
    return f'{base}?{query}' if query else base


@app.get('/health')
def healthcheck():
    return {'status': 'ok'}


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request, next: str = '/admin', error: str | None = None):
    if is_session_authenticated(request):
        return RedirectResponse(url=next, status_code=303)
    return templates.TemplateResponse('login.html', {'request': request, 'next': next, 'error': error})


@app.post('/login', response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form('/admin')):
    if verify_credentials(username, password):
        login_user(request)
        return RedirectResponse(url=next or '/admin', status_code=303)
    return templates.TemplateResponse(
        'login.html',
        {'request': request, 'next': next, 'error': 'Nieprawidłowy login lub hasło.'},
        status_code=401,
    )


@app.post('/logout')
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url='/login', status_code=303)


@app.get('/api/table', dependencies=[Depends(require_api_auth)])
def api_table(
    q: str | None = None,
    sort: str = 'id',
    direction: str = 'asc',
    page: int = 1,
    per_page: int = settings.table_page_size,
    db: Session = Depends(get_db),
):
    total = count_table_rows(db, q=q)
    rows = list(get_table_rows(db, q=q, sort=sort, direction=direction, page=page, per_page=per_page))
    return {
        'rows': rows,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': math.ceil(total / per_page) if per_page else 1,
        'sort': sort,
        'direction': direction,
        'q': q or '',
    }


@app.get('/api/sync-status', dependencies=[Depends(require_api_auth)])
def api_sync_status(db: Session = Depends(get_db)):
    return list(get_last_sync_runs(db, limit=20))


@app.get('/admin', response_class=HTMLResponse)
def admin_panel(
    request: Request,
    q: str | None = None,
    sort: str = 'id',
    direction: str = 'asc',
    page: int = 1,
    per_page: int = settings.table_page_size,
    db: Session = Depends(get_db),
):
    if not is_session_authenticated(request):
        return RedirectResponse(url=build_url('/login', next=str(request.url.path)), status_code=303)

    total = count_table_rows(db, q=q)
    per_page = max(1, min(per_page, 500))
    pages = max(1, math.ceil(total / per_page)) if total else 1
    page = min(max(page, 1), pages)

    rows = get_table_rows(db, q=q, sort=sort, direction=direction, page=page, per_page=per_page)
    runs = get_last_sync_runs(db, limit=10)

    def next_direction(column: str) -> str:
        if sort == column and direction == 'asc':
            return 'desc'
        return 'asc'

    context = {
        'request': request,
        'rows': rows,
        'runs': runs,
        'q': q or '',
        'sort': sort,
        'direction': direction,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'sort_labels': SORT_LABELS,
        'next_direction': next_direction,
        'build_url': build_url,
    }
    return templates.TemplateResponse('table.html', context)


@app.post('/admin/sync')
def admin_sync(request: Request, db: Session = Depends(get_db)):
    if not is_session_authenticated(request):
        return RedirectResponse(url=build_url('/login', next='/admin'), status_code=303)
    sync_all(db)
    return RedirectResponse(url='/admin', status_code=303)


@app.get('/admin/export.csv')
def export_csv(
    request: Request,
    q: str | None = None,
    sort: str = 'id',
    direction: str = 'asc',
    db: Session = Depends(get_db),
):
    if not is_session_authenticated(request):
        return RedirectResponse(url=build_url('/login', next='/admin'), status_code=303)

    rows = get_all_table_rows(db, q=q, sort=sort, direction=direction)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(['ID', 'symbol-kolor', 'stan dyspozycyjny (M1)', 'rezerwacje'])
    for row in rows:
        writer.writerow([row['id'], row['symbol_kolor'], row['m1_stan_dyspozycyjny'], row['rezerwacje']])

    content = io.BytesIO(buffer.getvalue().encode('utf-8-sig'))
    headers = {'Content-Disposition': 'attachment; filename="stany_m1.csv"'}
    return StreamingResponse(content, media_type='text/csv; charset=utf-8', headers=headers)
