# -*- coding: utf-8 -*-
"""统一配置：数据库、路径、统计口径参数"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
for _d in (DATA_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

SQLITE_PATH = os.path.join(DATA_DIR, "citybike.db")

# 优先读取低频看板工程里的库配置，保证与既有工程一致；读取失败则用内置默认值
_CONF_CANDIDATES = [
    r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json",
    r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.64_FINAL\db_conf.json",
    os.path.join(BASE_DIR, "db_conf.json"),
]

DB = {
    "host": "db.example.com",
    "port": 3306,
    "user": "citybike_pro",
    "password"***",
    "database": "sharing-citybike-pro",
    "charset": "utf8mb4",
    "connect_timeout": 30,
    "read_timeout": 600,
}
for _p in _CONF_CANDIDATES:
    try:
        _c = json.load(open(_p, encoding="utf-8"))
        DB["host"] = _c.get("host", DB["host"])
        DB["port"] = int(_c.get("port", DB["port"]))
        DB["user"] = _c.get("user", DB["user"])
        DB["password"] = _c.get("password", DB["password"])
        DB["database"] = _c.get("database", DB["database"])
        CONF_SOURCE = _p
        break
    except Exception:
        CONF_SOURCE = "内置默认"

BASE_DB = "sharing-system-base-pro"      # 基础库（同实例）

# ---- 统计口径参数（与"低频看板"一致）----
LOWFREQ = {
    "protected_days": 15,   # 新用户保护期
    "L1_max_days": 30, "L1_min_count": 1,
    "L2_max_days": 45, "L2_min_count": 2,
    "L3_max_days": 60, "L3_min_count": 3,
    "L4_min_count": 4,
}
LOWFREQ_POWER_THRESHOLD = 25   # 电量低于该值视为 L5 提醒换电

BATTERY_DESIGN_CAPACITY = 24000   # 电池设计容量（Wh），电流 24A
SERVICE_PORT = 8090
