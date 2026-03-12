# Deploy ด้วย Docker Compose

เอกสารนี้ใช้กับโปรเจคนี้โดยตรง ถ้าต้องการรัน collector แบบ `docker compose`

## ไฟล์ที่เพิ่มแล้ว

- [Dockerfile](/d:/git/poc_lighter_hyperliquid/Dockerfile)
- [compose.yaml](/d:/git/poc_lighter_hyperliquid/compose.yaml)
- [docker/collector-entrypoint.sh](/d:/git/poc_lighter_hyperliquid/docker/collector-entrypoint.sh)
- [.dockerignore](/d:/git/poc_lighter_hyperliquid/.dockerignore)

## behavior ปัจจุบัน

container จะทำตามนี้:

1. เช็กว่า `config.yaml` มีอยู่
2. รัน `collect_reference_data`
3. เริ่ม `collect_all_live --all-shared --write-r2`

output:

- local bind mount:
  - `./data`
  - `./logs`
- R2:
  - `live/funding_snapshots/...parquet`
  - `live/book_snapshots/...parquet`
  - `live/trade_aggregates/...parquet`

## เตรียมก่อนรัน

1. ติดตั้ง Docker และ Docker Compose plugin บนเครื่อง server
2. วาง `config.yaml` ที่ root ของ repo
3. เช็กว่า `config.yaml` ใส่ค่า R2 ครบ

## คำสั่งหลัก

### build และ start

```bash
docker compose up -d --build
```

### ดู log

```bash
docker compose logs -f
```

### หยุด

```bash
docker compose down
```

### restart

```bash
docker compose restart
```

## ปรับค่า runtime

แก้ใน [compose.yaml](/d:/git/poc_lighter_hyperliquid/compose.yaml) ได้เลย เช่น:

- `WRITE_R2`
- `WRITE_RAW`
- `FLUSH_SEC`
- `PARQUET_BATCH_SEC`
- `SYMBOLS`
- `DURATION_SEC`
- `EXTRA_ARGS`

ตัวอย่าง ถ้าจะเก็บแค่ BTC,ETH,SOL:

```yaml
environment:
  ALL_SHARED: "0"
  SYMBOLS: "BTC,ETH,SOL"
```

ตัวอย่าง ถ้าจะเปิด raw:

```yaml
environment:
  WRITE_RAW: "1"
```

## หมายเหตุ

- container ใช้ bind mount ดังนั้นข้อมูลไม่หายเมื่อ recreate container
- ตอนนี้เครื่อง local นี้ยังไม่มี `docker` ติดตั้ง ผมเลยสร้างไฟล์ deploy ให้ แต่ยังไม่ได้ validate ด้วย `docker compose up` จริงบนเครื่องนี้
