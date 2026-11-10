# Organization inventory

The full inventory is in `inventory - Sheet1.csv`. The `national-scope.csv` subset includes entries whose service scope mentions national reach.

## CRA charity lookup

`cra_lookup.py` opens the CRA charity search for each organization name and reads the public reporting-period data returned when it opens a matching profile. `cra-results.csv` contains the 28 entries in the user-reviewed CSV, with the supplied profile links and column order preserved. Revenue and expenses use thousands separators.

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
