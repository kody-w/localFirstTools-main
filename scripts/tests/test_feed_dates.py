"""RSS 2.0 dates must remain RFC 822 parseable."""

from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_feeds import rss_date


def test_rss_date_formats_manifest_dates():
    assert rss_date("2026-08-15") == "Sat, 15 Aug 2026 00:00:00 GMT"


def test_generated_rss_dates_are_parseable():
    root = ET.parse(ROOT / "apps" / "feed.xml").getroot()
    channel = root.find("channel")
    assert channel is not None
    last_build = channel.findtext("lastBuildDate")
    assert parsedate_to_datetime(last_build) is not None
    dates = [
        item.findtext("pubDate")
        for item in channel.findall("item")
    ]
    assert dates
    assert all(parsedate_to_datetime(value) is not None for value in dates)
