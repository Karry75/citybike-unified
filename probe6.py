# -*- coding: utf-8 -*-
import json
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def q(sql, tag, n=40):
    print("\n### " + tag)
    try:
        cur.execute(sql)
        for r in cur.fetchall()[:n]:
            print("   ", r)
    except Exception as e:
        print("   ERR:", e)

for kw in ['%rent%', '%package%', '%violat%', '%breach%', '%earning%', '%settle%', '%coupon%', '%vehicle%', '%bike_control%']:
    q("SHOW TABLES LIKE '%s'" % kw, "tables " + kw, 25)

q("SELECT DISTINCT expense_name FROM t_expense_bill WHERE is_del=0 AND (expense_name LIKE '%违约%' OR expense_name LIKE '%长期%' OR expense_name LIKE '%滞纳%')", "expense 违约类")
q("SELECT business_type, business_sub_detail FROM t_expense_bill WHERE is_del=0 AND business_type='exchange_agreement' LIMIT 3", "agreement bill sample")
q("SELECT type, COUNT(*) FROM t_reception_log WHERE is_del=0 GROUP BY type ORDER BY 2 DESC LIMIT 30", "reception type dist")
q("SELECT COUNT(*) FROM t_reception_log WHERE is_del=0 AND solver_user_name IS NOT NULL AND solver_user_name<>''", "reception solver filled")
q("SELECT id,name FROM t_exchange_rent_package WHERE is_del=0 LIMIT 5", "package sample")
conn.close()
