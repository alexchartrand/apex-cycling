import httpx

from app.core.config import get_settings


class SqorzClientError(Exception):
    """Raised when the sqorz API returns a non-2xx response or is unreachable."""

    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


async def fetch_transponder_history(transponder_code: str) -> dict:
    """Fetch the full training history for one transponder. The response
    shape (confirmed live): {transponderCode, eventTrainingDetails: [{
    trainingDetail: {...}, accountId, accountName, cacheSeconds, ...}]}.
    """
    settings = get_settings()
    url = f"{settings.sqorz_base_url}/{transponder_code}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise SqorzClientError(f"Request to sqorz failed: {exc}") from exc

    if response.status_code != 200:
        raise SqorzClientError(
            f"sqorz returned HTTP {response.status_code}", http_status=response.status_code
        )

    return response.json()
