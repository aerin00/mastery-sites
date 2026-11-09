"""Stdlib regression tests for the static index generator."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

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


class LintTests(unittest.TestCase):
    def _site(self, root, cat, slug, text):
        p = root / cat / slug / 'index.html'
        p.parent.mkdir(parents=True)
        p.write_text(text, encoding='utf-8')

    def test_complete_site_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._site(root, 'shared', 'ok',
                       '<!-- index:\ndescription: fine\ningested: 2026-09-21\n-->'
                       '<title>T</title><body><nav id="ms-homebar"></nav></body>')
            self.assertEqual(g.lint(root, g.collect(root)), [])

    def test_reports_each_missing_field(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._site(root, 'mystery', 'bare', '<title>T</title><body></body>')
            problems = '\n'.join(g.lint(root, g.collect(root)))
            for needle in ['no description', 'no ingested', 'All-sites bar', 'CATEGORY_DOTS',
                           'CATEGORY_BLURBS']:
                self.assertIn(needle, problems)

    def test_category_named_after_builtin_view_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._site(root, 'recent', 'x', '<title>T</title><body></body>')
            self.assertIn('collides with a built-in nav view',
                          '\n'.join(g.lint(root, g.collect(root))))


class ImportSiteTests(unittest.TestCase):
    def setUp(self):
        import import_site
        self.m = import_site
        self.src = ('<!DOCTYPE html>\n<html><head><title>Page</title></head>'
                    '<body class="x"><p>hello</p></body></html>')

    def test_build_page_inserts_front_matter_and_bar(self):
        out = self.m.build_page(self.src, 'desc', 'a, b', True, '2026-09-21T10:00:00-07:00')
        self.assertTrue(out.startswith('<!DOCTYPE html>\n<!-- index:\ndescription: desc\ntags: a, b\npinned: true\ningested: 2026-09-21T10:00:00-07:00\n-->\n<html>'))
        self.assertIn('<body class="x"><nav id="ms-homebar"', out)
        self.assertEqual(g.parse_front_matter(out)['tags'], ['a', 'b'])

    def test_fingerprint_ignores_injected_metadata(self):
        out = self.m.build_page(self.src, 'desc', '', False, '2026-09-21')
        self.assertEqual(self.m.fingerprint(out), self.m.fingerprint(self.src))
        self.assertNotEqual(self.m.fingerprint(out), self.m.fingerprint(self.src + '<!-- x -->'))

    def test_rejects_source_without_title_or_body(self):
        with self.assertRaises(SystemExit):
            self.m.build_page('<html><body></body></html>', 'd', '', False, '2026-09-21')
        with self.assertRaises(SystemExit):
            self.m.build_page('<title>t</title><div></div>', 'd', '', False, '2026-09-21')

    def _run(self, root, *argv):
        with mock.patch.object(self.m, 'ROOT', root), \
             mock.patch.object(sys, 'argv', ['import_site.py', *argv]), \
             mock.patch.object(self.m.subprocess, 'run') as generator:
            self.m.main()
        return generator

    def test_lifecycle_new_imported_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'repo'
            inbox = Path(d) / 'inbox'
            inbox.mkdir(parents=True)
            src = inbox / 'page.html'
            src.write_text(self.src, encoding='utf-8')
            dest = root / 'shared' / 'page' / 'index.html'
            args = [str(src), 'shared/page', '--description', 'd']
            self.assertEqual(self.m.import_state(self.src, dest), 'new')

            self.assertTrue(self._run(root, *args).called)
            self.assertEqual(self.m.import_state(self.src, dest), 'imported')
            self.assertTrue(src.exists())

            # A plain re-run changes nothing and names the next step.
            with self.assertRaises(SystemExit) as stop:
                self._run(root, *args)
            self.assertIn('re-run with --archive', str(stop.exception))

            # The documented second run only archives; it does not re-import.
            before = dest.read_text(encoding='utf-8')
            self.assertFalse(self._run(root, *args, '--archive').called)
            self.assertEqual(dest.read_text(encoding='utf-8'), before)
            self.assertFalse(src.exists())
            self.assertTrue((inbox / 'archive' / 'page.html').exists())

    def test_different_page_at_target_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'repo'
            src = Path(d) / 'page.html'
            src.write_text(self.src, encoding='utf-8')
            dest = root / 'shared' / 'page' / 'index.html'
            dest.parent.mkdir(parents=True)
            dest.write_text('<title>Other</title><body>other</body>', encoding='utf-8')
            with self.assertRaises(SystemExit) as stop:
                self._run(root, str(src), 'shared/page', '--description', 'd', '--archive')
            self.assertIn('different page', str(stop.exception))
            self.assertTrue(src.exists())

    def test_bad_ingested_or_failed_generator_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'repo'
            root.mkdir()
            src = Path(d) / 'page.html'
            src.write_text(self.src, encoding='utf-8')
            args = [str(src), 'shared/page', '--description', 'd']
            with self.assertRaises(SystemExit):
                self._run(root, *args, '--ingested', 'yesterday')
            self.assertEqual(list(root.iterdir()), [])

            failure = self.m.subprocess.CalledProcessError(1, 'generate_index.py')
            with mock.patch.object(self.m, 'ROOT', root), \
                 mock.patch.object(sys, 'argv', ['import_site.py', *args]), \
                 mock.patch.object(self.m.subprocess, 'run', side_effect=failure), \
                 self.assertRaises(SystemExit):
                self.m.main()
            self.assertEqual(list(root.iterdir()), [])
