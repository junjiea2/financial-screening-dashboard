if (-not $env:DEEPSEEK_API_KEY) {
    Write-Error "DEEPSEEK_API_KEY is not set in this PowerShell session."
    exit 1
}

python ai_independent_evaluate.py `
    --input data\ai\ai_independent_candidates_next300_financials.csv `
    --output data\ai\ai_independent_candidates_next300.csv `
    --model deepseek-chat `
    --sleep 0.2 `
    --resume

python merge_dual_track.py `
    --rules data\screening\screening_result_investable_all_rules.csv `
    --ai data\ai\ai_independent_candidates_next300.csv `
    --output data\screening\dual_track_investable_all_ai_next300.csv
