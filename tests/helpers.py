"""Shared test helpers."""
from unittest.mock import MagicMock


def make_mock_response(status_code=200, json_data=None, text=""):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else {}
    mock.text = text
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock.raise_for_status.return_value = None
    return mock


def make_flows_response(items, total_pages=1):
    return make_mock_response(json_data={
        "items": items,
        "totalPages": total_pages,
        "page": 1,
        "totalItems": len(items),
    })
