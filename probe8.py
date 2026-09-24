# -*- coding: utf-8 -*-
import json
import re
import pymysql

p = r"C:\Users\Karry\AppData\Roaming\Tencent\Marvis\User\oAN1i2X2kt2giqZmP1GRegCVbS-U\workspace\conv_9546494933534973bc077ebf084a7c02\temp\schema_dump.txt"
txt = open(p, encoding="utf-8", errors="ignore").read()
for t in ["t_site_store_employee", "t_merchant", "t_promoter", "t_exchange_rent_package", "t_site"]:
    m = re.search(r"^.*%s.*$" % t, txt, re.M)
    idx = txt.find(t)
    print("\n=== " + t + " ===")
    print(txt[idx-200: idx+2600] if idx > 0 else "NOT FOUND")

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()
for t in ["t_bike_user_relation", "t_user_exchange_rent_violated_log"]:
    print("\n### cols " + t)
    cur.execute("SELECT column_name, column_comment FROM information_schema.columns WHERE table_schema='sharing-citybike-pro' AND table_name='%s' ORDER BY ordinal_position" % t)
    for r in cur.fetchall():
        print("   ", r)
conn.close()
