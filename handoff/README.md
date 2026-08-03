# Glassdoor Aggregate Metrics 交接包

如果你不熟悉程式，請先閱讀同一個資料夾裡的 **`QUICK_START.md`**；它只保留環境設定與更新資料所需的最少步驟。本文件提供較完整的技術與排錯說明。

## 先說明：工作目錄

**所有命令都要從本 `handoff` 資料夾根目錄執行。** 請先在檔案總管開啟 `handoff`，在該資料夾按右鍵選擇「在終端機中開啟」，或在 PowerShell 執行 `cd` 進入這個資料夾。

這是一份可獨立更新資料的工作副本，原始專案不需要放在同一個位置。交接時的 `artifacts` 是目前資料基準；之後應以它為基礎，定期抓取新資料並更新分析。

## 這個工具做什麼？

這個工具會從 Glassdoor 抓取**公司／地區層級的 aggregate review metrics（彙總評論指標）**，例如整體評分、各項評分與評論數等。它不是下載每一則評論，而是整理公司在指定地區的彙總資料。

交接包內已經帶有目前的 `artifacts` 資料（包括地區池、URL 清單、成功結果、嘗試紀錄與執行摘要）。這些檔案是後續更新資料的基準，請在更新前先備份，並且**不要刪除 `artifacts` 資料夾或其中的檔案**。

## Windows 初次設定

