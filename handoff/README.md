# Glassdoor Aggregate Metrics 交接包

## 先說明：工作目錄

**所有命令都要從本 `handoff` 資料夾根目錄執行。** 請先在檔案總管開啟 `handoff`，在該資料夾按右鍵選擇「在終端機中開啟」，或在 PowerShell 執行 `cd` 進入這個資料夾。

這是一份可獨立延續工作的副本，原始專案不需要放在同一個位置。

## 這個工具做什麼？

這個工具會從 Glassdoor 抓取**公司／地區層級的 aggregate review metrics（彙總評論指標）**，例如整體評分、各項評分與評論數等。它不是下載每一則評論，而是整理公司在指定地區的彙總資料。

交接包內已經帶有目前的 `artifacts` 資料（包括快取、成功結果、嘗試紀錄與執行摘要），可以直接從目前進度繼續。**請不要刪除 `artifacts` 資料夾或其中的檔案。**

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

## 建議的第一次小批量流程

請先只跑單一公司／地區，確認流程正常。以下指令都從 `handoff` 根目錄執行，使用 ASUS、Taipei、CDP port 9223：

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage discover-locations
```

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage resolve-review-urls
```

```powershell
.venv\Scripts\python.exe -m glassdoor_analysis --companies ASUS --regions Taipei --browser-cdp-url http://127.0.0.1:9223 --stage extract-metrics --max-extractions 1
```

工具會使用 `artifacts` 裡的快取。**快取已存在時不要隨意加入 `--rebuild-region-pool` 或 `--rebuild-review-urls`**，除非你確定要重新建立對應資料；重建可能改變現有 checkpoint。

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
- 遵守每次 request 間 **8–12 秒 delay**。預設程式設定就是 8 秒基礎延遲加上最多 4 秒隨機延遲，請不要任意調低。
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

確認是在 CDP 新 Chrome 中登入 Glassdoor，且該視窗仍保持開啟。若出現 CAPTCHA、被要求重新登入、429 或其他 rate limit，請暫停，等待後以較小批量重試；不要平行執行多個抓取程序，也不要降低 8–12 秒 request delay。

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

## 交接原則

把 `artifacts` 視為可延續的 checkpoint：先備份、再執行、確認結果後再備份。若不確定某個選項是否會重建或覆蓋資料，先不要執行，保留現有 artifacts 並尋求確認。
