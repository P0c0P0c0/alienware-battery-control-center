from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from release_ops import lock, write_new


class FilesystemTests(unittest.TestCase):
    def test_write_refuses_symlink_targets_and_parents(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "file"
            write_new(original, b"original", 0o600)
            link = root / "link"
            link.symlink_to(original)
            with self.assertRaises(FileExistsError):
                write_new(link, b"replacement", 0o600)
            nested = root / "nested"
            nested.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "Symlink parent"):
                write_new(nested / "new", b"replacement", 0o600)
            with self.assertRaises(OSError):
                with lock(link):
                    self.fail("opened a symlink lock")
            self.assertEqual(original.read_bytes(), b"original")
