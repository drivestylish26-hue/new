#!/usr/bin/env python3
"""
SiteScan — Automatic On-Page + Technical SEO Diagnostic
Run locally: python seo_scan.py drivestylish.com
Requires: pip install requests beautifulsoup4
"""

import sys
import re
import json
import argparse
from urllib.parse import urljoin, urlparse
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing packages. Run: pip install requests beautifulsoup4")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SiteScanBot/1.0"
}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[38;5;203m"
AMBER = "\033[38;5;214m"
GREEN = "\033[38;5;114m"
BLUE = "\033[38;5;111m"

SHOPIFY_TIPS = {
    "Title tag": "Edit under Online Store > Preferences (homepage) or the 'Search engine listing' box on each product/collection.",
    "Meta description": "Set per-page in the 'Search engine listing' edit box at the bottom of each product/collection/page editor.",
    "Image alt text": "Open the image in Product > Media, click it, and fill the 'Alt text' field.",
    "Mobile viewport tag": "This lives in theme.liquid — usually best left alone unless a recent code edit broke it.",
    "Canonical tag": "Shopify sets this automatically on standard pages; check for a theme override in theme.liquid if missing.",
    "Structured data (schema)": "Add JSON-LD in theme.liquid or via an SEO app — Product schema should pull price/availability from Liquid variables.",
    "XML sitemap": "Shopify auto-generates /sitemap.xml — if unreachable, check for a redirect app or DNS override.",
    "robots.txt": "Shopify allows a robots.txt.liquid override — check Settings > Apps > Themes > Edit code if this looks wrong.",
}


def normalize_url(raw):
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    return raw


def fetch(url, timeout=15):
    return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)


def add(results, label, status, detail, fix=None):
    results.append({"label": label, "status": status, "detail": detail, "fix": fix})


