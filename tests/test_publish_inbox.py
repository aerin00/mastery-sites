"""Stdlib tests for publish_inbox.py: metadata extraction, validation, LLM reply parsing."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_inbox as p

PAGE = ('<!DOCTYPE html><html><head><title>Copilot &amp; Flows</title>'
        '<meta name="description" content="How flows hand off to Copilot.">'
        '<style>.x{color:red}</style></head>'
        '<body><script>var a=1;</script><h1>Hello</h1><p>World  text</p></body></html>')
CATS = ['shared', 'sharepoint']


class ExtractionTests(unittest.TestCase):
    def test_title_is_unescaped(self):
        self.assertEqual(p.page_title(PAGE), 'Copilot & Flows')

    def test_visible_text_drops_head_script_and_style(self):
        self.assertEqual(p.visible_text(PAGE), 'Hello World text')
        self.assertEqual(p.visible_text(PAGE, limit=5), 'Hello')

    def test_filename_target(self):
        self.assertEqual(p.from_filename('shared--my-site.html'), ('shared', 'my-site'))
        self.assertIsNone(p.from_filename('my-site.html'))

    def test_local_plan_prefers_meta_description(self):
        plan = p.local_plan(Path('sharepoint--flows.html'), PAGE)
        self.assertEqual(plan['description'], 'How flows hand off to Copilot.')
        no_meta = p.local_plan(Path('shared--x.html'), '<title>Only Title</title>')
        self.assertEqual(no_meta['description'], 'Only Title')
        with self.assertRaises(ValueError):
            p.local_plan(Path('plain.html'), PAGE)


class ValidateTests(unittest.TestCase):
    def ok(self, **kw):
        plan = {'category': 'shared', 'slug': 'new-site', 'description': 'd', 'tags': ['a']}
        plan.update(kw)
        return p.validate(plan, CATS, {'shared/taken'})

    def test_normalizes_case_whitespace_and_tags(self):
        out = self.ok(category=' Shared ', slug='New-Site', description='one\n line',
                      tags='Power Automate, copilot ,, x, y, z')
        self.assertEqual(out, {'category': 'shared', 'slug': 'new-site', 'description': 'one line',
                               'tags': ['power-automate', 'copilot', 'x', 'y']})

    def test_rejects_unknown_category_bad_slug_taken_and_empty(self):
        for kw in [{'category': 'fitness'}, {'slug': 'bad slug'}, {'slug': 'taken'},
                   {'slug': ''}, {'description': '  '}]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.ok(**kw)

    def test_long_description_is_trimmed(self):
        out = self.ok(description='w' * 400)
        self.assertEqual(len(out['description']), p.DESC_LIMIT)
        self.assertTrue(out['description'].endswith('…'))


class LlmPlanTests(unittest.TestCase):
    def reply(self, content):
        body = json.dumps({'choices': [{'message': {'content': content}}]}).encode()
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(body)
        return resp

    def test_sends_model_categories_and_text_and_parses_fenced_json(self):
        content = '```json\n{"category": "shared", "slug": "x", "description": "d", "tags": []}\n```'
        with mock.patch.object(p.urllib.request, 'urlopen', return_value=self.reply(content)) as op:
            plan = p.llm_plan(PAGE, CATS, 'm/model', 'k')
        self.assertEqual(plan['slug'], 'x')
        req = op.call_args[0][0]
        sent = json.loads(req.data)
        self.assertEqual(sent['model'], 'm/model')
        self.assertIn('shared, sharepoint', sent['messages'][0]['content'])
        self.assertIn('Hello World text', sent['messages'][0]['content'])
        self.assertEqual(req.get_header('Authorization'), 'Bearer k')

    def test_non_json_reply_raises(self):
        with mock.patch.object(p.urllib.request, 'urlopen', return_value=self.reply('no idea')):
            with self.assertRaises(ValueError):
                p.llm_plan(PAGE, CATS, 'm', 'k')


class DryRunTests(unittest.TestCase):
    def test_dry_run_plans_without_importing_or_pushing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'inbox').mkdir()
            (root / 'inbox' / 'shared--fresh.html').write_text(PAGE, encoding='utf-8')
            (root / 'inbox' / 'shared--taken.html').write_text(PAGE, encoding='utf-8')
            (root / 'shared' / 'taken').mkdir(parents=True)
            (root / 'shared' / 'taken' / 'index.html').write_text(PAGE, encoding='utf-8')
            out = io.StringIO()
            with mock.patch.object(p, 'ROOT', root), mock.patch.object(p, 'INBOX', root / 'inbox'), \
                 mock.patch.object(sys, 'argv', ['publish_inbox.py', '--dry-run']), \
                 mock.patch.object(p.subprocess, 'run') as sub, mock.patch('sys.stdout', out):
                p.main()
            sub.assert_not_called()
            self.assertIn('-> shared/fresh', out.getvalue())
            self.assertIn('SKIP shared--taken.html: shared/taken already exists', out.getvalue())
            self.assertFalse((root / 'shared' / 'fresh').exists())


if __name__ == '__main__':
    unittest.main()
