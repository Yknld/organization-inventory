"""Refresh user-reviewed CRA links and join the original inventory.
Run: python3 refresh_reviewed_cra.py
"""
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
API = "https://apps.cra-arc.gc.ca/ebci/hacc/ngcids/rest/api/cidsRequest/retrieveReportingPeriod/"


def read_csv(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def date(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat() if value else ""


def amount(value):
    return format(value, ",") if isinstance(value, (int, float)) else ""


def main():
    fields, reviewed = read_csv("reviewed-cra-links.csv")
    inventory_fields, inventory = read_csv("inventory - Sheet1.csv")
    by_name = {}
    for row in inventory:
        by_name.setdefault(row["Organization name"], []).append(row)
    extra_fields = ["CRA designation", "CRA website", "CRA ongoing programs",
                    "CRA new programs", "CRA compensation CAD", "CRA full-time employees",
                    "CRA part-time employees", "CRA retrieved UTC"]
    output_fields = fields + [f for f in inventory_fields if f not in fields] + extra_fields
    results = []
    for selected in reviewed:
        name = selected["Organization name"]
        matches = by_name.get(name, [])
        if len(matches) > 1:
            matches = [r for r in matches if "national" in r["Service scope (approx.)"].casefold()]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one original inventory match for {name}: {len(matches)}")
        row = {**matches[0], **selected}
        url = selected["profile URL"]
        if url.strip().upper() == "NR":
            row["lookup"] = "NR in user review; no CRA profile supplied"
            results.append(row)
            continue
        match = re.fullmatch(r"https://apps\.cra-arc\.gc\.ca/ebci/hacc/srch/pub/dsplyRprtngPrd/(\d{9}RR\d{4})", url)
        if not match:
            raise ValueError(f"Unrecognized reviewed CRA URL: {url}")
        registration = match[1]
        with urlopen(API + registration, timeout=45) as response:
            data = json.load(response)
        account = data["charityAccountDetails"]
        identity = account["bnView"]
        if identity["businessNumberModel"]["businessNumberString"] != registration:
            raise ValueError(f"CRA registration mismatch for {name}")
        details = data.get("quickViewDetails") or {}
        period = (data.get("selectedFP") or {}).get("endDate")
        row.update({
            "CRA name": identity["organizationName"],
            "status": account["state"]["englishText"],
            "status effective": date(account.get("stateEffectiveDate")),
            "registration": registration,
            "period ending": date(period),
            "revenue CAD": amount((details.get("revenueChart") or {}).get("total")) if period else "",
            "expenses CAD": amount((details.get("expenseChart") or {}).get("total")) if period else "",
            "CRA designation": ((account.get("organizationByDesignation") or {}).get("designationType") or {}).get("englishText", ""),
            "CRA website": "; ".join(account.get("charityWebsiteAddresses") or []),
            "CRA ongoing programs": details.get("ongoingCharitableProgram") or "",
            "CRA new programs": details.get("newCharitableProgram") or "",
            "CRA compensation CAD": amount(details.get("compensationExpenditureTotalAmount")) if period else "",
            "CRA full-time employees": details.get("numberOfFullTimeEmployees", "") if period else "",
            "CRA part-time employees": details.get("numberOfPartTimeEmployees", "") if period else "",
            "CRA retrieved UTC": datetime.now(timezone.utc).isoformat(),
            "lookup": "retrieved from user-reviewed CRA link",
        })
        client_type = identity.get("clientType") or {}
        row["type"] = client_type.get("englishText") or client_type.get("propertyKey", "").rsplit(".", 1)[-1].capitalize()
        if not period:
            row["lookup"] += "; financials unavailable"
        # User review resolves earlier name-search candidates and source-ID conflicts.
        row["notes"] = "Profile selected by user review."
        if "revoked" not in row["status"].casefold():
            results.append(row)
        print(name, row["status"], row["period ending"], row["revenue CAD"], row["expenses CAD"], flush=True)
        time.sleep(0.5)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", dir=ROOT, delete=False) as output:
        temporary = Path(output.name)
        try:
            writer = csv.DictWriter(output, output_fields)
            writer.writeheader()
            writer.writerows(results)
            output.close()
            temporary.replace(ROOT / "cra-results.csv")
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Saved {len(results)} reviewed entries.")


if __name__ == "__main__":
    main()