def analyze(url):
    onpage, tech = [], []

    resp = fetch(url)
    html = resp.text
    final_url = resp.url
    origin = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
    soup = BeautifulSoup(html, "html.parser")

    robots_text = None
    try:
        r = fetch(origin + "/robots.txt", timeout=10)
        if r.status_code == 200:
            robots_text = r.text
    except Exception:
        robots_text = None

    sitemap_url = origin + "/sitemap.xml"
    if robots_text:
        m = re.search(r"Sitemap:\s*(\S+)", robots_text, re.I)
        if m:
            sitemap_url = m.group(1).strip()
    sitemap_ok = False
    try:
        r = fetch(sitemap_url, timeout=10)
        sitemap_ok = r.status_code == 200 and len(r.text) > 20
    except Exception:
        sitemap_ok = False

    # ---------------- ON-PAGE ----------------
    title = soup.title.get_text(strip=True) if soup.title else ""
    if not title:
        add(onpage, "Title tag", "critical", "No <title> tag found.",
            "Add a unique, descriptive <title> tag inside <head> — one of the strongest on-page ranking signals.")
    elif len(title) < 15 or len(title) > 65:
        add(onpage, "Title tag", "warning", f'Title is {len(title)} characters: "{title}"',
            "Keep titles 30-60 characters so Google shows the full title. Lead with the primary keyword, end with the brand.")
    else:
        add(onpage, "Title tag", "pass", f'"{title}" ({len(title)} chars)')

    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    if not meta_desc:
        add(onpage, "Meta description", "critical", "No meta description found.",
            "Add a meta description (120-160 characters) with a clear reason to click and the target keyword.")
    elif len(meta_desc) < 70 or len(meta_desc) > 165:
        add(onpage, "Meta description", "warning", f"Length is {len(meta_desc)} characters.",
            "Rewrite to land between 120-160 characters.")
    else:
        add(onpage, "Meta description", "pass", f"{len(meta_desc)} characters — good length.")

    h1s = soup.find_all("h1")
    if len(h1s) == 0:
        add(onpage, "H1 heading", "critical", "No H1 tag found.",
            "Add exactly one H1 per page stating the page topic with the primary keyword.")
    elif len(h1s) > 1:
        add(onpage, "H1 heading", "warning", f"{len(h1s)} H1 tags found.",
            "Use only one H1 per page. Convert extras to H2/H3.")
    else:
        add(onpage, "H1 heading", "pass", f'"{h1s[0].get_text(strip=True)[:80]}"')

    h2_count = len(soup.find_all("h2"))
    if h2_count == 0:
        add(onpage, "Heading structure", "warning", "No H2 subheadings found.",
            "Break content into sections using H2/H3 — helps readability and how Google understands page structure.")
    else:
        add(onpage, "Heading structure", "pass", f"{h2_count} H2 tags, {len(soup.find_all('h3'))} H3 tags found.")

    imgs = soup.find_all("img")
    missing_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    if not imgs:
        add(onpage, "Image alt text", "pass", "No images detected on this page.")
    elif missing_alt:
        sev = "critical" if missing_alt == len(imgs) else "warning"
        add(onpage, "Image alt text", sev, f"{missing_alt} of {len(imgs)} images missing alt text.",
            "Add descriptive alt text to every product/content image.")
    else:
        add(onpage, "Image alt text", "pass", f"All {len(imgs)} images have alt text.")

    canonical = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
    if not canonical:
        add(onpage, "Canonical tag", "warning", "No canonical tag found.",
            "Add a self-referencing canonical tag on every page to prevent duplicate-content issues.")
    else:
        add(onpage, "Canonical tag", "pass", canonical.get("href", ""))

    og_title = soup.find("meta", attrs={"property": re.compile("^og:title$", re.I)})
    og_desc = soup.find("meta", attrs={"property": re.compile("^og:description$", re.I)})
    og_image = soup.find("meta", attrs={"property": re.compile("^og:image$", re.I)})
    if not (og_title and og_desc and og_image):
        missing = [n for n, v in [("og:title", og_title), ("og:description", og_desc), ("og:image", og_image)] if not v]
        add(onpage, "Open Graph tags", "warning", f"Missing: {', '.join(missing)}",
            "Add og:title, og:description, og:image so links look good when shared on WhatsApp/Facebook/Instagram.")
    else:
        add(onpage, "Open Graph tags", "pass", "og:title, og:description and og:image all present.")

    body_text = soup.get_text(" ", strip=True)
    word_count = len(body_text.split())
    if word_count < 250:
        add(onpage, "Content length", "warning", f"Approx. {word_count} words of visible text.",
            "Thin content ranks poorly. Aim for 500+ words on key landing/collection pages.")
    else:
        add(onpage, "Content length", "pass", f"Approx. {word_count} words of visible text.")

    internal, external = 0, 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        try:
            full = urljoin(origin, href)
            if urlparse(full).netloc == urlparse(origin).netloc:
                internal += 1
            else:
                external += 1
        except Exception:
            pass
    add(onpage, "Internal linking",
        "warning" if internal < 3 else "pass",
        f"{internal} internal links, {external} external links.",
        "Add more internal links to related product/collection/blog pages.")

    # ---------------- TECHNICAL ----------------
    is_https = final_url.startswith("https://")
    add(tech, "HTTPS", "pass" if is_https else "critical",
        "Site is served over HTTPS." if is_https else "Site is not using HTTPS.",
        "Move the store to HTTPS — a Google ranking signal and a trust signal for shoppers.")

    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if not viewport:
        add(tech, "Mobile viewport tag", "critical", "No viewport meta tag found.",
            'Add <meta name="viewport" content="width=device-width, initial-scale=1.0">.')
    elif re.search(r"user-scalable=no|maximum-scale=1", viewport.get("content", ""), re.I):
        add(tech, "Mobile viewport tag", "warning", "Viewport blocks pinch-zoom.",
            "Remove user-scalable=no / maximum-scale=1 — hurts accessibility.")
    else:
        add(tech, "Mobile viewport tag", "pass", viewport.get("content", ""))

    html_lang = soup.html.get("lang") if soup.html else None
    add(tech, "HTML lang attribute", "pass" if html_lang else "warning",
        f'lang="{html_lang}"' if html_lang else "No lang attribute on <html>.",
        'Add lang="en" (or correct language) to the <html> tag.')

    robots_meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    robots_content = robots_meta.get("content", "") if robots_meta else ""
    if re.search("noindex", robots_content, re.I):
        add(tech, "Robots meta tag", "critical", f'noindex directive found: "{robots_content}"',
            "Remove the noindex directive immediately if this page should rank.")
    else:
        add(tech, "Robots meta tag", "pass", robots_content or "No blocking directive found.")

    jsonld_types = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or "{}")
            arr = data if isinstance(data, list) else [data]
            for d in arr:
                if isinstance(d, dict) and d.get("@type"):
                    jsonld_types.append(d["@type"])
        except Exception:
            pass
    if not jsonld_types:
        add(tech, "Structured data (schema)", "warning", "No JSON-LD structured data found.",
            "Add JSON-LD — Organization + WebSite site-wide, Product schema on product pages.")
    else:
        add(tech, "Structured data (schema)", "pass", "Found: " + ", ".join(sorted(set(jsonld_types))))

    if robots_text is None:
        add(tech, "robots.txt", "warning", "Could not fetch /robots.txt.",
            "Make sure /robots.txt is publicly accessible.")
    elif re.search(r"Disallow:\s*/\s*(\r?\n|$)", robots_text) and "Disallow: /\n" in (robots_text + "\n") and not re.search(r"Disallow:\s*/\S", robots_text):
        add(tech, "robots.txt", "critical", 'robots.txt appears to block the entire site ("Disallow: /").',
            "Check robots.txt urgently — this stops Google from crawling the whole store.")
    else:
        add(tech, "robots.txt", "pass", "Accessible and does not block the whole site.")

    add(tech, "XML sitemap", "pass" if sitemap_ok else "warning",
        f"Sitemap reachable at {sitemap_url}" if sitemap_ok else f"Could not confirm a working sitemap at {sitemap_url}",
        "Publish an XML sitemap and submit it in Google Search Console.")

    favicon = soup.find("link", attrs={"rel": re.compile("icon", re.I)})
    add(tech, "Favicon", "pass" if favicon else "warning",
        "Favicon link present." if favicon else "No favicon link tag found.",
        "Add a favicon for browser tabs and branded search trust.")

    size_kb = round(len(html.encode("utf-8")) / 1024)
    add(tech, "Page weight (HTML)", "warning" if size_kb > 300 else "pass",
        f"{size_kb} KB of HTML on this page.",
        "Trim unused theme sections/apps and lazy-load below-the-fold content.")

    mixed = len(re.findall(r'src=["\']http://(?!localhost)', html, re.I))
    add(tech, "Mixed content", "warning" if mixed else "pass",
        f"{mixed} resource(s) loaded over plain HTTP." if mixed else "No insecure HTTP resources detected.",
        "Update hardcoded http:// URLs to https://.")

    is_shopify = bool(re.search(r"cdn\.shopify\.com|Shopify\.theme|shopify-features", html, re.I))
    gen_tag = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    if gen_tag and "shopify" in (gen_tag.get("content", "") or "").lower():
        is_shopify = True

    return onpage, tech, is_shopify, final_url


