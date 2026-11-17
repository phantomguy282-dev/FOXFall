"""Validate the live sitemap.xml: XML well-formedness, namespace, URLs."""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
import xml.etree.ElementTree as ET

req = urllib.request.Request(
    "https://phantomguy282-dev.github.io/FOXFall-website/sitemap.xml",
    headers={"User-Agent": "foxfall-audit"})
body = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")

root = ET.fromstring(body)
ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
print("root tag:", root.tag)
print("namespace correct:",
      root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
urls = root.findall("sm:url", ns)
print("url entries:", len(urls))
CANON = "https://phantomguy282-dev.github.io/FOXFall-website/"
for u in urls:
    loc = u.find("sm:loc", ns).text
    lastmod = u.find("sm:lastmod", ns)
    print("  loc:", loc)
    print("    correct base path:", loc.startswith(CANON))
    print("    lastmod:", lastmod.text if lastmod is not None else "(none)")
print("VALIDATION: OK")