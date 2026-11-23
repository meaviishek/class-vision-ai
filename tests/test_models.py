"""Model download logic: mirror fallback, checksum verification, no half-written files.

Uses a throw-away web server on localhost, so no internet is needed and nothing real is downloaded.
Run from the project root:   python -m unittest discover -s tests -v
"""
import hashlib
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.vision import models  # noqa: E402

GOOD = b"pretend-onnx-" * 4000
SAME_SIZE_WRONG_CONTENT = b"x" * len(GOOD)
ROUTES = {
    "/good": (200, GOOD),
    "/wrong-content": (200, SAME_SIZE_WRONG_CONTENT),
    "/truncated": (200, GOOD[:1000]),
    "/error-page": (200, b"<html>Sign in to continue</html>"),
}


class Handler(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        Handler.hits.append(self.path)
        code, body = ROUTES.get(self.path, (404, b"missing"))
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.hits.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, *paths, size=None):
        return {"m.onnx": models.ModelSpec(
            urls=tuple(self.base + p for p in paths), size=size or len(GOOD),
            sha256=hashlib.sha256(GOOD).hexdigest(), min_size=100)}

    def test_falls_through_bad_mirrors_to_a_good_one(self):
        specs = self.spec("/missing", "/error-page", "/truncated", "/wrong-content", "/good")
        seen = []
        models.download_models(lambda name, done, total: seen.append((name, done, total)), specs, self.folder)
        self.assertEqual((self.folder / "m.onnx").read_bytes(), GOOD)
        self.assertEqual(list(self.folder.glob("*.part")), [])                 # no leftovers
        self.assertEqual(Handler.hits, ["/missing", "/error-page", "/truncated", "/wrong-content", "/good"])
        self.assertEqual(seen[-1], ("m.onnx", len(GOOD), len(GOOD)))
        self.assertEqual(models.missing_models(specs, self.folder), [])

    def test_stops_at_the_first_mirror_that_works(self):
        models.download_models(None, self.spec("/good", "/missing"), self.folder)
        self.assertEqual(Handler.hits, ["/good"])

    def test_all_mirrors_bad_raises_with_every_reason_and_leaves_nothing(self):
        specs = self.spec("/missing", "/error-page", "/wrong-content")
        with self.assertRaises(RuntimeError) as cm:
            models.download_models(None, specs, self.folder)
        message = str(cm.exception)
        self.assertIn("m.onnx", message)
        for path in ("/missing", "/error-page", "/wrong-content"):
            self.assertIn(path, message)
        self.assertIn("checksum", message)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_unreachable_server_is_reported_not_raised_raw(self):
        spec = {"m.onnx": models.ModelSpec(urls=("http://127.0.0.1:9/never",), size=1, sha256="0" * 64, min_size=1)}
        with self.assertRaises(RuntimeError) as cm:
            models.download_models(None, spec, self.folder)
        self.assertIn("http://127.0.0.1:9/never", str(cm.exception))

    def test_installed_files_are_left_alone_and_pointer_stubs_are_replaced(self):
        specs = self.spec("/good")
        (self.folder / "m.onnx").write_bytes(b"a hand-placed model that is big enough" * 10)
        self.assertEqual(models.missing_models(specs, self.folder), [])
        models.download_models(None, specs, self.folder)
        self.assertEqual(Handler.hits, [])                                     # nothing fetched
        (self.folder / "m.onnx").write_bytes(b"version https://git-lfs.github.com/spec/v1\n")   # a Git LFS stub
        self.assertEqual(models.missing_models(specs, self.folder), ["m.onnx"])
        models.download_models(None, specs, self.folder)
        self.assertEqual((self.folder / "m.onnx").read_bytes(), GOOD)

    def test_official_specs_are_complete(self):
        self.assertEqual(sorted(models.MODELS), ["face_detection_yunet_2023mar.onnx",
                                                 "face_recognition_sface_2021dec.onnx"])
        for name, spec in models.MODELS.items():
            self.assertEqual(len(spec.sha256), 64, name)
            self.assertGreaterEqual(len(spec.urls), 2, name)                   # a primary and a fallback mirror
            self.assertTrue(all(u.startswith("https://") and u.endswith(name) for u in spec.urls), name)
            self.assertLess(spec.min_size, spec.size, name)
        self.assertEqual(models.DETECTOR.name, "face_detection_yunet_2023mar.onnx")
        self.assertEqual(models.RECOGNIZER.name, "face_recognition_sface_2021dec.onnx")


if __name__ == "__main__":
    unittest.main()
