# -*- coding: utf-8 -*-
"""公共工具：ADB 连接、时间/金额换算、SQLite 初始化。"""
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB, BASE_DB, SQLITE_PATH
import schema_def as sd

DAY = 86400000
NOW = int(time.time() * 1000)


def w(days):
    return NOW - days * DAY


W = {k: w(v) for k, v in dict(d1=1, d3=3, d7=7, d15=15, d30=30, d45=45, d60=60, d90=90).items()}
W["m1"] = W["d30"]
W["m3"] = W["d90"]


def d0(offset=0):
    """本地(UTC+8)某天 00:00 的毫秒时间戳，offset=-1 表示昨天。"""
    t = datetime.now() + timedelta(days=offset)
    return int((datetime(t.year, t.month, t.day) - timedelta(hours=8)).timestamp() * 1000)


YDAY0, TODAY0 = d0(-1), d0(0)


def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def conn(db=None):
    cfg = dict(DB)
    if db:
        cfg["database"] = db
    cfg["charset"] = "utf8mb4"
    cfg["connect_timeout"] = 20
    cfg["read_timeout"] = 1800
    return pymysql.connect(**cfg)


def q(c, sql, args=None):
    cur = c.cursor(pymysql.cursors.DictCursor)
    cur.execute(sql, args or ())
    return cur.fetchall()


def stream(c, sql, args=None):
    cur = c.cursor(pymysql.cursors.SSDictCursor)
    cur.execute(sql, args or ())
    for row in cur:
        yield row
    cur.close()


def ts(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000 + 8 * 3600).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def ymd(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000 + 8 * 3600).strftime("%Y-%m-%d")
    except Exception:
        return ""


def yuan(fen):
    if fen in (None, ""):
        return ""
    try:
        return round(float(fen) / 100.0, 2)
    except Exception:
        return ""


def n1(v):
    if v in (None, ""):
        return ""
    try:
        return round(float(v), 1)
    except Exception:
        return ""


def ni(v):
    if v in (None, ""):
        return ""
    try:
        return int(float(v))
    except Exception:
        return ""


def s(v):
    if v is None:
        return ""
    return str(v).strip()


def sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    c = sqlite3.connect(SQLITE_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=OFF")
    return c


def init_sqlite():
    c = sqlite_conn()
    for menu, keys in sd.DATA_KEYS.items():
        cols = ", ".join('"%s" TEXT' % k for k in keys)
        c.execute("DROP TABLE IF EXISTS %s" % menu)
        c.execute("CREATE TABLE %s (%s)" % (menu, cols))
    c.execute("DROP TABLE IF EXISTS meta")
    c.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    c.commit()
    return c
