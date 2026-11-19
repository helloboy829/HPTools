import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiperf.datasets import (
    DatasetFormat,
    DatasetImportError,
    DatasetReaderOptions,
    iter_dataset_cases,
)


class DatasetReaderTests(unittest.TestCase):
    def test_csv_keeps_cells_as_strings_and_preserves_case_order_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text(
                "case_id,prompt,expected,payload,component_id\n"
                "first,001,false,,component-a\n"
                "second,hello,true,{\"x\":1},component-b\n",
                encoding="utf-8-sig",
            )

            cases = tuple(iter_dataset_cases(path, DatasetFormat.CSV))

        self.assertEqual([case.ordinal for case in cases], [1, 2])
        self.assertEqual([case.case_id for case in cases], ["first", "second"])
        self.assertEqual(cases[0].values, {"prompt": "001"})
        self.assertEqual(cases[0].component_id, "component-a")
        self.assertEqual(cases[0].expected, "false")
        self.assertEqual(cases[0].payload, "")
        self.assertEqual(cases[1].payload, '{"x":1}')
        self.assertEqual(cases[1].provenance["source_line"], 3)

    def test_csv_keeps_source_provenance_as_case_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text("case_id,provenance,prompt\none,revision-2,hello\n", encoding="utf-8")

            case = next(iter_dataset_cases(path, DatasetFormat.CSV))

        self.assertEqual(case.provenance["source_metadata"], "revision-2")
        self.assertEqual(case.values, {"prompt": "hello"})

    def test_csv_rejects_duplicate_case_ids_without_echoing_row_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text("case_id,prompt\none,secret-one\none,secret-two\n", encoding="utf-8")

            with self.assertRaises(DatasetImportError) as raised:
                tuple(iter_dataset_cases(path, DatasetFormat.CSV))

        self.assertEqual(raised.exception.code, "DATASET_IMPORT_ERROR")
        self.assertEqual(raised.exception.details["row"], 3)
        self.assertEqual(raised.exception.details["field"], "case_id")
        self.assertNotIn("secret-two", str(raised.exception.to_dict()))

    def test_csv_rejects_duplicate_headers_and_wrong_row_width(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            duplicate = Path(temporary) / "duplicate.csv"
            duplicate.write_text("prompt,prompt\na,b\n", encoding="utf-8")
            width = Path(temporary) / "width.csv"
            width.write_text("prompt,expected\na\n", encoding="utf-8")

            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(duplicate, DatasetFormat.CSV))
            with self.assertRaises(DatasetImportError) as raised:
                tuple(iter_dataset_cases(width, DatasetFormat.CSV))

        self.assertEqual(raised.exception.details["row"], 2)

    def test_csv_blank_rows_require_an_explicit_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text("prompt\na\n\nb\n", encoding="utf-8")

            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(path, DatasetFormat.CSV))

            cases = tuple(
                iter_dataset_cases(
                    path,
                    DatasetFormat.CSV,
                    options=DatasetReaderOptions(skip_blank_rows=True),
                )
            )

        self.assertEqual([case.values["prompt"] for case in cases], ["a", "b"])
        self.assertEqual([case.ordinal for case in cases], [1, 2])

    def test_missing_case_ids_are_deterministically_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.jsonl"
            path.write_text('{"values":{"prompt":"one"}}\n{"values":{"prompt":"two"}}\n', encoding="utf-8")

            cases = tuple(iter_dataset_cases(path, DatasetFormat.JSONL))

        self.assertEqual([case.case_id for case in cases], ["row-000001", "row-000002"])
        self.assertTrue(all(case.provenance["case_id_generated"] is True for case in cases))

    def test_csv_preserves_json_looking_values_and_generates_id_for_blank_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text('case_id,values\n,"{""x"":1}"\n', encoding="utf-8")

            case = next(iter_dataset_cases(path, DatasetFormat.CSV))

        self.assertEqual(case.case_id, "row-000001")
        self.assertEqual(case.values, {"values": '{"x":1}'})

    def test_empty_optional_attachment_path_is_preserved_as_no_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.jsonl"
            path.write_text('{"input_paths":""}\n', encoding="utf-8")

            case = next(iter_dataset_cases(path, DatasetFormat.JSONL))

        self.assertEqual(case.input_paths, "")

    def test_csv_multiline_record_provenance_points_to_the_starting_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.csv"
            path.write_text('case_id,prompt\none,"line one\nline two"\ntwo,done\n', encoding="utf-8")

            cases = tuple(iter_dataset_cases(path, DatasetFormat.CSV))

        self.assertEqual([case.provenance["source_line"] for case in cases], [2, 4])

    def test_json_array_streams_large_record_and_keeps_numeric_value_at_chunk_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            large_value = "x" * (64 * 1024 + 11)
            path.write_text(
                json.dumps([{"case_id": "large", "values": {"text": large_value}}, {"case_id": "number", "expected": 1}]),
                encoding="utf-8",
            )

            cases = tuple(iter_dataset_cases(path, DatasetFormat.JSON))

        self.assertEqual(cases[0].values["text"], large_value)
        self.assertEqual(cases[1].expected, 1)

    def test_json_array_records_include_their_starting_physical_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text('[\n  {"case_id":"first"},\n\n  {"case_id":"second"}\n]\n', encoding="utf-8")

            cases = tuple(iter_dataset_cases(path, DatasetFormat.JSON))

        self.assertEqual([case.provenance["source_line"] for case in cases], [2, 4])

    def test_json_array_counts_cr_only_line_endings_in_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_bytes(b'[\r {"case_id":"first"},\r {"case_id":"second"}\r]')

            cases = tuple(iter_dataset_cases(path, DatasetFormat.JSON))

        self.assertEqual([case.provenance["source_line"] for case in cases], [2, 3])

    def test_json_array_handles_scalars_split_across_read_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text('[{"expected":1.23456789e-12},{"expected":true}]', encoding="utf-8")

            with patch("aiperf.datasets.reader._JSON_CHUNK_SIZE", 8):
                cases = tuple(iter_dataset_cases(path, DatasetFormat.JSON))

        self.assertAlmostEqual(cases[0].expected, 1.23456789e-12)
        self.assertIs(cases[1].expected, True)

    def test_json_keeps_native_values_and_preserves_unknown_case_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "case_id": "typed",
                            "values": {"count": 3, "enabled": False, "history": []},
                            "component_id": "component-1",
                            "payload": None,
                            "expected": {"rules": ["x"], "threshold": 0.5},
                            "source": {"revision": 2},
                            "metadata": {"labels": ["smoke"]},
                            "asset_refs": [{"asset_id": "a-1", "role": "input"}],
                            "provenance": {"source_revision": 7},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            case = next(iter_dataset_cases(path, DatasetFormat.JSON))

        self.assertEqual(case.values, {"count": 3, "enabled": False, "history": []})
        self.assertEqual(case.component_id, "component-1")
        self.assertIsNone(case.payload)
        self.assertEqual(case.expected, {"rules": ["x"], "threshold": 0.5})
        self.assertEqual(case.source, {"revision": 2})
        self.assertEqual(case.metadata, {"labels": ["smoke"]})
        self.assertEqual(case.asset_refs, [{"asset_id": "a-1", "role": "input"}])
        self.assertIsNone(case.input_paths)
        self.assertEqual(case.provenance["source_metadata"], {"source_revision": 7})

    def test_json_array_reader_yields_before_parsing_the_entire_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text('[{"case_id":"first"}, {"case_id":"second"}] trailing', encoding="utf-8")
            cases = iter_dataset_cases(path, DatasetFormat.JSON)

            first = next(cases)
            self.assertEqual(first.case_id, "first")
            self.assertEqual(next(cases).case_id, "second")
            with self.assertRaises(DatasetImportError):
                next(cases)

    def test_jsonl_preserves_serialized_json_strings_and_reports_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.jsonl"
            path.write_text(
                '{"case_id":"one","values":{"body":"{\\"a\\":1}"}}\n'
                '{"case_id":"two","expected":[1,false,null]}\n',
                encoding="utf-8",
            )

            cases = tuple(iter_dataset_cases(path, DatasetFormat.JSONL))

        self.assertEqual(cases[0].values["body"], '{"a":1}')
        self.assertEqual(cases[1].expected, [1, False, None])
        self.assertEqual([case.provenance["source_line"] for case in cases], [1, 2])

    def test_jsonl_is_incremental_and_reports_safe_line_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.jsonl"
            path.write_text('{"case_id":"one"}\nnot-json-secret\n', encoding="utf-8")
            cases = iter_dataset_cases(path, DatasetFormat.JSONL)

            self.assertEqual(next(cases).case_id, "one")
            with self.assertRaises(DatasetImportError) as raised:
                next(cases)

        self.assertEqual(raised.exception.details["row"], 2)
        self.assertNotIn("not-json-secret", str(raised.exception.to_dict()))

    def test_invalid_utf8_is_reported_without_chaining_raw_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.jsonl"
            path.write_bytes(b'prompt\nsecret-\xff\n')

            with self.assertRaises(DatasetImportError) as raised:
                tuple(iter_dataset_cases(path, DatasetFormat.JSONL))

        self.assertTrue(raised.exception.__suppress_context__)
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn("secret-", str(raised.exception.to_dict()))

    def test_json_rejects_non_array_root_and_non_object_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root.json"
            root.write_text('{"cases":[]}', encoding="utf-8")
            row = Path(temporary) / "row.json"
            row.write_text('[1]', encoding="utf-8")

            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(root, DatasetFormat.JSON))
            with self.assertRaises(DatasetImportError) as raised:
                tuple(iter_dataset_cases(row, DatasetFormat.JSON))

        self.assertEqual(raised.exception.details["row"], 1)

    def test_json_rejects_duplicate_object_fields_and_nonstandard_constants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            duplicate = Path(temporary) / "duplicate.jsonl"
            duplicate.write_text('{"values":{"x":1,"x":2}}\n', encoding="utf-8")
            constant = Path(temporary) / "constant.json"
            constant.write_text('[{"value":NaN}]', encoding="utf-8")
            overflow = Path(temporary) / "overflow.json"
            overflow.write_text('[{"value":1e999}]', encoding="utf-8")
            whitespace = Path(temporary) / "whitespace.json"
            whitespace.write_bytes(b"[\x0b{\"value\":1}]")

            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(duplicate, DatasetFormat.JSONL))
            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(constant, DatasetFormat.JSON))
            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(overflow, DatasetFormat.JSON))
            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(whitespace, DatasetFormat.JSON))

    def test_attachment_paths_are_confined_to_the_dataset_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "dataset"
            root.mkdir()
            (root / "input.txt").write_text("safe", encoding="utf-8")
            cases_path = root / "cases.jsonl"
            options = DatasetReaderOptions(attachment_fields=("attachment",))

            for reference in ("../outside.txt", "C:\\outside.txt", "/outside.txt", "missing.txt"):
                cases_path.write_text(
                    json.dumps({"values": {"prompt": "x", "attachment": reference}}),
                    encoding="utf-8",
                )
                with self.subTest(reference_kind=reference.split(":")[0]):
                    with self.assertRaises(DatasetImportError) as raised:
                        tuple(
                            iter_dataset_cases(
                                cases_path,
                                DatasetFormat.JSONL,
                                dataset_root=root,
                                options=options,
                            )
                        )
                    self.assertEqual(raised.exception.details["field"], "attachment")
                    self.assertNotIn(reference, str(raised.exception.to_dict()))

            cases_path.write_text(
                json.dumps({"values": {"prompt": "x", "attachment": "input.txt"}}),
                encoding="utf-8",
            )
            case = next(
                iter_dataset_cases(
                    cases_path,
                    DatasetFormat.JSONL,
                    dataset_root=root,
                    options=options,
                )
            )

        self.assertEqual(case.values["attachment"], "input.txt")

    def test_input_paths_are_validated_without_changing_the_original_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "asset.bin").write_bytes(b"asset")
            path = root / "cases.json"
            path.write_text(
                json.dumps([{"input_paths": ["asset.bin"], "payload": {"items": [1]}}]),
                encoding="utf-8",
            )

            case = next(iter_dataset_cases(path, DatasetFormat.JSON, dataset_root=root))

        self.assertEqual(case.input_paths, ["asset.bin"])
        self.assertEqual(case.payload, {"items": [1]})

    def test_attachment_path_requires_root_and_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "dataset"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            case_path = root / "cases.jsonl"
            case_path.write_text('{"input_paths":"../outside.txt"}', encoding="utf-8")

            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(case_path, DatasetFormat.JSONL))

            symlink = root / "escape.txt"
            try:
                symlink.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this Windows host")

            case_path.write_text('{"input_paths":"escape.txt"}', encoding="utf-8")
            with self.assertRaises(DatasetImportError):
                tuple(iter_dataset_cases(case_path, DatasetFormat.JSONL, dataset_root=root))

    def test_asset_ref_paths_are_checked_but_asset_ids_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "asset.txt").write_text("asset", encoding="utf-8")
            path = root / "cases.jsonl"
            path.write_text(
                '{"asset_refs":[{"asset_id":"managed-1"},{"path":"asset.txt","role":"input"}]}\n',
                encoding="utf-8",
            )

            case = next(iter_dataset_cases(path, DatasetFormat.JSONL, dataset_root=root))

        self.assertEqual(
            case.asset_refs,
            [{"asset_id": "managed-1"}, {"path": "asset.txt", "role": "input"}],
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "cases.jsonl"
            path.write_text('{"asset_refs":[{"path":"../escape.txt"}]}\n', encoding="utf-8")

            with self.assertRaises(DatasetImportError) as raised:
                tuple(iter_dataset_cases(path, DatasetFormat.JSONL, dataset_root=root))

        self.assertEqual(raised.exception.details["field"], "asset_refs[0].path")
        self.assertNotIn("escape.txt", str(raised.exception.to_dict()))


if __name__ == "__main__":
    unittest.main()
