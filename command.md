# คำสั่งรันที่ใช้บ่อย

## เริ่มเก็บ live data

### เก็บทุก shared symbols

```powershell
.\start_live_collect.ps1
```

ค่า default ตอนนี้คือ:

- `flush-sec = 1`
- `hyperliquid-poll-sec = 1`
- `parquet-batch-sec = 60`
- ไม่เขียน raw JSONL ถ้าไม่ได้ใส่ `-WriteRaw`

### เก็บเฉพาะ 20 เหรียญที่แนะนำ

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA
```

### เก็บเฉพาะ 20 เหรียญที่แนะนำ เป็นเวลา 30 นาที

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA -DurationSec 1800
```

### เก็บแบบเดียวกัน แต่เปิด raw JSONL สำหรับ debug

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA -DurationSec 1800 -WriteRaw
```

## รันแบบ foreground

### ทดสอบแบบ all shared 5 นาที

```powershell
.\.venv\Scripts\python.exe -m src.collectors.live.collect_all_live --all-shared --duration-sec 300
```

### ทดสอบเฉพาะ 20 เหรียญที่แนะนำ 5 นาที

```powershell
.\.venv\Scripts\python.exe -m src.collectors.live.collect_all_live --symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA --duration-sec 300
```

## เช็คสถานะ

### ดู run info ล่าสุด

```powershell
Get-Content .\logs\collectors\live_collect_latest.json
```

### ดู log ล่าสุด

```powershell
Get-Content .\logs\collectors\live_collect_latest.json | ConvertFrom-Json
```

### ดูว่าไฟล์ latest ยังอัปเดตอยู่ไหม

```powershell
Get-Item .\data\processed\live_funding_snapshots_latest.csv,.\data\processed\live_book_snapshots_latest.csv,.\data\processed\live_trade_tape_latest.csv | Select-Object Name,Length,LastWriteTime
```

### ดูไฟล์ trade aggregates ล่าสุด

```powershell
Get-Item .\data\processed\live_trade_aggregates_latest.csv | Select-Object Name,Length,LastWriteTime
```

## หยุดการเก็บข้อมูล

### หยุดจาก PID ล่าสุด

```powershell
$run = Get-Content .\logs\collectors\live_collect_latest.json | ConvertFrom-Json
Stop-Process -Id $run.pid
```

## output หลัก

- `data/processed/live_funding_snapshots_latest.csv`
- `data/processed/live_book_snapshots_latest.csv`
- `data/processed/live_trade_tape_latest.csv`
- `data/processed/live_trade_aggregates_latest.csv`
- `data/processed/live/funding_snapshots/...parquet`
- `data/processed/live/book_snapshots/...parquet`
- `data/processed/live/trade_aggregates/...parquet`
- `data/raw/lighter/ws/...`
- `data/raw/hyperliquid/ws/...`
- `data/raw/hyperliquid/rest/live_info/...`
