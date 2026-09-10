"""Stdlib regression tests for the static index generator."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_index as g


class IngestionMetadataTests(unittest.TestCase):
    def test_missing_date_stays_unknown(self):
        self.assertEqual(g.ingestion_date(''), ('', ''))

    def test_date_only_has_timezone_independent_order(self):
        self.assertEqual(g.ingestion_date('2026-09-10'),
                         ('2026-09-10', '2026-09-10T00:00:00+00:00'))

    def test_rejects_ambiguous_or_malformed_dates(self):
        for value in ['20260910', '2026-02-30', '2026-09-10T16:27:00',
                      '2026-09-10 16:27:00-07:00', 'yesterday',
                      '2026-09-10T16:27:00+25:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                g.ingestion_date(value)

    def test_offsets_sort_by_instant_not_local_calendar(self):
        earlier = g.ingestion_date('2026-09-11T00:15:00+02:00')
        later = g.ingestion_date('2026-09-10T16:27:00-07:00')
        self.assertLess(earlier[1], later[1])
        self.assertEqual(earlier[0], '2026-09-11')
        self.assertEqual(g.ingestion_date('2026-09-10T23:27:00Z'), later)

    def test_ingestion_timestamp_reaches_generated_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / 'shared' / 'example' / 'index.html'
            site.parent.mkdir(parents=True)
            site.write_text(
                '<!DOCTYPE html>\n<!-- index:\n'
                'ingested: 2026-09-10T16:27:00-07:00\n-->\n'
                '<title>Example</title>', encoding='utf-8')
            entries = g.collect(root)
            output = g.build_html(entries)
            payload = json.loads(re.search(r'const SITES = (.*?);\n', output)[1])
            self.assertEqual(payload[0].get('ingested_date'), '2026-09-10')
            self.assertEqual(payload[0].get('ingested_sort'), '2026-09-10T23:27:00+00:00')
            self.assertIn('datetime="2026-09-10"', output)


if __name__ == '__main__':
    unittest.main()
