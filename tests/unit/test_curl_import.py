import unittest

from aiperf.requests import BodyKind, CurlImportError, parse_curl


class CurlImportTests(unittest.TestCase):
    def test_imports_request_headers_query_and_json_body(self) -> None:
        result = parse_curl(
            "curl --request POST 'https://example.test/api?fixed=1' "
            "-H 'Content-Type: application/json' -H 'X-Trace: abc' "
            "--data-raw '{\"prompt\":\"hello\"}'"
        )

        step = result.request.steps[0]
        self.assertEqual(step.method, "POST")
        self.assertEqual(step.url, "https://example.test/api")
        self.assertEqual([(item.name, item.value) for item in step.query], [("fixed", "1")])
        self.assertEqual(step.body.kind, BodyKind.JSON)
        self.assertEqual(step.body.value, {"prompt": "hello"})
        self.assertEqual(result.warnings, ())

    def test_preserves_repeated_headers_and_multipart_file_as_hint(self) -> None:
        result = parse_curl(
            "curl https://example.test/upload -H 'X-Tag: one' -H 'X-Tag: two' "
            "-F 'prompt=hello' -F 'files=@C:/private/report.pdf'"
        )

        step = result.request.steps[0]
        self.assertEqual([header.value for header in step.headers if header.name == "X-Tag"], ["one", "two"])
        self.assertEqual(step.body.kind, BodyKind.MULTIPART)
        file_part = step.body.parts[1]
        self.assertTrue(file_part.is_file)
        self.assertEqual(file_part.value, "C:/private/report.pdf")
        self.assertIn("file path was retained only as an import hint", result.warnings[0])

    def test_replaces_sensitive_values_with_secret_references(self) -> None:
        result = parse_curl(
            "curl 'https://example.test?token=real-token' "
            "-H 'Authorization: Bearer real-auth' -F 'api_key=real-key'"
        )

        step = result.request.steps[0]
        self.assertEqual(step.query[0].value, "{{secrets.TOKEN}}")
        self.assertEqual(step.headers[0].value, "{{secrets.AUTHORIZATION}}")
        self.assertEqual(step.body.parts[0].value, "{{secrets.API_KEY}}")
        self.assertEqual(result.credential_refs, ("API_KEY", "AUTHORIZATION", "TOKEN"))
        self.assertNotIn("real-", repr(result))

    def test_rejects_shell_operators_and_unsupported_options(self) -> None:
        for command in (
            "curl https://example.test | powershell -Command whoami",
            "curl https://example.test && echo unsafe",
            "curl https://example.test; echo unsafe",
            "curl https://example.test > output.txt",
            "curl https://example.test $(whoami)",
            "curl https://example.test `whoami`",
            "curl https://example.test --config secrets.txt",
            "curl https://example.test --next https://other.test",
            "curl https://example.test --proxy-command evil",
            "curl https://example.test --unknown value",
            "curl https://example.test -d @private.json",
            "curl https://example.test --data-binary @private.bin",
            "curl https://example.test -F 'file=<private.txt'",
            "curl https://example.test -F 'file=@private.txt;type=text/plain'",
        ):
            with self.subTest(command=command):
                with self.assertRaises(CurlImportError):
                    parse_curl(command)

    def test_accepts_equals_forms_and_preserves_duplicate_query_and_form_fields(self) -> None:
        result = parse_curl(
            "curl --url='https://example.test/path?a=1&a=2' "
            "--request=POST --header='Content-Type: application/x-www-form-urlencoded' "
            "--data=x=1 --data=y=2"
        )

        step = result.request.steps[0]
        self.assertEqual([(item.name, item.value) for item in step.query], [("a", "1"), ("a", "2")])
        self.assertEqual(step.method, "POST")
        self.assertEqual(step.body.kind, BodyKind.FORM)
        self.assertEqual(step.body.value, (("x", "1"), ("y", "2")))

    def test_redacts_secrets_inside_json_body(self) -> None:
        result = parse_curl(
            "curl https://example.test -H 'Content-Type: application/json' "
            "--data-raw '{\"prompt\":\"hello\",\"api_key\":\"private-value\"}'"
        )
        body = result.request.steps[0].body.value
        self.assertEqual(body, {"prompt": "hello", "api_key": "{{secrets.API_KEY}}"})
        self.assertEqual(result.credential_refs, ("API_KEY",))
        self.assertNotIn("private-value", repr(result))

    def test_rejects_malformed_json_without_echoing_payload(self) -> None:
        with self.assertRaises(CurlImportError) as raised:
            parse_curl(
                "curl https://example.test -H 'Content-Type: application/json' "
                "--data-raw '{\"password\":\"private-value\"'"
            )
        self.assertNotIn("private-value", str(raised.exception))

    def test_data_raw_treats_leading_at_as_literal_text(self) -> None:
        result = parse_curl("curl https://example.test --data-raw @literal-text")
        self.assertEqual(result.request.steps[0].body.value, "@literal-text")

    def test_combines_repeated_data_options_in_curl_order(self) -> None:
        result = parse_curl("curl https://example.test -d first=1 --data-raw second=2")
        self.assertEqual(result.request.steps[0].body.value, "first=1&second=2")

    def test_rejects_url_userinfo_and_redacts_malformed_secret_inputs(self) -> None:
        with self.assertRaises(CurlImportError) as raised:
            parse_curl("curl https://user:super-secret@example.test")
        self.assertNotIn("super-secret", str(raised.exception))

        with self.assertRaises(CurlImportError) as raised:
            parse_curl("curl https://example.test -H 'Authorization: super-secret' -X")
        self.assertNotIn("super-secret", str(raised.exception))

        with self.assertRaises(CurlImportError):
            parse_curl("curl 'https://@example.test/'")

    def test_drops_url_fragment_from_http_request_target(self) -> None:
        result = parse_curl("curl 'https://example.test/path?x=1#client-fragment'")
        step = result.request.steps[0]
        self.assertEqual(step.url, "https://example.test/path")
        self.assertEqual([(item.name, item.value) for item in step.query], [("x", "1")])

    def test_rejects_empty_or_non_curl_input(self) -> None:
        for command in ("", "wget https://example.test", "curl"):
            with self.subTest(command=command):
                with self.assertRaises(CurlImportError):
                    parse_curl(command)


if __name__ == "__main__":
    unittest.main()
