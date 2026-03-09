import csv
import io
from math import ceil

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from openpyxl import Workbook

from .auth import (
    is_session_authenticated,
    login_user,
    logout_user,
    require_api_auth,
    verify_credentials,
)
from .db import get_db
from .repositories import count_table_rows, get_last_sync_info, get_table_rows
from .settings import settings
from .sync_service import sync_all

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_session_authenticated(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not verify_credentials(username, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Nieprawidłowy login lub hasło."},
            status_code=401,
        )

    login_user(request)
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
):
    if not is_session_authenticated(request):
        return RedirectResponse(url="/login?next=/admin", status_code=303)

    q = (request.query_params.get("q") or "").strip()
    sort = (request.query_params.get("sort") or "id_asc").strip()
    page = max(int(request.query_params.get("page", 1)), 1)
    per_page = 50

    total = count_table_rows(db, q=q)
    total_pages = max(ceil(total / per_page), 1)

    if page > total_pages:
        page = total_pages

    rows = get_table_rows(db, q=q, sort=sort, page=page, per_page=per_page)
    sync_info = get_last_sync_info(db)

    return templates.TemplateResponse(
        "table.html",
        {
            "request": request,
            "rows": rows,
            "q": q,
            "sort": sort,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "last_data_fetch_at": sync_info["last_data_fetch_at"],
            "last_run": sync_info["last_run"],
        },
    )


@app.post("/admin/sync")
def admin_sync(
    request: Request,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    sync_all(db)
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/export-csv")
def export_csv(
    request: Request,
    db: Session = Depends(get_db),
):
    if not is_session_authenticated(request):
        return RedirectResponse(url="/login?next=/admin", status_code=303)

    q = (request.query_params.get("q") or "").strip()
    sort = (request.query_params.get("sort") or "id_asc").strip()

    rows = get_table_rows(db, q=q, sort=sort, page=1, per_page=100000)
    sync_info = get_last_sync_info(db)
    last_data_fetch_at = sync_info["last_data_fetch_at"]

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["Data ostatniego pobrania danych", last_data_fetch_at or "brak danych"])
    writer.writerow([])

    writer.writerow([
        "ID",
        "symbol-kolor",
        "stan dyspozycyjny (M1)",
        "rezerwacje",
        "Całkowita liczba sprzedanych",
    ])

    for row in rows:
        writer.writerow([
            row["id"],
            row["symbol_kolor"],
            row["m1_stan_dyspozycyjny"],
            row["rezerwacje"],
            row["calkowita_liczba_sprzedanych"],
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="stany_magazynowe.csv"'
        },
    )


@app.get("/admin/export-xlsx")
def export_xlsx(
    request: Request,
    db: Session = Depends(get_db),
):
    if not is_session_authenticated(request):
        return RedirectResponse(url="/login?next=/admin", status_code=303)

    q = (request.query_params.get("q") or "").strip()
    sort = (request.query_params.get("sort") or "id_asc").strip()

    rows = get_table_rows(db, q=q, sort=sort, page=1, per_page=100000)
    sync_info = get_last_sync_info(db)
    last_data_fetch_at = sync_info["last_data_fetch_at"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Stany"

    ws["A1"] = "Data ostatniego pobrania danych"
    ws["B1"] = str(last_data_fetch_at or "brak danych")

    headers = [
        "ID",
        "symbol-kolor",
        "stan dyspozycyjny (M1)",
        "rezerwacje",
        "Całkowita liczba sprzedanych",
    ]
    ws.append([])
    ws.append(headers)

    for row in rows:
        ws.append([
            row["id"],
            row["symbol_kolor"],
            row["m1_stan_dyspozycyjny"],
            row["rezerwacje"],
            row["calkowita_liczba_sprzedanych"],
        ])

    widths = {
        "A": 12,
        "B": 30,
        "C": 24,
        "D": 14,
        "E": 28,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="stany_magazynowe.xlsx"'
        },
    )
