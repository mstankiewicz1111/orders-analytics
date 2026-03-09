from typing import Any

import requests

from .settings import settings


class IdosellClient:
    def __init__(self) -> None:
        self.base_url = settings.idosell_api_base_url.rstrip('/')
        self.headers = {
            'accept': 'application/json',
            'X-API-KEY': settings.idosell_api_key,
        }

    def fetch_stocks(self, product_ids: list[int]) -> dict[str, Any]:
        if not product_ids:
            return {'results': [], 'is_errors': False}

        params = {
            'identType': 'id',
            'products': ','.join(str(product_id) for product_id in product_ids),
        }
        response = requests.get(
            f'{self.base_url}/products/stocks',
            params=params,
            headers=self.headers,
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
