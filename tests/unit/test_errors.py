import unittest

from aiperf.errors import AIperfError


class AIperfErrorTests(unittest.TestCase):
    def test_to_dict_redacts_sensitive_detail_fields(self) -> None:
        error = AIperfError(
            "REQUEST_BUILD_ERROR",
            "Request could not be built",
            {"field": "headers.Authorization", "Authorization": "Bearer sensitive", "row": 4},
        )

        self.assertEqual(
            error.to_dict(),
            {
                "code": "REQUEST_BUILD_ERROR",
                "message": "Request could not be built",
                "details": {
                    "field": "headers.Authorization",
                    "Authorization": "[REDACTED]",
                    "row": 4,
                },
            },
        )

    def test_exception_string_does_not_include_details(self) -> None:
        error = AIperfError("BAD_INPUT", "Invalid request", {"password": "sensitive"})

        self.assertEqual(str(error), "Invalid request")
        self.assertNotIn("sensitive", str(error))

    def test_empty_details_are_omitted(self) -> None:
        error = AIperfError("BAD_INPUT", "Invalid request")

        self.assertEqual(error.to_dict(), {"code": "BAD_INPUT", "message": "Invalid request"})


if __name__ == "__main__":
    unittest.main()
