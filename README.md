<h1 align="center">RA DCbot</h1>

## 開發進度
- 1140114  
  - 基礎照片審核功能  
- 1140115  
  - 新增按鈕審核功能＋自動私訊回覆結果  
- 1140118  
  - 新增卡片綁定介面  
- 1140121  
  - 使用 `fastapi` 進行簡單的 API 測試  
  - 新增簡易投票系統  
- 1140128  
  - 將審核頻道 ID 導入 `.env`  
- 1140203  
  - 新增積點、活動、任務功能
  - 刪除投票功能
- 1140205
  - **修改程式框架和細部內容**

## 安裝模組
```bash
pip install -r requirements.txt
```
執行上述指令以安裝此專案所需的 Python 套件

## DC BOT 設定
1.	在專案目錄內新增`.env`檔案
2.	加入以下環境變數：
```dotenv
DISCORD_TOKEN=YOUR_DISCORD_TOKEN
TARGET_CHANNEL_ID=YOUR_CHANNEL_ID #用於圖片審核的頻道ID
ADMIN_CHANNEL_ID=YOUR_CHANNEL_ID #後台管理的頻道ID
```
## 功能簡介
### 相關指令：
  - `RA 功能選單`
    - 在私訊內輸入可呼叫功能選單
  - `RA 後台管理`
    - 後台管理員指令，在 ADMIN_CHANNEL_ID 指定的頻道中使用

### FastAPI 後端 API
---
使用 FastAPI 作為後端 API，可在本地端啟動後，透過 http://localhost:8080 存取目前已架設的路由
1. GET/
- 根路由，回傳簡單的歡迎訊息
2. /images
- GET/images: 查詢所有已上傳圖片
- POST/images: 新增一筆圖片資料
3. /event
- POST/event: 建立新活動
- GET/event: 取得所有活動列表
- PUT/event: 清除所有活動 (重置用)
- GET/event/{event_id}: 取得特定活動資訊
4. /task
- POST/task: 建立新任務並隸屬於某個活動
- GET/task/{task_id}: 取得特定任務資訊
5. /gamer
- POST/gamer: 建立新的玩家資料
- GET/gamer/{gamer_id}: 取得特定玩家資訊
- PUT/gamer/{gamer_id}/points: 增加指定玩家點數
- PUT/gamer/{gamer_id}/card: 更新玩家卡號
---
### 目前版本：0.0.7 beta
### support by elvislo 



