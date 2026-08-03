#目標
我要做一個 glassdoor 網站資料的抓取工具，抓取不同公司的 review 資料，例如 ASUS 的網站 https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm
這個連結進去會有一個類似 header 的區塊顯示: ASUS reviews
然後不同的地區會有以下變化，例如台北的 review: ASUS Taipei reviews
所以說我需要抓取每個公司，然後盡可能多的地區的 review，我想要把這些地區做成一個 pool，每個公司都掃這個地區 pool，如果有資料就抓出來。
我到時候會把這些公司然後地區資料分群作分析。

我需要抓取資料組成以下欄位:
| 欄位 | 說明 |
|------|------|
| Company | 公司名稱 |
| Review URL | Glassdoor Review 頁面 URL |
| Overall | 整體評分 |
| Recommend | 推薦比例 |
| CEO Approval | CEO 支持率 |
| Total Reviews | 評論總數 |
| Diversity & Inclusion | 多元與包容 |
| Work/Life Balance | 工作生活平衡 |
| Compensation and Benefits | 薪酬福利 |
| Culture & Values | 文化價值 |
| Career Opportunities | 職涯機會 |
| Senior Management | 高階管理 |


#抓取地區
https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm
不同公司可能會在 office location 上填寫他們公司地區，這些地區可能會有 reivew，我想要把各公司這些地區混合當作基礎 pool，然後後續再找更多 glassdoor 上有的地區，增大 pool，用來給各公司撈取資料用

我之後會需要把不同地區分群:
Taiwan
APAC
EMEA
Americas
Global(header 上沒有地區，我就稱他為 global)
所以說增加 pool 時，要盡量符合這些能分進群體中的國家或城市


#目標公司
ASUS(我主要需要分析的公司)
NVIDIA
TSMC
MSI
HP Inc.
Quanta Computer
Wistron
Compal Electronics
Wiwynn
Delta Electronics
Inventec
Pegatron
AU Optronics
Trend Micro Inc.
Dell Technologies
Acer Group
Lenovo
Google


#資料正確性需求
因為我發現有時候我想要的公司地區組成的 url，會跟實際頁面上的地區不同，所以說我的 review 頁面 url 需要有一個核對的步驟，例如我要抓 asus taipei，就要確定 review 頁面開起來上面是寫 ASUS Taipei reviews，不能是 ASUS ShangHai reviews


#技術
我想要用 python
未來如果要做前後端，後端用 FastAPI，前端用 Vite 相關或者你推薦


#Note
有不清楚需要確認的地方再跟我詢問，有建議的做法直接提出來讓我 review



