# Glassdoor 資料更新｜簡易使用說明

這份說明是給不需要閱讀程式碼的使用者。大部分操作都可以直接在 `handoff` 資料夾內**雙擊檔案**完成。

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
- Node.js 18 或更新版本（安裝時會一併安裝 npm）
- Google Chrome

安裝 Python 時，如果看到「Add Python to PATH」，建議勾選。

### 2. 建立環境

在 `handoff` 資料夾內，雙擊：

```text
1_setup_environment.bat
```

它會自動建立環境並安裝程式。這個步驟只需要第一次做。

## 每次更新資料的操作順序

### 1. 開啟 Chrome 並登入 Glassdoor

雙擊：

```text
2_start_chrome_cdp.bat
```

它會開啟一個專用的 Chrome 視窗。請在這個新視窗登入 Glassdoor，並保持視窗開啟。

### 2. 先測試 10 筆既有評分

雙擊：

```text
3_test_10_metrics.bat
```

這會只更新 10 筆既有公司／地區評分。畫面會逐筆顯示進度，例如：

```text
Extraction progress: 3/639
```

### 3. 測試正常後，更新全部既有評分

雙擊：

```text
4_refresh_all_existing_metrics.bat
```

這是最常用的更新方式。它只會重新抓取既有公司／地區的最新評分，不會更新：

- 公司辦公室地點
- 區域 pool
- 公司／地區 review URL
- 新增公司或新地區

### 4. 只有需要新增地區或更新公司地點時

雙擊：

```text
5_update_all_data.bat
```

這個完整更新會：

1. 備份目前的 `artifacts`
2. 更新公司的辦公室地點與區域 pool
3. 找出新的公司／地區 review URL
4. 抓取尚未完成的新資料
5. 更新既有公司／地區的最新評分

完整更新可能需要較長時間。除非確實需要新增地區或更新公司地點，否則優先使用第 4 個檔案更新既有評分即可。

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
- 不要同時執行兩個更新檔案。
- 不要把 cookies、登入資料或其他個人資料放進共享資料夾。
- 如果看到 CAPTCHA、要求重新登入、429 或 rate limit，請先停止，稍後再試。
- 每筆抓取之間會自動等待，看到進度慢慢增加是正常的。

## 如果遇到問題

### Chrome 沒有開啟或無法連線

重新雙擊：

```text
2_start_chrome_cdp.bat
```

確認在新開的 Chrome 登入 Glassdoor 後，再重新雙擊測試或更新檔案。

### Python 或環境錯誤

重新雙擊：

```text
1_setup_environment.bat
```

### 抓取被中止

先不要刪除任何檔案。保留 `artifacts` 與自動建立的 backup，記下畫面上的錯誤訊息，再請熟悉的人協助確認。

參數、安全設定與較完整的技術說明，請參考同一個資料夾內的 `README.md`。
