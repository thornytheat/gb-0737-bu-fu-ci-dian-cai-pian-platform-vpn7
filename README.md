# 布幅疵点裁片台

制服工场的验布和裁床共用这份卷宗。台面显示真实卷布坐标、禁切区、裁片、切口和未用量。各卷签条可打印，归档可独立下载。

## 启动

```sh
docker compose up --build
```

打开 `http://localhost:18426/`。SQLite 归档保存在 Compose 命名卷内。本地可用 Python 3.11 或 3.12。

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 18426
```

可用 `FABRIC_DB` 和 `FABRIC_SAMPLES` 指向独立数据库和来源目录。默认使用 `var/fabric.sqlite3` 和 `sample_data/`。

## 演示

1. 保持「东库到货 · 原始验布」与刀口 5 mm，点击「排版归档」。核对 8 片、40 mm 切口、差额 0 mm。
2. 选 `R-001`，查看重叠安全区并集。选 `R-003`，查看整卷封存与原始疵点行。选 `R-005`，查看裁片连刀口用到卷尾 625 mm。
3. 打开「换卷核算」下的「工单欠料」，确认 `C004` 缺 1 片。可在「裁床签条」的归档历史切回其他批次。
4. 点击「重跑」显示核验一致。「打印签条」打开当前卷的打印视图，「导出卷宗」下载本次归档及证据。

## 模块与验证

模块接口为 `GET /api/intake`、`/api/locate`、`/api/zones`、`/api/fit`、`/api/changeovers`、`/api/ledger`、`/api/slips`。模块都能用 `sample=dirty` 或 `sample=clean` 单独试算，支持 `kerf_mm` 及归档 `run_id`。`POST /api/runs` 归档，`POST /api/runs/{id}/rerun` 重算核验，`GET /api/export/{id}` 独立下载。接口文档在 `/docs`。

详情见 [数据字典](docs/DATA-DICTIONARY.md) 和 [深度登记](docs/DEPTH.md)。项目采用有界一维配长，超过规划上限时需拆分工单。

```sh
docker compose exec -T app pytest -q
```
