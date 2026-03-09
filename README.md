# Wassyl / IdoSell stock panel — szkielet pod Render v2

Szkielet aplikacji opiera się na ustalonej architekturze:
- źródło listy produktów: feed XML,
- filtr: tylko status `w produkcji`,
- pobieranie stanów: `GET /products/stocks`, batchami po 100 produktów,
- prezentacja w tabeli: `ID`, `symbol-kolor`, `stan dyspozycyjny (M1)`, `rezerwacje`.

## Co doszło w wersji 2
- logowanie do panelu przez prosty formularz i sesję,
- paginacja tabeli,
- sortowanie po wszystkich kolumnach,
- eksport CSV,
- możliwość pozostawienia `ADMIN_TOKEN` tylko do API JSON (opcjonalnie).

## Stos technologiczny
- FastAPI
- PostgreSQL
- Jinja2 templates
- Render Web Service + Render Cron Job + Render Postgres

## Struktura
- `app/` — aplikacja
- `sql/init.sql` — tworzenie tabel i indeksów
- `scripts/run_sync.py` — uruchomienie synchronizacji z CLI / Crona
- `render.yaml` — blueprint dla Render

## Wymagane zmienne środowiskowe
Skopiuj `.env.example` i ustaw:
- `DATABASE_URL`
- `IDOSELL_API_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SESSION_SECRET`

Opcjonalnie:
- `ADMIN_TOKEN` — tylko jeśli chcesz nadal autoryzować endpointy JSON nagłówkiem `X-ADMIN-TOKEN`.

## Lokalny start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env.example | xargs)
psql "$DATABASE_URL" -f sql/init.sql
uvicorn app.main:app --reload
```

## Endpointy
- `GET /health` — healthcheck
- `GET /login` — ekran logowania
- `POST /login` — logowanie do panelu
- `POST /logout` — wylogowanie
- `GET /admin` — panel tabeli
- `POST /admin/sync` — ręczne uruchomienie synchronizacji
- `GET /admin/export.csv` — eksport widoku do CSV
- `GET /api/table` — JSON z tabelą
- `GET /api/sync-status` — status ostatnich synchronizacji

## Sortowanie i paginacja
Panel wspiera parametry:
- `q` — wyszukiwanie po ID, symbolu lub kolorze,
- `sort` — `id`, `symbol_kolor`, `m1`, `rezerwacje`,
- `direction` — `asc` lub `desc`,
- `page` — numer strony od 1,
- `per_page` — liczba rekordów na stronę.

## Model działania synchronizacji
1. Jeśli cache feedu wygasł, aplikacja pobiera XML i zapisuje tylko produkty ze statusem `w produkcji`.
2. Aplikacja pobiera stany z IdoSell batchami po maks. 100 produktów.
3. Zapisuje:
   - aktualny stan do `product_stock_current`,
   - historię dzienną do `product_stock_history`,
   - log przebiegu do `sync_runs`.
4. Panel pokazuje zagregowaną tabelę dla magazynu `M1` (`stock_id = 1`).

## Uwaga o czasie Crona
W `render.yaml` harmonogram cron jest podany w UTC.
`15 2 * * *` oznacza 02:15 UTC, czyli zwykle 03:15 lub 04:15 czasu Warszawy, zależnie od DST.

## Wdrożenie na Render
1. Wrzuć repo do GitHub.
2. W Render wybierz **New + > Blueprint**.
3. Wskaż repo z `render.yaml`.
4. Uzupełnij sekrety: `IDOSELL_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SESSION_SECRET`.
5. Po utworzeniu bazy uruchom:
   ```bash
   psql "$DATABASE_URL" -f sql/init.sql
   ```
   albo wykonaj ten SQL ręcznie w konsoli Postgresa.
