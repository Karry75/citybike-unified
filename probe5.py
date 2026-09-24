# -*- coding: utf-8 -*-
"""dump 设备上报报文完整键结构"""
import json
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def tree(obj, prefix="", depth=0, maxdepth=3, out=None):
    if out is None:
        out = []
    if depth > maxdepth:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = prefix + "." + k if prefix else k
            if isinstance(v, dict):
                out.append((p, "{...}"))
                tree(v, p, depth + 1, maxdepth, out)
            elif isinstance(v, list):
                out.append((p, "[list len=%d]" % len(v)))
                if v and isinstance(v[0], (dict, list)):
                    tree(v[0], p + "[0]", depth + 1, maxdepth, out)
                elif v:
                    out.append((p + "[0]", str(v[0])[:80]))
            else:
                out.append((p, str(v)[:90]))
    return out

cur.execute("SELECT last_upload_data FROM t_exchange_last_upload WHERE last_upload_data LIKE '%restart%' OR last_upload_data LIKE '%alarmSwitch%' ORDER BY last_upload_time DESC LIMIT 1")
r = cur.fetchone()
if not r:
    cur.execute("SELECT last_upload_data FROM t_exchange_last_upload WHERE last_upload_data IS NOT NULL ORDER BY last_upload_time DESC LIMIT 1")
    r = cur.fetchone()
data = json.loads(r[0])
docs = tree(data)
lines = ["### CABINET PAYLOAD KEYS (%d)" % len(docs)]
lines += ["%s  =  %s" % (a, b) for a, b in docs]
open(r"D:\workboddy file\dudu分析\citybike_unified\payload_cabinet.txt", "w", encoding="utf-8").write("\n".join(lines))

cur.execute("SELECT source_data FROM t_battery_last_upload WHERE source_data IS NOT NULL ORDER BY update_time DESC LIMIT 1")
r2 = cur.fetchone()[0]
sd = json.loads(r2)
inner = json.loads(sd["jsonStr"]) if "jsonStr" in sd else sd
docs2 = tree(inner, maxdepth=3)
lines2 = ["### BATTERY PAYLOAD KEYS (%d)" % len(docs2), "outer: " + ", ".join(sd.keys())]
lines2 += ["%s  =  %s" % (a, b) for a, b in docs2]
open(r"D:\workboddy file\dudu分析\citybike_unified\payload_battery.txt", "w", encoding="utf-8").write("\n".join(lines2))
print("\n".join(lines))
print()
print("\n".join(lines2))
conn.close()