def score_and_grade(onpage, tech):
    all_checks = onpage + tech
    crit = sum(1 for c in all_checks if c["status"] == "critical")
    warn = sum(1 for c in all_checks if c["status"] == "warning")
    passed = sum(1 for c in all_checks if c["status"] == "pass")
    score = max(0, min(100, 100 - crit * 10 - warn * 4))
    if score >= 85:
        grade = "Excellent"
    elif score >= 65:
        grade = "Good, a few gaps"
    elif score >= 45:
        grade = "Needs work"
    else:
        grade = "Critical issues"
    return score, grade, crit, warn, passed


def color_for(status):
    return {"pass": GREEN, "warning": AMBER, "critical": RED}[status]


def print_report(url, onpage, tech, is_shopify):
    score, grade, crit, warn, passed = score_and_grade(onpage, tech)
    print(f"\n{BOLD}SiteScan — SEO Diagnostic{RESET}")
    print(f"{DIM}{url}{RESET}\n")
    score_color = GREEN if score >= 65 else (AMBER if score >= 45 else RED)
    print(f"Score: {score_color}{BOLD}{score}/100{RESET}  ({grade})")
    print(f"{RED}{crit} critical{RESET}   {AMBER}{warn} warnings{RESET}   {GREEN}{passed} passed{RESET}\n")

    for title, checks in [("ON-PAGE SEO", onpage), ("TECHNICAL SEO", tech)]:
        print(f"{BOLD}{BLUE}{title}{RESET}")
        for c in checks:
            c_color = color_for(c["status"])
            print(f"  {c_color}{c['status'].upper():<9}{RESET} {c['label']:<26} {DIM}{c['detail']}{RESET}")
        print()

    mistakes = [c for c in (onpage + tech) if c["status"] != "pass"]
    mistakes.sort(key=lambda c: 0 if c["status"] == "critical" else 1)
    print(f"{BOLD}{BLUE}MISTAKES & FIX GUIDE{RESET}")
    if not mistakes:
        print(f"  {GREEN}No major mistakes found in this scan.{RESET}\n")
    else:
        for c in mistakes:
            c_color = color_for(c["status"])
            print(f"  {c_color}[{c['status'].upper()}]{RESET} {BOLD}{c['label']}{RESET}")
            print(f"    - {c['detail']}")
            if c.get("fix"):
                print(f"    - Fix: {c['fix']}")
            if is_shopify and c["label"] in SHOPIFY_TIPS:
                print(f"    - {DIM}Shopify tip: {SHOPIFY_TIPS[c['label']]}{RESET}")
            print()


