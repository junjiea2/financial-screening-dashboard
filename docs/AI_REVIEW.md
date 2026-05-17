# AI 二次复核层

`ai_review_results.py` 用来在规则筛选之后，对指定结果集追加 AI 复核列。

它不会替代原来的四步排雷规则，只做解释和二次检查：

- `AI判断`
- `AI置信度`
- `AI原因`
- `AI风险点`
- `AI复核模型`

## 准备 API Key

第一版默认使用 DeepSeek。不要把 API Key 写进代码或 CSV，建议只放在当前 PowerShell 环境变量里：

```powershell
$env:DEEPSEEK_API_KEY="sk-..."
```

可选指定模型：

```powershell
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
```

如果 `deepseek-v4-flash` 报模型不存在，使用兼容性更好的默认模型 `deepseek-chat`：

```powershell
$env:DEEPSEEK_MODEL="deepseek-chat"
```

## 建议先小批量测试

只复核前 20 只规则结果为“通过”的股票：

```powershell
python ai_review_results.py `
  --input screening_result_investable_2000.csv `
  --output screening_result_investable_2000_ai.csv `
  --only 通过 `
  --limit 20 `
  --provider deepseek `
  --resume
```

稳定后再放大到 100 或更多：

```powershell
python ai_review_results.py `
  --input screening_result_investable_2000.csv `
  --output screening_result_investable_2000_ai.csv `
  --only 通过 `
  --limit 100 `
  --provider deepseek `
  --resume
```

`--resume` 会复用已有输出中的 AI 列，`cache/ai_reviews/` 也会缓存每只股票的复核结果，避免重复请求。

## 设计原则

规则引擎负责硬筛选，AI 负责把“为什么通过/为什么仍需谨慎”写清楚。AI 输出不应该直接作为买卖建议，只作为人工进一步研究的解释层。

也可以切回 OpenAI：

```powershell
$env:OPENAI_API_KEY="sk-..."
python ai_review_results.py `
  --input screening_result_investable_2000.csv `
  --output screening_result_investable_2000_ai.csv `
  --only 通过 `
  --limit 20 `
  --provider openai `
  --resume
```
