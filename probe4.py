# -*- coding: utf-8 -*-
"""探测设备上报原始报文结构"""
import json
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def show(sql, tag, maxlen=2200):
    print("\n### " + tag)
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        for r in rows[:2]:
            for i, v in enumerate(r):
                s = str(v)
                print("   [%d] %s" % (i, s[:maxlen]))
    except Exception as e:
        print("   ERR:", e)

show("SELECT last_upload_data FROM t_exchange_last_upload WHERE last_upload_data IS NOT NULL AND last_upload_data<>'' ORDER BY last_upload_time DESC LIMIT 2", "cabinet last_upload_data")
show("SELECT source_data FROM t_battery_last_upload WHERE source_data IS NOT NULL AND source_data<>'' ORDER BY update_time DESC LIMIT 2", "battery source_data")
show("SELECT sector FROM (SELECT 1) t", "noop")
conn.close()
