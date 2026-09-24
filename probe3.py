# -*- coding: utf-8 -*-
"""探测：费用账单 in_unit × expense_name 组合与主键语义"""
import json
import pymysql

conf = json.load(open(r"D:\workboddy file\dudu di pin\lowfreq_local_v10.28.59-hotfix_FINAL\db_conf.json", encoding="utf-8"))
conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"],
                       password=conf["password"], database=conf["database"],
                       charset="utf8mb4", connect_timeout=30, read_timeout=300)
cur = conn.cursor()

def q(sql, tag="", n=30):
    print("\n### " + tag)
    try:
        cur.execute(sql)
        for r in cur.fetchall()[:n]:
            print("   ", r)
    except Exception as e:
        print("   ERR:", e)

q("""SELECT in_unit, expense_name, COUNT(*) c, SUM(after_taxes_fee) s
     FROM t_expense_bill WHERE is_del=0 GROUP BY in_unit, expense_name
     ORDER BY c DESC LIMIT 40""", "in_unit x expense_name")

q("""SELECT id, in_unit, in_unit_id, in_unit_name, out_unit, out_unit_id, out_unit_name,
      expense_name, fee, after_taxes_fee, business_type, create_time
     FROM t_expense_bill WHERE is_del=0 AND in_unit='merchant' LIMIT 3""", "in_unit=merchant sample")

q("""SELECT id, in_unit, in_unit_id, in_unit_name, expense_name, after_taxes_fee, create_time
     FROM t_expense_bill WHERE is_del=0 AND expense_name LIKE '%落柜场地换电分成%' LIMIT 3""", "落柜场地 sample")

q("""SELECT id, in_unit, in_unit_id, in_unit_name, expense_name, after_taxes_fee, create_time
     FROM t_expense_bill WHERE is_del=0 AND expense_name LIKE '%用户拓展换电分成%' LIMIT 3""", "用户拓展 sample")

q("""SELECT id, in_unit, in_unit_id, in_unit_name, expense_name, after_taxes_fee, create_time
     FROM t_expense_bill WHERE is_del=0 AND in_unit='swapSite' LIMIT 3""", "swapSite sample")

q("""SELECT COUNT(DISTINCT in_unit_id) FROM t_expense_bill WHERE is_del=0 AND in_unit='swapSite'""", "distinct swapSite ids")
q("""SELECT COUNT(DISTINCT in_unit_id) FROM t_expense_bill WHERE is_del=0 AND in_unit='signSiteChannel'""", "distinct signSiteChannel ids")
q("""SELECT COUNT(DISTINCT in_unit_id) FROM t_expense_bill WHERE is_del=0 AND in_unit IN ('promoter','l2_promoter')""", "distinct promoter ids")

q("""SELECT * FROM t_expense_bill WHERE is_del=0 ORDER BY create_time DESC LIMIT 2""", "latest bill full")

conn.close()