def build_html_report(url, onpage, tech, is_shopify):
    score, grade, crit, warn, passed = score_and_grade(onpage, tech)
    color = "#3fbf8f" if score >= 65 else ("#e3a23c" if score >= 45 else "#e15b4f")

    def rows(checks):
        out = []
        for c in checks:
            badge = {"pass": "PASS", "warning": "WARN", "critical": "FAIL"}[c["status"]]
            css = c["status"]
            fix_html = f'<div class="fix">Fix: {c["fix"]}</div>' if c.get("fix") else ""
            out.append(
                f'<div class="row {css}"><span class="tag {css}">{badge}</span>'
                f'<div><div class="lbl">{c["label"]}</div><div class="det">{c["detail"]}</div>{fix_html}</div></div>'
            )
        return "".join(out)

    mistakes = [c for c in (onpage + tech) if c["status"] != "pass"]
    mistakes.sort(key=lambda c: 0 if c["status"] == "critical" else 1)
    mistake_html = ""
    if not mistakes:
        mistake_html = '<p style="color:#9096a3">No major mistakes found in this scan.</p>'
    else:
        for c in mistakes:
            tip = f'<div class="shopify">Shopify tip: {SHOPIFY_TIPS[c["label"]]}</div>' if is_shopify and c["label"] in SHOPIFY_TIPS else ""
            mistake_html += (
                f'<div class="mcard {c["status"]}"><span class="tag {c["status"]}">{c["status"].upper()}</span> '
                f'<b>{c["label"]}</b><ol><li>{c["detail"]}</li><li>{c["fix"]}</li></ol>{tip}</div>'
            )

    html_out = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>SEO Report — {url}</title>
<style>
body{{background:#101218;color:#EDEAE0;font-family:Arial,sans-serif;margin:0;padding:40px;}}
.wrap{{max-width:820px;margin:0 auto;}}
h1{{font-size:22px;}} .dim{{color:#9096a3;font-size:13px;}}
.score{{font-size:34px;font-weight:bold;color:{color};margin:14px 0 4px;}}
.section{{margin-top:30px;border-top:1px solid #2a2f39;padding-top:14px;}}
.row{{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #21252d;font-size:14px;}}
.tag{{font-size:10px;font-weight:bold;padding:2px 6px;border-radius:4px;height:fit-content;}}
.tag.pass{{background:#132622;color:#3fbf8f;}} .tag.warning{{background:#2a2116;color:#e3a23c;}} .tag.critical{{background:#2c1917;color:#e15b4f;}}
.lbl{{font-weight:600;}} .det{{color:#9096a3;font-size:12.5px;margin-top:2px;}}
.fix{{color:#c9d0e0;font-size:12.5px;margin-top:5px;background:#1d2129;padding:6px 9px;border-left:2px solid #5b8cff;}}
.mcard{{border:1px solid #2a2f39;border-radius:8px;padding:12px 16px;margin-bottom:10px;}}
.mcard.critical{{border-left:3px solid #e15b4f;}} .mcard.warning{{border-left:3px solid #e3a23c;}}
ol{{font-size:13px;color:#9096a3;}}
.shopify{{font-size:12px;color:#5b6170;margin-top:6px;}}
</style></head><body><div class="wrap">
<div class="dim">SiteScan report — generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<h1>{url}</h1>
<div class="score">{score}/100</div>
<div class="dim">{grade} — {crit} critical, {warn} warnings, {passed} passed</div>
<div class="section"><h2>On-page SEO</h2>{rows(onpage)}</div>
<div class="section"><h2>Technical SEO</h2>{rows(tech)}</div>
<div class="section"><h2>Mistakes &amp; fix guide</h2>{mistake_html}</div>
</div></body></html>"""
    return html_out


def main():
    parser = argparse.ArgumentParser(description="SiteScan — Automatic SEO Diagnostic")
    parser.add_argument("domain", help="Domain or URL to scan, e.g. drivestylish.com")
    parser.add_argument("--html", action="store_true", help="Also save an HTML report file")
    args = parser.parse_args()

    url = normalize_url(args.domain)
    if not url:
        print("Invalid domain.")
        sys.exit(1)

    print(f"Scanning {url} ...")
    try:
        onpage, tech, is_shopify, final_url = analyze(url)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Could not fetch this page: {e}{RESET}")
        sys.exit(1)

    print_report(final_url, onpage, tech, is_shopify)

    if args.html:
        report_html = build_html_report(final_url, onpage, tech, is_shopify)
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", urlparse(final_url).netloc)
        out_path = f"seo_report_{safe_name}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        print(f"HTML report saved: {out_path}")


if __name__ == "__main__":
    main()
