"""Search CRA by name. Install: pip install playwright && playwright install chromium
Run: python cra_lookup.py [--input national-scope.csv] [--output cra-name-search-results.csv]
Single lookup: python cra_lookup.py --name "Federation of Black Canadians"
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode

from playwright.sync_api import Error, sync_playwright

BASE = "https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/bscSrch?"
FIELDS = ["Organization name", "lookup", "CRA name", "status", "type", "province",
          "city", "status effective", "registration", "period ending", "revenue CAD",
          "expenses CAD", "profile URL", "search URL", "notes"]


def key(name):
    plain = unicodedata.normalize("NFKD", name.casefold().replace("&", " and "))
    words = re.findall(r"[a-z0-9]+", "".join(c for c in plain if not unicodedata.combining(c)))
    return " ".join(words).removeprefix("the ")


def lookup(page, name):
    query = BASE + urlencode({"q.srchNmFltr": name, "request_locale": "en"})
    result = {"Organization name": name, "search URL": query}
    try:
        page.goto(query, wait_until="domcontentloaded")
        marker = page.get_by_text(re.compile(r"Search results:.*matches? found|no (?:matches|results|organizations).*found|^no results$|no records found", re.I)).first
        marker.wait_for()
        if re.search(r"\b(?:0|no)\b", marker.inner_text(), re.I):
            return dict(result, lookup="no search results")
        links = page.locator("table tr td:first-child a")
        links.first.wait_for()
        names = links.all_inner_texts()
        matches = [i for i, value in enumerate(names) if key(value) == key(name)]
        more = page.get_by_role("button", name="Next page").first
        if len(matches) != 1 or (more.count() and more.is_enabled()):
            return dict(result, lookup="review candidates", notes=" | ".join(names))
        link = links.nth(matches[0])
        cells = link.locator("xpath=ancestor::tr").locator("td").all_inner_texts()
        result.update(zip(["CRA name", "status", "type", "province", "city", "status effective"], cells))
        # Read the reporting data CRA sends when the search result is opened.
        with page.expect_response(lambda response: "/retrieveReportingPeriod/" in response.url) as pending:
            link.click()
        response = pending.value
        if not response.ok:
            raise ValueError(f"CRA reporting request returned HTTP {response.status}")
        data = response.json()
        registration = data["charityAccountDetails"]["bnView"]["businessNumberModel"]["businessNumberString"]
        if not registration or registration != response.url.rsplit("/", 1)[-1]:
            raise ValueError("CRA profile identifier mismatch")
        result["registration"] = registration
        result["profile URL"] = BASE.rsplit("/", 1)[0] + "/" + "dsplyRprtngPrd/" + registration
        period = (data.get("selectedFP") or {}).get("endDate")
        details = data.get("quickViewDetails") or {}
        if period:
            result["period ending"] = datetime.fromtimestamp(period / 1000, timezone.utc).date().isoformat()
            for chart, field in [("revenueChart", "revenue CAD"), ("expenseChart", "expenses CAD")]:
                total = (details.get(chart) or {}).get("total")
                if isinstance(total, (int, float)):
                    result[field] = format(total, ",")
        result["lookup"] = ("matched" if "expenses CAD" in result and "revenue CAD" in result
                            else "matched; financials unavailable")
    except (Error, KeyError, TypeError, ValueError) as exc:
        result.update(lookup="lookup error", notes=str(exc).splitlines()[0])
    return result


def flag_registration_conflict(row, urls):
    references = set(re.findall(r"\d{9}RR\d{4}", urls.upper()))
    if row.get("registration") and references and references != {row["registration"]}:
        row["notes"] = "Inventory source URL references a different registration: " + ", ".join(sorted(references))
        row["lookup"] = "review registration conflict"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("national-scope.csv"))
    parser.add_argument("--output", type=Path, default=Path("cra-name-search-results.csv"))
    parser.add_argument("--name")
    parser.add_argument("--chrome", action="store_true", help="Use installed Google Chrome")
    parser.add_argument("--headed", action="store_true", help="Show the browser and allow time for manual site verification")
    args = parser.parse_args()
    if not args.name:
        if args.input.resolve() == args.output.resolve():
            parser.error("Choose an output different from the inventory")
        with args.input.open(encoding="utf-8-sig", newline="") as src:
            inventory = list(csv.DictReader(src))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, channel="chrome" if args.chrome else None)
        page = browser.new_page(locale="en-CA")
        page.set_default_timeout(90000 if args.headed else 15000)
        if args.name:
            print(json.dumps(lookup(page, args.name), indent=2, ensure_ascii=False))
            return
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                dir=args.output.parent, delete=False) as out:
            partial = Path(out.name)
            try:
                writer = csv.DictWriter(out, FIELDS)
                writer.writeheader()
                for record in inventory:
                    name = record["Organization name"].strip()
                    row = flag_registration_conflict(lookup(page, name), record.get("Source URL(s)") or "")
                    if "revoked" not in row.get("status", "").casefold():
                        writer.writerow(row)
                    print(name, row["lookup"], file=sys.stderr, flush=True)
                    time.sleep(0.5)
                out.close()
                partial.replace(args.output)
            finally:
                partial.unlink(missing_ok=True)



if __name__ == "__main__":
    main()
