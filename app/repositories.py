from sqlalchemy import text


SORT_MAP = {
    "id_asc": "id ASC",
    "id_desc": "id DESC",
    "symbol_asc": "symbol_kolor ASC",
    "symbol_desc": "symbol_kolor DESC",
    "m1_asc": "m1_stan_dyspozycyjny ASC",
    "m1_desc": "m1_stan_dyspozycyjny DESC",
    "rez_asc": "rezerwacje ASC",
    "rez_desc": "rezerwacje DESC",
    "sold_asc": "calkowita_liczba_sprzedanych ASC",
    "sold_desc": "calkowita_liczba_sprzedanych DESC",
}


def _base_cte_sql() -> str:
    return """
    WITH aggregated AS (
        SELECT
            p.product_id AS id,
            (p.symbol || '-' || p.kolor) AS symbol_kolor,
            COALESCE(SUM(s.quantity - s.reserved_orders), 0) AS m1_stan_dyspozycyjny,
            COALESCE(SUM(s.reserved_orders), 0) AS rezerwacje,
            CASE
                WHEN (
                    COALESCE(SUM(s.quantity - s.reserved_orders), 0)
                    + COALESCE(SUM(s.reserved_orders), 0)
                ) > 1000
                THEN 2000 - (
                    COALESCE(SUM(s.quantity - s.reserved_orders), 0)
                    + COALESCE(SUM(s.reserved_orders), 0)
                )
                ELSE 1000 - (
                    COALESCE(SUM(s.quantity - s.reserved_orders), 0)
                    + COALESCE(SUM(s.reserved_orders), 0)
                )
            END AS calkowita_liczba_sprzedanych
        FROM production_products_cache p
        LEFT JOIN product_stock_current s
          ON s.product_id = p.product_id
         AND s.stock_id = 1
        WHERE p.expires_at > NOW()
        GROUP BY p.product_id, p.symbol, p.kolor
    )
    """


def count_table_rows(db, q: str = "") -> int:
    params = {}
    sql = _base_cte_sql() + """
    SELECT COUNT(*)
    FROM aggregated
    WHERE 1=1
    """

    if q:
        sql += """
        AND (
            CAST(id AS TEXT) ILIKE :q
            OR symbol_kolor ILIKE :q
        )
        """
        params["q"] = f"%{q}%"

    return int(db.execute(text(sql), params).scalar() or 0)


def get_table_rows(db, q: str = "", sort: str = "id_asc", page: int = 1, per_page: int = 50):
    params = {
        "limit": per_page,
        "offset": (page - 1) * per_page,
    }

    order_by = SORT_MAP.get(sort, "id ASC")

    sql = _base_cte_sql() + """
    SELECT
        id,
        symbol_kolor,
        m1_stan_dyspozycyjny,
        rezerwacje,
        calkowita_liczba_sprzedanych
    FROM aggregated
    WHERE 1=1
    """

    if q:
        sql += """
        AND (
            CAST(id AS TEXT) ILIKE :q
            OR symbol_kolor ILIKE :q
        )
        """
        params["q"] = f"%{q}%"

    sql += f"""
    ORDER BY {order_by}
    LIMIT :limit OFFSET :offset
    """

    return db.execute(text(sql), params).mappings().all()
