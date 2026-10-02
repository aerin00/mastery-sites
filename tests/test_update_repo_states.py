"""Stdlib regression tests for the repo-states watchlist generator."""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_repo_states as u


NOW = dt.datetime(2026, 10, 2, 21, 0, tzinfo=dt.timezone.utc)


def repo(name: str, pushed_at: str, **kw) -> dict:
    """Minimal repo fixture with sensible defaults."""
    return {
        "name": name,
        "description": kw.get("description"),
        "language": kw.get("language"),
        "pushed_at": pushed_at,
        "archived": kw.get("archived", False),
        "fork": kw.get("fork", False),
        "visibility": kw.get("visibility", "public"),
        "open_issues_count": kw.get("open_issues_count", 0),
        "html_url": f"https://github.com/aerin00/{name}",
    }


class StalenessTests(unittest.TestCase):
    def test_age_days_parses_z_and_offset(self):
        self.assertEqual(u.age_days("2026-10-01T12:00:00Z", NOW), 1)
        self.assertEqual(u.age_days("2026-10-01T12:00:00+00:00", NOW), 1)

    def test_future_push_clamps_to_zero(self):
        self.assertEqual(u.age_days("2026-10-03T00:00:00Z", NOW), 0)

    def test_class_boundaries(self):
        self.assertEqual(u.staleness(0), "fresh")
        self.assertEqual(u.staleness(7), "fresh")
        self.assertEqual(u.staleness(8), "active")
        self.assertEqual(u.staleness(30), "active")
        self.assertEqual(u.staleness(31), "aging")
        self.assertEqual(u.staleness(90), "aging")
        self.assertEqual(u.staleness(91), "dormant")


class RenderTests(unittest.TestCase):
    def test_sorted_by_last_push_descending(self):
        """Row order comes from data-k, so bare-name substring matches
        (e.g. "older" inside "placeholder") cannot fool the assertion."""
        repos = [
            repo("older", "2026-08-01T00:00:00Z"),
            repo("newest", "2026-10-01T00:00:00Z"),
            repo("middle", "2026-09-01T00:00:00Z"),
        ]
        html = u.render_page(repos, NOW)
        order = [k.strip() for k in re.findall(r'data-k="([^"]*)"', html)]
        self.assertEqual(order, ["newest", "middle", "older"])

    def test_escapes_hostile_description(self):
        hostile = '<script>alert("x")</script>'
        html = u.render_page([repo("bad", "2026-10-01T00:00:00Z", description=hostile)], NOW)
        self.assertNotIn(hostile, html)
        self.assertIn("&lt;script&gt;", html)

    def test_page_meets_site_conventions(self):
        """Title, front-matter with fixed ingest date, homebar first in body."""
        html = u.render_page([repo("r", "2026-10-01T00:00:00Z")], NOW)
        self.assertIn("<title>GitHub Repo States</title>", html)
        self.assertIn(f"ingested: {u.INGESTED}", html)
        body = html[html.index("<body>"):]
        self.assertIn('<nav id="ms-homebar"', body[:40], "homebar must lead the body")
        self.assertIn("Data refreshed", html)
        self.assertIn(f'<meta name="generated" content="{NOW.isoformat()}">', html)

    def test_empty_description_row_renders(self):
        html = u.render_page([repo("bare", "2026-10-01T00:00:00Z")], NOW)
        self.assertIn("bare", html)


if __name__ == "__main__":
    unittest.main()
