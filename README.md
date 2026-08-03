# Glassdoor Analysis

依照 [spec.v1.md](./spec.v1.md) 建立的 Python CLI，負責抓取 Glassdoor review 頁面的聚合評分資料，並輸出成功資料、attempt log 與 run summary。

## Environment

本專案使用專案根目錄下的 `.venv` 虛擬環境。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## 前置條件

### 基本環境

- Windows PowerShell
- Python 3.11 或以上
- Google Chrome（只有使用 Chrome CDP 抓取模式時需要）
- Git（若要從 repository 取得程式碼）

建立虛擬環境並安裝專案：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### Chrome remote debugging（使用 CDP 模式時）

專案不會自動啟動 Chrome；它會連線到已經開啟的 Chrome remote debugging session。可以使用專案內的 PowerShell script 啟動獨立的 Chrome profile：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_chrome_cdp.ps1
```

預設會在 `http://127.0.0.1:9223` 開啟 CDP。請在新開的 Chrome 視窗登入 Glassdoor，並用以下指令確認 Debug Port 已啟動：

```powershell
Invoke-WebRequest http://127.0.0.1:9223/json/version
```

如果要使用其他 port 或 Chrome 路徑：

```powershell
.\scripts\start_chrome_cdp.ps1 -Port 9224
.\scripts\start_chrome_cdp.ps1 -ChromePath "C:\\Path\\to\\chrome.exe"
```

此 script 使用獨立的 Chrome profile，避免干擾平常使用的 Chrome profile。不要把該 profile、cookies 或登入資料提交到 Git。

若不使用 Chrome CDP，也可以透過 `--session-source` 提供 session JSON 或 cookie header；但 Glassdoor 仍可能要求登入、CAPTCHA 或其他存取驗證。

## CLI

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --output-dir .\artifacts --dry-validate
```

正式流程由五個可續跑階段組成：

1. `discover-locations`：抓取每家公司的 Office Locations，輸出 `office_locations.json/csv` 與聯集後的 `region_pool.json`。
2. `resolve-review-urls`：依照各公司 Office Locations 頁面中的辦公室連結與 `N reviews in <city>` 連結建立基礎 manifest。
3. `probe-review-url-gaps`：對尚未解析的組合，重用 region pool 中的 Glassdoor location ID 建立候選 URL，驗證 header 與聚合欄位後更新 manifest。
4. `extract-metrics`：只讀取狀態為 `resolved` 的 review URL，驗證頁面後輸出含 `country` 的 `reviews_aggregate.json/csv`。
5. `backfill-countries`：不發出網路請求，依 `region_country_map` 回填既有 aggregate 的 `country` 欄位。

`probe-review-url-gaps` 可能包含大量組合，因此需獨立執行；`--stage all` 不會自動啟動 gap probes。

可以分段執行：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --stage discover-locations --rebuild-region-pool --browser-cdp-url http://127.0.0.1:9223 --output-dir .\artifacts
.venv\Scripts\python.exe -m glassdoor_analysis --stage resolve-review-urls --rebuild-review-urls --browser-cdp-url http://127.0.0.1:9223 --output-dir .\artifacts
.venv\Scripts\python.exe -m glassdoor_analysis --stage probe-review-url-gaps --max-gap-probes 100 --browser-cdp-url http://127.0.0.1:9223 --output-dir .\artifacts
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage extract-metrics `
  --request-delay-seconds 8 `
  --request-jitter-seconds 4 `
  --cooldown-every 25 `
  --cooldown-seconds 120 `
  --progress-every 10 `
  --browser-cdp-url http://127.0.0.1:9223 `
  --output-dir .\artifacts
