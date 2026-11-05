"""The storage interface. Callers only see these three methods, so swapping local disk for
S3-compatible cloud storage later means writing one new class, not changing callers."""

from typing import Protocol


class StorageService(Protocol):
    def save(self, key: str, data: bytes) -> None:
        """Store `data` under `key` (e.g. 'complaints/<id>/<uuid>.jpg'), overwriting if present."""
        ...

    def read(self, key: str) -> bytes:
        """Return the stored bytes. Raises FileNotFoundError if the key doesn't exist."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object. Deleting a missing key is not an error."""
        ...
