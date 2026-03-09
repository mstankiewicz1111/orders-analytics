from io import BytesIO
from typing import Iterator
import xml.etree.ElementTree as ET

import requests

from .settings import settings


class FeedProduct(dict):
    product_id: int
    symbol: str
    kolor: str


def iter_production_products() -> Iterator[dict]:
    response = requests.get(
        settings.feed_url,
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": "wassyl-stock-panel/1.0"},
    )
    response.raise_for_status()

    context = ET.iterparse(BytesIO(response.content), events=("end",))
    for _, elem in context:
        if elem.tag != "product":
            continue

        id_el = elem.find("id")
        symbol_el = elem.find("symbol")
        color_el = elem.find("kolor")
        status_el = elem.find("status")

        try:
            product_id = int((id_el.text or "").strip()) if id_el is not None else None
        except ValueError:
            product_id = None

        status = (status_el.text or "").strip().lower() if status_el is not None else ""

        if product_id and status == "w produkcji":
            yield {
                "product_id": product_id,
                "symbol": (symbol_el.text or "").strip() if symbol_el is not None else "",
                "kolor": (color_el.text or "").strip() if color_el is not None else "",
            }

        elem.clear()
