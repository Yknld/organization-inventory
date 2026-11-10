# Organization inventory

The full inventory is in `inventory - Sheet1.csv`. The `national-scope.csv` subset includes entries whose service scope mentions national reach.

## Refresh the reviewed results

Run `python3 refresh_reviewed_cra.py` to retrieve CRA status, reporting period, revenue, expenses, programs, compensation and employee counts using the exact links in `reviewed-cra-links.csv`. It joins each reviewed organization to `inventory - Sheet1.csv`, including the original evidence summaries, communities, service scope and source links.

The results preserve the reviewed selection and profile URLs. Entries marked `NR` retain that review marker and their original inventory information. No CRA registration conclusion is inferred from that marker. Revoked profiles are excluded. The output is replaced only after every supplied CRA link has been retrieved successfully.

## CRA name search

`cra_lookup.py` opens the CRA charity search for each organization name and reads the public reporting-period data returned when it opens a matching profile. Name searches write to `cra-name-search-results.csv`. The combined reviewed results are in `cra-results.csv`. Revenue and expenses use thousands separators.

With Python 3.9+ and Google Chrome installed, run:

```sh
python3 -m venv .venv
.venv/bin/pip install playwright
.venv/bin/python cra_lookup.py --chrome --name "Federation of Black Canadians"
.venv/bin/python cra_lookup.py --chrome
```

Use `--input "inventory - Sheet1.csv" --output full-cra-results.csv` to search the full inventory. To use Playwright's Chromium instead, run `.venv/bin/playwright install chromium` and omit `--chrome`.

Revenue and expenses are historical amounts in Canadian dollars for the period shown. Blank amounts indicate unavailable or unresolved figures. A zero means CRA returned zero.

The lookup accepts a unique matching name after normalizing case, accents, punctuation, “&” and a leading “The”. Other candidates are listed for review. A search with no results can mean the organization uses another legal name. When an inventory source URL contains a different registration number, the row is flagged for review. Use the search and profile links to resolve those cases before relying on the figures.
