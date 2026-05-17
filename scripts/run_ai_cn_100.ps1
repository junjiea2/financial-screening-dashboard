if (-not $env:DEEPSEEK_API_KEY) {
  Write-Error "DEEPSEEK_API_KEY is not set. Run: `$env:DEEPSEEK_API_KEY='sk-...'"
  exit 1
}

python ai_independent_evaluate.py `
  --input data\samples\full_financials_cn_100.csv `
  --output data\ai\ai_independent_cn_100.csv `
  --market CN `
  --limit 100 `
  --model deepseek-chat `
  --resume
