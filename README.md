# 台股情緒儀表板

收集台股客觀指標，以歷史百分位合成 0-100 情緒總分：**≥80 過熱提醒減碼、≤20 過冷提醒加碼**（Telegram 推播），並提供走勢儀表板網頁。

## 指標（8 項，等權）

| 面向 | 指標 | 方向 | 來源 |
|---|---|---|---|
| 估值 | 上市個股本益比中位數 | 越高越樂觀 | TWSE `BWIBBU_d` |
| 估值 | 上市個股殖利率中位數 | 越高越悲觀 | TWSE `BWIBBU_d` |
| 籌碼 | 融資餘額 20 日增減 | 越高越樂觀 | TWSE `MI_MARGN` |
| 籌碼 | 外資台指期未平倉淨部位 | 越高越樂觀 | TAIFEX OpenAPI |
| 情緒 | 台指選擇權 Put/Call 未平倉比 | 越高越悲觀 | TAIFEX OpenAPI |
| 情緒 | 大盤 20 日歷史波動率 | 越高越悲觀 | 由指數計算 |
| 技術 | 大盤收盤 vs 240 日均線乖離率 | 越高越樂觀 | TWSE `FMTQIK` |
| 技術 | 漲跌家數比 20 日平均 | 越高越樂觀 | TWSE `MI_INDEX` |

每項指標取近三年歷史算當日值的百分位（0-100，方向統一為越高越樂觀），等權平均成總分。

## 運作方式

- **GitHub Actions**（`.github/workflows/daily.yml`）：週一至五台北 22:30 自動執行 `collector/collect_daily.py`，抓當日資料、更新 `data/history.csv` 與 `docs/data/*.json` 後 commit。
- **GitHub Pages**：儀表板網頁在 `docs/`，Pages 指向 main branch `/docs` 目錄。
- **Telegram 通知**：總分跨入/離開過熱・過冷區間時推播；資料連續 2 天抓取失敗也會警示。

## 初次設定

1. **建 Telegram Bot**：跟 [@BotFather](https://t.me/BotFather) 說 `/newbot` 拿到 token；跟你的 bot 說一句話後，開 `https://api.telegram.org/bot<TOKEN>/getUpdates` 找 `chat.id`。
2. **Repo secrets**：Settings → Secrets and variables → Actions，新增 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
3. **啟用 Pages**：Settings → Pages → Source 選 `main` branch 的 `/docs` 目錄。
4. **回補歷史**（本機一次性，約 1 小時）：
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m collector.bootstrap
   git add data docs/data && git commit -m "bootstrap history" && git push
   ```

## 開發

```bash
.venv/bin/python -m pytest tests/           # 測試
.venv/bin/python -m collector.collect_daily # 手動收集一次
python3 -m http.server -d docs 8791         # 本機看儀表板
```

僅供參考，非投資建議。
