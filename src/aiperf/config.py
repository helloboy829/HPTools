"""Application configuration and explicit runtime directory paths."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Runtime directories rooted in an explicitly configured absolute path."""

    root: Path
    data: Path
    assets: Path
    runs: Path
    packages: Path
    temp: Path
    logs: Path

    @classmethod
    def from_root(cls, root: Path) -> "AppPaths":
        """Build paths without deriving anything from the process working directory."""

        root = Path(root)
        if not root.is_absolute():
            raise ValueError("application root must be an absolute path")

        return cls(
            root=root,
            data=root / "data",
            assets=root / "assets",
            runs=root / "runs",
            packages=root / "packages",
            temp=root / "temp",
            logs=root / "logs",
        )

    def ensure_directories(self) -> None:
        """Create all configured runtime directories if they do not exist."""

        for path in (self.data, self.assets, self.runs, self.packages, self.temp, self.logs):
            path.mkdir(parents=True, exist_ok=True)
