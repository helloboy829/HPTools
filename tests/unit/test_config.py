import tempfile
import unittest
from pathlib import Path

from aiperf.config import AppPaths


class AppPathsTests(unittest.TestCase):
    def test_maps_runtime_directories_below_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "AI PERF 中文"
            paths = AppPaths.from_root(root)

            expected = {
                "data": root / "data",
                "assets": root / "assets",
                "runs": root / "runs",
                "packages": root / "packages",
                "temp": root / "temp",
                "logs": root / "logs",
            }
            for name, path in expected.items():
                self.assertEqual(getattr(paths, name), path)
                self.assertEqual(path.parent, root)

    def test_ensure_directories_creates_runtime_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            paths = AppPaths.from_root(root)

            paths.ensure_directories()

            for name in ("data", "assets", "runs", "packages", "temp", "logs"):
                self.assertTrue(getattr(paths, name).is_dir(), name)

    def test_rejects_relative_root(self) -> None:
        with self.assertRaises(ValueError):
            AppPaths.from_root(Path("relative-root"))


if __name__ == "__main__":
    unittest.main()
