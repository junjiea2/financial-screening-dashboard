$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$public = Join-Path $root "public"

if (Test-Path -LiteralPath $public) {
    Remove-Item -LiteralPath $public -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $public | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $public "data\screening") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $public "data\reports") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "dashboard\index.html") -Destination (Join-Path $public "index.html")
Copy-Item -LiteralPath (Join-Path $root "dashboard\app.js") -Destination (Join-Path $public "app.js")
Copy-Item -LiteralPath (Join-Path $root "dashboard\styles.css") -Destination (Join-Path $public "styles.css")

$screeningFiles = @(
    "dual_track_investable_all_ai_quality_all.csv",
    "dual_track_investable_all_ai1700.csv",
    "dual_track_investable_all_ai1000.csv",
    "dual_track_investable_all_ai500.csv",
    "dual_track_investable_all_ai200.csv",
    "screening_result_investable_all_rules.csv",
    "dual_track_investable_2000_ai200.csv",
    "dual_track_investable_2000_ai100.csv",
    "dual_track_cn_100.csv",
    "screening_result_investable_2000_dual_rules.csv",
    "screening_result_investable_2000.csv",
    "screening_result_investable_500.csv"
)

foreach ($file in $screeningFiles) {
    Copy-Item -LiteralPath (Join-Path $root "data\screening\$file") -Destination (Join-Path $public "data\screening\$file")
}

$reportFiles = @(
    "stability_report_investable_all.txt",
    "stability_report_investable_2000.txt",
    "stability_report_investable_500.txt"
)

foreach ($file in $reportFiles) {
    Copy-Item -LiteralPath (Join-Path $root "data\reports\$file") -Destination (Join-Path $public "data\reports\$file")
}

$appPath = Join-Path $public "app.js"
(Get-Content -LiteralPath $appPath -Raw -Encoding UTF8).Replace("../data/", "./data/") |
    Set-Content -LiteralPath $appPath -Encoding UTF8

$indexPath = Join-Path $public "index.html"
$index = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
$index = $index.Replace("./styles.css", "./styles.css")
$index = $index.Replace("./app.js", "./app.js")
$index = $index.Replace("../data/", "./data/")
$index = $index.Replace("优先读取 data/screening/dual_track_investable_all_ai_quality_all.csv；找不到时回退到小样本结果", "Public dashboard: rule screening plus AI quality review")
$index | Set-Content -LiteralPath $indexPath -Encoding UTF8

New-Item -ItemType File -Force -Path (Join-Path $public ".nojekyll") | Out-Null

@"
# Financial Screening Dashboard

This is the static site bundle for GitHub Pages.

- Entry: index.html
- Default dataset: data/screening/dual_track_investable_all_ai_quality_all.csv
- This bundle includes only frontend files and public CSV/TXT files required for browsing.
- It does not include API keys, cache files, collection scripts, or console logs.

Local preview:

Do not open index.html directly with file://. Browsers block local CSV fetches in file mode.

```powershell
cd public
python -m http.server 8766
```

Then open http://127.0.0.1:8766/
"@ | Set-Content -LiteralPath (Join-Path $public "README.md") -Encoding UTF8

Write-Output "Built public site at $public"
