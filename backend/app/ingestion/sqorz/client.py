import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.ingestion.sqorz.schemas import SqorzHistoryPayload


class SqorzClientError(Exception):
    """Raised when the sqorz API returns a non-2xx response or is unreachable."""

    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class SqorzHttpClient:
    """HTTP client for the sqorz transponder history API."""

    async def fetch_transponder_history(self, transponder_code: str) -> dict:
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

        payload = response.json()

        # Validate the response shape up front so a malformed/changed upstream
        # payload fails here with a clear message, rather than as an obscure
        # KeyError/TypeError deep inside normalize_snapshot. The validated model
        # is discarded — normalize_snapshot still works off the original dict so
        # the RawSnapshot we persist is a faithful, unmodified copy.
        try:
            SqorzHistoryPayload.model_validate(payload)
        except ValidationError as exc:
            raise SqorzClientError(f"sqorz response failed schema validation: {exc}") from exc

        return payload
