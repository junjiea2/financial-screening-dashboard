# 发布为可分享网页

当前项目已经可以构建一个纯静态网页目录：`public/`。

## 本地构建

```powershell
.\scripts\build_public.ps1
```

注意：不要直接双击打开 `public/index.html`。浏览器在 `file://` 模式下会阻止网页读取本地 CSV，页面会显示 `Failed to fetch`。

本地预览需要启动静态服务：

```powershell
cd public
python -m http.server 8766
```

打开：

```text
http://127.0.0.1:8766/
```

## 发布到 GitHub Pages

1. 在 GitHub 新建一个仓库。
2. 把本项目推送到仓库的 `main` 分支。
3. 进入仓库的 `Settings -> Pages`。
4. `Source` 选择 `GitHub Actions`。
5. 推送后 `.github/workflows/pages.yml` 会自动发布 `public/`。

发布后，别人可以通过 GitHub Pages 链接直接打开网页。

## 公开内容说明

`public/` 只包含：

- 前端页面：`index.html`、`app.js`、`styles.css`
- 浏览所需筛选结果 CSV
- 浏览所需报告 TXT

不会包含：

- DeepSeek API key
- Python 采集脚本
- raw/normalized 全量中间数据
- cache
- 控制台日志
