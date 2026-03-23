"""0Latency Memory client."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import AuthenticationError, RateLimitError, ZeroLatencyError

DEFAULT_BASE_URL = "https://api.0latency.ai"
DEFAULT_TIMEOUT = 30.0


class Memory:
    """Client for the 0Latency memory API.

    Usage::

        from zerolatency import Memory

        memory = Memory("your-api-key")
        memory.add("User prefers dark mode")
        results = memory.recall("What does the user prefer?")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "zerolatency-python/0.1.0",
            },
            timeout=timeout,
        )

    # -- public API ----------------------------------------------------------

    def add(
        self,
        content: str,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a memory.

        Args:
            content: The text content to remember.
            agent_id: Optional agent identifier for scoping memories.
            metadata: Optional key-value metadata to attach.

        Returns:
            API confirmation payload.
        """
        payload: dict[str, Any] = {"content": content}
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if metadata is not None:
            payload["metadata"] = metadata
        return self._post("/v1/memories", payload)

    def recall(
        self,
        query: str,
        agent_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Retrieve relevant memories.

        Args:
            query: Natural-language search query.
            agent_id: Optional agent identifier for scoping.
            limit: Maximum number of results (default 10).

        Returns:
            Matching memories from the API.
        """
        params: dict[str, Any] = {"query": query, "limit": limit}
        if agent_id is not None:
            params["agent_id"] = agent_id
        return self._get("/v1/memories/recall", params)

    def extract(
        self,
        conversation: list[dict[str, str]],
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Start async memory extraction from a conversation.

        Args:
            conversation: List of message dicts (e.g. ``[{"role": "user", "content": "..."}]``).
            agent_id: Optional agent identifier.

        Returns:
            Dict containing ``job_id`` for status polling.
        """
        payload: dict[str, Any] = {"conversation": conversation}
        if agent_id is not None:
            payload["agent_id"] = agent_id
        return self._post("/v1/memories/extract", payload)

    def extract_status(self, job_id: str) -> dict[str, Any]:
        """Check the status of an extraction job.

        Args:
            job_id: The job identifier returned by :meth:`extract`.

        Returns:
            Job status payload.
        """
        return self._get(f"/v1/memories/extract/{job_id}")

    def health(self) -> dict[str, Any]:
        """Check API health.

        Returns:
            Health status payload.
        """
        return self._get("/v1/health")

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._client.close()

    def __enter__(self) -> Memory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals -----------------------------------------------------------

    def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        return self._handle(self._client.post(path, json=json))

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._handle(self._client.get(path, params=params))

    @staticmethod
    def _handle(response: httpx.Response) -> dict[str, Any]:
        if response.is_success:
            return response.json()  # type: ignore[no-any-return]

        try:
            body = response.json()
        except Exception:
            body = None

        if response.status_code == 401:
            raise AuthenticationError(response=body)
        if response.status_code == 429:
            raise RateLimitError(response=body)

        msg = body.get("detail", response.text) if isinstance(body, dict) else response.text
        raise ZeroLatencyError(msg, status_code=response.status_code, response=body)
