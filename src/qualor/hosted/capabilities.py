"""Short-lived process-local browser capabilities for the hosted demo boundary."""

import hashlib
import hmac
import secrets
import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta


class HostedActionCapabilities:
    """Issue opaque capabilities while retaining only bounded token digests."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=30),
        maximum: int = 64,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if ttl <= timedelta(0) or maximum < 1:
            raise ValueError("Hosted capability limits must be positive")
        self._ttl = ttl
        self._maximum = maximum
        self._clock = clock
        self._entries: OrderedDict[bytes, datetime] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    def _prune(self, now: datetime) -> None:
        expired = [digest for digest, expiry in self._entries.items() if expiry <= now]
        for digest in expired:
            del self._entries[digest]

    def issue(self) -> str:
        now = self._clock()
        with self._lock:
            self._prune(now)
            while True:
                token = secrets.token_urlsafe(32)
                digest = self._digest(token)
                if digest not in self._entries:
                    break
            self._entries[digest] = now + self._ttl
            while len(self._entries) > self._maximum:
                self._entries.popitem(last=False)
        return token

    def validate(self, token: str) -> bool:
        if not token or len(token) > 1024:
            return False
        candidate = self._digest(token)
        now = self._clock()
        with self._lock:
            self._prune(now)
            matched = False
            for stored in self._entries:
                matched = hmac.compare_digest(candidate, stored) or matched
            return matched

    @property
    def size(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._entries)
