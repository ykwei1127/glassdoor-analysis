# Glassdoor 資料更新｜簡易使用說明

這份說明是給不需要閱讀程式碼的使用者。請把整個 `handoff` 資料夾保留在電腦上，之後所有操作都在這個資料夾中進行。

## 目前已經準備好的資料

這份交接包不是空白專案，已經包含上一輪抓取結果：

- **18 家公司**的資料
- **136 個地區**的區域 pool
- **639 筆**公司／地區評分資料
- 每筆資料包含整體評分、推薦率、CEO approval、評論數，以及多個分類評分
- 也保留了 URL 清單、辦公室地點、執行紀錄與錯誤紀錄，方便下一輪更新

目前的資料在：

```text
handoff\artifacts\
```

請不要刪除或搬動這個資料夾。它是之後更新資料的基礎。

> 注意：目前有些公司／地區在 Glassdoor 找不到有效頁面，或頁面沒有提供完整評分，因此不是每一個可能組合都有資料。這是目前網站資料狀態，不代表程式沒有執行。

## 第一次設定環境

### 1. 安裝必要軟體

請先安裝：

- Python 3.11 或更新版本
- Google Chrome

安裝時如果看到「Add Python to PATH」，建議勾選。

### 2. 建立環境

在 `handoff` 資料夾內開啟 PowerShell，貼上以下兩行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

這個步驟只需要第一次做。

## 開始更新資料

### 1. 開啟可登入 Glassdoor 的 Chrome

在同一個 PowerShell 視窗貼上：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_chrome_cdp.ps1
```

接著在新開的 Chrome 視窗登入 Glassdoor，並保持這個視窗開啟。

### 2. 執行一輪資料更新

確認已登入後，在 `handoff` 根目錄貼上：

```powershell
.\scripts\update_data.ps1 -RefreshExisting
```

這個腳本會自動：

1. 備份目前的 `artifacts`
2. 更新公司的辦公室地點與區域 pool
3. 找出新的公司／地區 review URL
4. 抓取尚未完成的新資料
5. 重新更新既有公司／地區的最新評分

更新可能需要一段時間，請不要關閉 PowerShell 或 Chrome，也不要同時開另一個更新程序。

如果這次只想補抓新地區，不想重新抓既有評分，可以使用：

```powershell
.\scripts\update_data.ps1
```

## 只更新既有公司／地區的評分

如果你只想把目前已經有的公司／地區評分更新成 Glassdoor 最新數字，**不要使用上面的 `update_data.ps1`**，請使用另一支專用腳本：

```powershell
.\scripts\refresh_existing_metrics.ps1
```

這支腳本只會重新抓取既有評分，不會更新：

- 公司辦公室地點
- 區域 pool
- 公司／地區 review URL
- 新增公司或新地區

第一次建議先只測試 10 筆：

```powershell
.\scripts\refresh_existing_metrics.ps1 -MaxExtractions 10
```

確認結果正常後，再執行不帶 `-MaxExtractions` 的完整更新。這兩支腳本都會先自動備份 `artifacts`。

## 更新完成後看哪裡？

最重要的結果在：

```text
artifacts\reviews_aggregate.csv
artifacts\reviews_aggregate.json
```

一般分析建議使用 `reviews_aggregate.csv`，可以直接用 Excel 開啟。

其他檔案用途：

- `run_summary.json`：本次更新的統計摘要
- `region_pool.json`：目前所有地區
- `company_region_review_urls.json`：公司與地區的 review URL 狀態
- `metrics_attempt_log.json`：每次抓取的成功與失敗紀錄

## 重要提醒

- 每次更新前，腳本會自動建立 `artifacts_backup_日期時間` 備份。
- 不要刪除 `artifacts`，否則程式會失去目前的資料基準。
- 不要把 cookies、登入資料或其他個人資料放進共享資料夾。
- 如果看到 CAPTCHA、要求重新登入、429 或 rate limit，請先停止，稍後再試。
- 不要同時執行兩個更新腳本。

## 如果遇到問題

### Chrome 沒有開啟或無法連線

重新執行：

```powershell
.\scripts\start_chrome_cdp.ps1
```

確認在新開的 Chrome 登入 Glassdoor 後，再重新執行更新腳本。

### Python 或環境錯誤

確認目前 PowerShell 位於 `handoff` 資料夾，並重新執行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

### 抓取被中止

先不要刪除任何檔案。保留 `artifacts` 與自動建立的 backup，記下畫面上的錯誤訊息，再請熟悉的人協助確認。