.venv\Scripts\python.exe -m glassdoor_analysis --stage backfill-countries --output-dir .\artifacts
```

前兩個階段會增量保存結果；中斷後不加 `--rebuild-region-pool` 或 `--rebuild-review-urls` 重新執行，即可沿用已完成項目。

可選參數：

- `--companies ASUS NVIDIA`
- `--regions Taipei Austin`
- `--output-dir .\artifacts`
- `--session-source .\session.json`
- `--browser-cdp-url http://127.0.0.1:9223`
- `--rebuild-region-pool`
- `--rebuild-review-urls`
- `--stage all|discover-locations|resolve-review-urls|probe-review-url-gaps|extract-metrics|backfill-countries`
- `--max-gap-probes 100`
- `--retry-gap-failures`
- `--max-extractions 100`
- `--retry-extraction-failures`
- `--refresh-existing-metrics`
- `--request-delay-seconds 8`
- `--request-jitter-seconds 4`
- `--cooldown-every 25`
- `--cooldown-seconds 120`
- `--progress-every 10`
- `--office-locations-cache .\artifacts\office_locations.json`
- `--review-urls-cache .\artifacts\company_region_review_urls.json`
- `--region-pool-cache .\artifacts\region_pool.json`
- `--dry-validate`

`--rebuild-region-pool` 會重新抓公司 office locations 並把合併後的 pool 落到 `region_pool.json`；未指定時若 cache 存在，會優先重用 cache。

`--dry-validate` 只驗證頁面與產出 `attempt_log.*` / `run_summary.json`，不會生成 `reviews_aggregate.csv` 或 `reviews_aggregate.json`；summary 中的 `success_count` 仍代表驗證成功數。

每次執行都會把實際使用的 region pool 輸出到 `output_dir/region_pool.json`，方便後續分析與稽核。

Country mapping 以 normalized region 為 key，由程式內的明確對應表管理。`backfill-countries` 會更新既有 `reviews_aggregate.json/csv`，並輸出 `region_country_map.json/csv` 供稽核；不需要重抓 review 頁面或開啟 Chrome 9223。

地區 review URL 優先透過 Office Locations 的頁面連結解析。Gap probe 只重用已驗證 office URL 中的 Glassdoor location ID 來建立候選，不使用 Glassdoor keyword search 或搜尋 fallback；候選頁仍必須通過公司、地區與聚合欄位驗證。

Gap probe 與 metrics extraction 預設都會在每次網路請求間等待 8–12 秒，並在每 25 個網路請求後冷卻 120 秒。若偵測到 Glassdoor rate limit、CAPTCHA 或登入限制，該批次會立即停止，當前紀錄仍保留為可重試狀態。不要以 `0` 關閉延遲後執行大型批次。

`extract-metrics` 每完成一筆便增量更新 `reviews_aggregate.json/csv` 與 `metrics_attempt_log.json/csv`，預設每 10 筆印出一次進度。中斷後重跑相同指令會跳過已成功資料；如要重試先前的頁面驗證失敗，可加上 `--retry-extraction-failures`。

若 parser 更新後需要重抓既有成功資料，可加上 `--refresh-existing-metrics`。此模式只處理已存在於 `reviews_aggregate.json` 的 company-region，並以新結果覆蓋同一筆資料，不會建立重複紀錄。

Glassdoor 的 category metrics 目前有兩種呈現：review 較多的頁面使用 `Company ratings over time` 圖表，review 較少的頁面直接顯示 `Ratings by category`。Parser 會優先讀取頁面內 location-level ratings payload，並以 category DOM 作備援，避免誤用 individual review、demographic 或 company-wide 評分。

同一台電腦開啟 9223、9224、9225 三個 Chrome debug port 並不會改變 public IP。Glassdoor 的限制可能以來源 IP 的總請求量計算，因此不建議在同一 IP 上平行 extraction；這通常只會把三倍流量送到同一限制器。若未來採用多 worker，仍應共享單一全域節流器，不能讓每個 port 各自用完整速率。

如果一般 HTTP 請求會被 Glassdoor captcha 擋住，可以改用 `--browser-cdp-url` 直接透過已登入的 Chrome remote debugging session 抓頁面。

`session.json` 支援以下格式：

```json
{
  "cookies": {
    "cookie_name": "cookie_value"
  },
  "headers": {
    "User-Agent": "..."
  }
}
```

也支援瀏覽器匯出的 cookies array，例如：

```json
[
  { "name": "tldp", "value": "..." },
  { "name": "sess", "value": "..." }
]
```

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
