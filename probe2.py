# -*- coding: utf-8 -*-
"""探测：换电订单、接待记录、费用账单口径"""
import json, sys
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def q(sql, tag=""):
    print("\n### " + tag)
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        for r in rows[:25]:
            print("   ", r)
        print("   -- rows:", len(rows))
    except Exception as e:
        print("   ERR:", e)

q("SELECT COUNT(*) FROM t_exchange_order", "order count")
q("SELECT order_status, COUNT(*) FROM t_exchange_order GROUP BY order_status", "order_status dist")
q("SELECT MIN(FROM_UNIXTIME(create_time/1000+28800)), MAX(FROM_UNIXTIME(create_time/1000+28800)) FROM t_exchange_order", "order time range")
q("SELECT COUNT(DISTINCT exchange_agreement_id) FROM t_exchange_order WHERE order_status='success' AND is_del=0", "agreements with success orders")
q("SHOW TABLES LIKE 't_reception%'", "reception table")
q("SELECT COUNT(*) FROM t_reception_log", "reception count")
q("SELECT * FROM t_reception_log ORDER BY create_time DESC LIMIT 3", "reception sample")
q("SELECT in_unit, COUNT(*) c FROM t_expense_bill WHERE is_del=0 GROUP BY in_unit ORDER BY c DESC LIMIT 30", "expense in_unit dist")
q("SELECT expense_name, COUNT(*) c FROM t_expense_bill WHERE is_del=0 GROUP BY expense_name ORDER BY c DESC LIMIT 40", "expense_name dist")
q("SELECT business_type, COUNT(*) c FROM t_expense_bill WHERE is_del=0 GROUP BY business_type ORDER BY c DESC LIMIT 30", "business_type dist")

conn.close()
