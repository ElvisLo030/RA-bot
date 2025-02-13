<h1 align="center">RA DCbot</h1>

## 安裝模組
```bash
pip install -r requirements.txt
```

## DC BOT 設定
1.	在專案目錄內新增`.env`檔案
2.	加入以下環境變數：
```dotenv
DISCORD_TOKEN=YOUR_DISCORD_TOKEN
TARGET_CHANNEL_ID=YOUR_CHANNEL_ID #用於圖片審核的頻道ID
ADMIN_CHANNEL_ID=YOUR_CHANNEL_ID #後台管理的頻道ID
DASHBOARD_USERNAME=YOUR_USERNAME #後台網頁之使用者名稱
DASHBOARD_PASSWORD=YOUR_PASSWORD #後台網頁之密碼
```

## 功能簡介
### 相關指令與功能：
  - 前綴指令：`RA` 
  - `RA 功能選單`
    - 在私訊內輸入可呼叫功能選單
    - 綁定卡片、參加活動/任務、上傳圖片
  - `RA 後台管理`
    - 後台管理員指令，在 ADMIN_CHANNEL_ID 指定的頻道中使用
    - 建立活動/任物、查詢/修改玩家資料、封鎖玩家

### API和後台介面
---
使用 FastAPI 在本地端啟動後，透過 http://localhost:8080 存取API

或可以使用 http://localhost:8080/dashboard 查看後台網頁
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
### 目前版本：0.11 beta
### 最後更新日期：1140213
### support by elvislo 