1. 安裝下列軟體：
   - [Python 3.11 或更新版本](https://www.python.org/downloads/)
   - [Google Chrome](https://www.google.com/chrome/)
   - [Git](https://git-scm.com/download/win)
2. 從 `handoff` 根目錄開啟 PowerShell。
3. 建立虛擬環境：

   ```powershell
   python -m venv .venv
   ```

4. 安裝本工具：

   ```powershell
   .venv\Scripts\python.exe -m pip install -e .
   ```

之後建議都使用 `.venv\Scripts\python.exe` 執行 Python，避免用到電腦上其他 Python 版本。

## （建議）先跑測試

在 `handoff` 根目錄執行：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

正常情況預期看到 **78 tests OK**（也可能因 Python 或環境訊息而有少量額外輸出，但測試應全部通過）。

## 使用 Chrome CDP 登入 Glassdoor

若使用 CDP（推薦給需要登入狀態的抓取）：

1. 在 PowerShell 執行：

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\scripts\start_chrome_cdp.ps1
   ```

2. 腳本會開啟一個新的 Chrome。請在**新開的 Chrome** 登入 Glassdoor；不要把自己的日常 Chrome 工作階段拿來共用。
3. 驗證 CDP 是否已啟動：

   ```powershell
   Invoke-WebRequest http://127.0.0.1:9223/json/version
   ```

   如果成功，回應中會看到 Chrome 版本及 `webSocketDebuggerUrl` 等資訊。

## 第一次使用：小批量測試

第一次交接或換電腦時，請先只跑單一公司／地區，確認環境正常。以下指令都從 `handoff` 根目錄執行，使用 ASUS、Taipei、CDP port 9223：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage discover-locations
```

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage resolve-review-urls
```

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage extract-metrics --max-extractions 1
```

工具會使用 `artifacts` 裡的快取。第一次小批量測試時，**快取已存在時不要加入 `--rebuild-region-pool` 或 `--rebuild-review-urls`**，避免測試意外改變目前資料基準。

## 日常更新新資料

交接後的主要工作是更新新資料，不是每次都從頭建立專案。建議流程如下：

### 1. 備份目前資料

在 `handoff` 根目錄執行，將日期換成實際更新日期：

```powershell
Copy-Item artifacts artifacts_backup_2026-08-03 -Recurse
```

### 2. 更新 Office Locations 與 region pool

如果要找出公司新增或變更的辦公室地點，執行：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage discover-locations `
  --rebuild-region-pool `
  --browser-cdp-url http://127.0.0.1:9223
```

`--rebuild-region-pool` 會重新抓取 Office Locations 並更新 `artifacts\region_pool.json`。這是刻意更新資料池的操作，執行前務必先備份 `artifacts`。

### 3. 為新地區建立 review URL

保留既有 manifest，並只補上目前 pool 中尚未存在的公司／地區組合：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage resolve-review-urls `
  --browser-cdp-url http://127.0.0.1:9223
```

日常新增資料時不要加 `--rebuild-review-urls`；只有在確定要捨棄並重建整份 URL manifest 時才使用它。

### 4. 抓取新地區的 aggregate metrics

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage extract-metrics `
  --browser-cdp-url http://127.0.0.1:9223
```

一般執行會保留已經成功的資料，只處理尚未成功的新 resolved URL。完成後檢查 `artifacts\reviews_aggregate.json/csv` 與 `run_summary.json`。

### 5. 更新既有公司／地區的最新評分

如果目的不是新增地區，而是要把既有公司／地區頁面上的最新評分、推薦率或評論數重新抓一次，請使用：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage extract-metrics `
  --refresh-existing-metrics `
  --max-extractions 10 `
  --browser-cdp-url http://127.0.0.1:9223
```

先用 `--max-extractions 10` 小批量確認結果，再移除這個限制執行完整更新。這個模式會以新結果替換相同 company／region 的舊資料，因此執行前務必備份 `artifacts`。

不熟悉命令列時，也可以直接執行：

```powershell
.\scripts\refresh_existing_metrics.ps1 -MaxExtractions 10
```

確認小批量結果正常後，再執行不帶 `-MaxExtractions` 的完整更新。

### 6. 若要重試失敗項目

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis `
  --stage extract-metrics `
  --retry-extraction-failures `
  --browser-cdp-url http://127.0.0.1:9223
```

## 重跑與重試規則

- 平常重跑 `extract-metrics` 時，不會重新抓取已經成功寫入的資料。
- 若確實要重新抓取已存在的資料，才加上：

  ```powershell
  --refresh-existing-metrics
  ```

- 若要重試先前失敗的 extraction，才加上：

  ```powershell
  --retry-extraction-failures
  ```

這兩個選項的用途不同，請不要為了「保險」而每次都加上。

## 參數與安全預設值

一般使用不需要修改以下設定：

| 設定 | 預設值 | 說明 |
|---|---:|---|
| Chrome Debug Port | `9223` | Chrome 連線埠 |
| 基本 request delay | `4` 秒 | 每次 request 前的基本等待 |
| 隨機額外等待 | `0–2` 秒 | 實際每次約等待 `4–6` 秒 |
| Cooldown | 每 `25` 筆後 `8` 秒 | 降低 CAPTCHA 或 rate limit 風險 |
| refresh 進度顯示 | 每 `1` 筆 | `refresh_existing_metrics.ps1` 的預設值 |

CLI 也可以用以下參數調整：

```powershell
--request-delay-seconds 4
--request-jitter-seconds 2
--cooldown-every 25
--cooldown-seconds 8
```

除非熟悉 Glassdoor 抓取限制，否則不建議把 delay 或 cooldown 降低；若遇到 CAPTCHA、登入失效或 rate limit，應先停止抓取。

## 輸出檔案在哪裡？

所有預設輸出都在 `artifacts` 資料夾。重要檔案包括：

- `reviews_aggregate.json`、`reviews_aggregate.csv`：成功取得的公司／地區彙總指標。
- `metrics_attempt_log.json`、`metrics_attempt_log.csv`：metrics 抓取嘗試與成功／失敗紀錄。
- `run_summary.json`：每次執行的摘要。
- `region_pool.json`：地區池與地區快取 checkpoint。
- `company_region_review_urls.json`、`company_region_review_urls.csv`：公司／地區對應的 review URL 清單與快取。
- 另外的 `office_locations.*`、`region_country_map.*`、`attempt_log.*` 也是現有流程資料，請一併保留。

## 安全與操作習慣

- 每次更新前**先備份整個 `artifacts` 資料夾**；更新後也再備份一次，並清楚標記日期。
- 不要把 session、cookies、token、password 或 secret 檔案提交、複製到共享位置或上傳 Git。
- 不要平行大量抓取；先用單一公司／地區小批量確認，再逐步增加範圍。
- 遵守每次 request 間 **4–6 秒 delay**。預設程式設定就是 4 秒基礎延遲加上最多 2 秒隨機延遲，並在每 25 次 request 後冷卻 8 秒，請不要任意調低。
- 遇到 CAPTCHA、登入失效或 rate limit 時，先停止抓取，不要用更密集的請求硬試。

## 出問題時

### CDP port 未啟動

確認已在本 PowerShell 視窗執行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，並重新執行 ` .\scripts\start_chrome_cdp.ps1`（指令前不需要空格）。接著重跑：

```powershell
Invoke-WebRequest http://127.0.0.1:9223/json/version
```

若仍失敗，關閉由腳本開啟的 Chrome 後再次啟動；也確認沒有其他程式占用 9223 port。

### 找不到 cache

請確認目前 PowerShell 的路徑是 `handoff` 根目錄，而不是 `scripts` 或其他資料夾。`extract-metrics` 需要先有 `artifacts\region_pool.json` 和 `artifacts\company_region_review_urls.json`。請先依序執行上面的 `discover-locations`、`resolve-review-urls`，不要直接刪除 artifacts。若 cache 已移動，可用完整的 `--output-dir` 或 cache 路徑參數指向正確位置。

### 登入、CAPTCHA 或 rate limit

確認是在 CDP 新 Chrome 中登入 Glassdoor，且該視窗仍保持開啟。若出現 CAPTCHA、被要求重新登入、429 或其他 rate limit，請暫停，等待後以較小批量重試；不要平行執行多個抓取程序，也不要降低 4–6 秒 request delay。

### Python 或 pip 問題

確認 Python 版本是 3.11 或更新版本：

```powershell
python --version
```

若 `.venv` 尚未建立或環境損壞，可在確認位於 `handoff` 根目錄後重建，再重新安裝：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

若 `pip` 顯示權限或網路錯誤，先確認網路連線、Python 安裝時已勾選加入 PATH，並使用上面的 `.venv\Scripts\python.exe -m pip`，不要直接依賴全域 `pip`。

## 交接後的資料更新原則

把 `artifacts` 視為目前分析基準與更新 checkpoint：先備份、更新 pool 與新 URL、抓取新 metrics、確認結果後再備份。一般更新不應刪除既有成功資料；只有明確要重建或重新抓取舊資料時，才使用 `--rebuild-*` 或 `--refresh-existing-metrics`。若不確定某個選項會不會改變資料，先不要執行，保留現有 artifacts 並尋求確認。
