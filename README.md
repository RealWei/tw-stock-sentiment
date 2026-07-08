# 台股情緒儀表板

收集台股客觀指標，以歷史百分位合成 0-100 情緒總分：**≥80 過熱提醒減碼、≤20 過冷提醒加碼**（Telegram 推播），並提供走勢儀表板網頁。

## 指標（6 項，等權）

| 面向 | 指標 | 方向 | 來源 |
|---|---|---|---|
| 估值 | 上市個股本益比中位數 | 越高越樂觀 | TWSE `BWIBBU_d` |
| 籌碼 | 融資餘額 20 日增減 | 越高越樂觀 | TWSE `MI_MARGN` |
| 籌碼 | 外資台指期未平倉淨部位 | 越高越樂觀 | TAIFEX OpenAPI |
| 情緒 | 台指選擇權 Put/Call 未平倉比 | 越高越悲觀 | TAIFEX OpenAPI |
| 情緒 | 大盤 20 日歷史波動率 | 越高越悲觀 | 由指數計算 |
| 技術 | 漲跌家數比 20 日平均 | 越高越樂觀 | TWSE `MI_INDEX` |

每項指標取近三年歷史算當日值的百分位（0-100，方向統一為越高越樂觀），等權平均成總分（儀表顯示用）。

**燈號與通知由雙計決定**（2024-08~2026-07 波段回測結論：8 指標在轉折點的極端值不同步，平均會互相抵消，總分到不了極端區）：

- **過熱計** = 外資期貨、融資增速、P/C 比三項各取「近 5 日最高分」的平均，**≥80** 提醒減碼
- **恐慌計** = 波動率、本益比、融資增速、漲跌家數、P/C 比五項各取「近 5 日最低分」的平均，**≤15** 提醒加碼

回測中恐慌計精準抓到 2024-08-05 與 2025-04-09 兩次崩盤底（讀數 13、10），過熱計抓到 2025-11 頂，平時觸發率各約 4%。動能型頭部（無全面亢奮者）先天難偵測，屬已知限制。

## 技術訊號（獨立於總分）

加權指數與櫃買指數各自偵測，近 30 個交易日的訊號顯示於儀表板，新訊號觸發時 Telegram 推播：

| 訊號 | 定義 |
|---|---|
| 價量背離 | 收盤創 20 日新高但量低於 20 日均量（偏空）／創新低量縮（偏多） |
| RSI 背離 | 收盤創 60 日新高但 14 日 RSI 低於前波峰（偏空）；創低反之（偏多） |
| 創高留上影線 | 盤中創 60 日新高、上影線 ≥2 倍實體且 ≥40% 振幅（偏空） |
| 吞噬形態 | 60 日高檔的看空吞噬／低檔的看多吞噬 |
| 高檔十字星 | 60 日高檔出現實體 ≤10% 振幅的十字星（偏空警訊） |

另提供撐壓位階：收盤距月線/季線/年線 %、近 60/240 日高低點。
櫃買歷史 OHLC 官方需付費，故 K 棒類訊號自建置日起累積（收盤/成交值有完整歷史）。

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
