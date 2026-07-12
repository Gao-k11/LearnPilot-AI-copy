from typing import Any

try:
    import httpx
except ModuleNotFoundError:
    httpx = None

from backend.app.core.config import get_settings


class MLServiceUnavailable(RuntimeError):
    pass


class MLServiceHTTPError(MLServiceUnavailable):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MLServiceTimeout(MLServiceUnavailable):
    pass


class MLServiceClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ml_service_url).rstrip("/")
        self.enabled = settings.use_ml_service
        self.timeout = timeout if timeout is not None else settings.ml_service_timeout_seconds

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def diagnose(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/diagnose", payload)

    def recommend(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/recommend", payload)

    def path(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/path", payload)

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/generate", payload)

    def feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/feedback", payload)

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/student/update-profile", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise MLServiceUnavailable("ML service is disabled")
        if httpx is None:
            raise MLServiceUnavailable("httpx is not installed")

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(path)
                else:
                    response = client.request(method, path, json=payload or {})
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise MLServiceTimeout(f"ML service timeout on {method} {path}") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            detail = exc.response.text[:300] if exc.response is not None else ""
            raise MLServiceHTTPError(
                f"ML service HTTP {status_code} on {method} {path}: {detail}",
                status_code=status_code,
            ) from exc
        except Exception as exc:
            raise MLServiceUnavailable(f"ML service request failed: {exc}") from exc

        if isinstance(data, dict):
            return data
        return {"data": data}
