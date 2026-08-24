# Financial Screening Dashboard

This is the static site bundle for GitHub Pages.

- Entry: index.html
- Default dataset: data/screening/investment_screen_v2_investable_all_summary.csv
- The default dataset is the deterministic v2 rules result; AI evaluation is not enabled.
- This bundle includes only frontend files and public CSV/TXT files required for browsing.
- It does not include API keys, cache files, collection scripts, or console logs.

Local preview:

Do not open index.html directly with file://. Browsers block local CSV fetches in file mode.

`powershell
cd public
python -m http.server 8766
`

Then open http://127.0.0.1:8766/
