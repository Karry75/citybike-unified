# -*- coding: utf-8 -*-
import json
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def q(sql, tag, n=200):
    print("\n### " + tag)
    try:
        cur.execute(sql)
        for r in cur.fetchall()[:n]:
            print("   ", r)
    except Exception as e:
        print("   ERR:", e)

for kw in ['%bike%', '%maker%', '%store_employee%', '%merchant%']:
    q("SHOW TABLES LIKE '%s'" % kw, "tables " + kw, 40)

for t in ['t_user_exchange_rent_package_order', 't_user_exchange_rent_violated_order',
          't_user_exchange_package', 't_bike_rent', 't_maker_earning_subsidy_log']:
    q("SELECT column_name, column_comment FROM information_schema.columns WHERE table_schema='sharing-citybike-pro' AND table_name='%s' ORDER BY ordinal_position" % t, "cols " + t, 60)
    q("SELECT COUNT(*) FROM %s WHERE is_del=0" % t, "count " + t, 2)
conn.close()
