from pathlib import Path


class LocalStorage:
    """Stores files on the local disk (default: backend/storage/, which git ignores).

    The folder is never served directly; files are only reachable through the
    authorized `/api/v1/evidence/{id}/file` endpoint.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # Refuse keys like "../../etc/passwd" that would escape the storage folder.
        if not path.is_relative_to(self.root):
            raise ValueError(f"Invalid storage key: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path_for(key).unlink(missing_ok=True)
