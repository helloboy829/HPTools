import unittest

from aiperf.requests.models import (
    BodyKind,
    MultipartPart,
    NameValue,
    RequestBody,
    RequestSpec,
    RequestStep,
)


class RequestModelTests(unittest.TestCase):
    def test_normalizes_method_and_preserves_duplicate_ordered_values(self) -> None:
        step = RequestStep(
            "step-1",
            "Upload",
            "post",
            "/upload",
            query=(NameValue("tag", "one"), NameValue("tag", "two")),
            headers=(NameValue("X-Test", "a"), NameValue("X-Test", "b")),
        )

        self.assertEqual(step.method, "POST")
        self.assertEqual([item.value for item in step.query], ["one", "two"])
        self.assertEqual([item.value for item in step.headers], ["a", "b"])

    def test_accepts_ordered_multipart_parts(self) -> None:
        body = RequestBody(
            BodyKind.MULTIPART,
            parts=(
                MultipartPart("prompt", "summarize"),
                MultipartPart("files", "docs/a.pdf", is_file=True, filename="a.pdf"),
                MultipartPart("files", "docs/b.pdf", is_file=True, filename="b.pdf"),
            ),
        )

        self.assertEqual([part.name for part in body.parts], ["prompt", "files", "files"])

    def test_rejects_invalid_step_and_duplicate_step_ids(self) -> None:
        with self.assertRaises(ValueError):
            RequestStep("", "name", "GET", "/")
        with self.assertRaises(ValueError):
            RequestStep("step", "name", "TRACE", "/")
        with self.assertRaises(ValueError):
            RequestStep("step", "name", "GET", "/", timeout_seconds=0)
        with self.assertRaises(ValueError):
            RequestSpec((RequestStep("same", "one", "GET", "/"), RequestStep("same", "two", "GET", "/")))

    def test_rejects_empty_names_and_invalid_multipart_parts(self) -> None:
        with self.assertRaises(ValueError):
            NameValue("", "value")
        with self.assertRaises(ValueError):
            MultipartPart("", "value")
        with self.assertRaises(ValueError):
            MultipartPart("file", "path", is_file=True)


if __name__ == "__main__":
    unittest.main()
