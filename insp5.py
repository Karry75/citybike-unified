# -*- coding: utf-8 -*-
"""大改需求配套探查：售车/优惠券/补贴/电池型号容量/仓位断充/电费库/费用账单科目"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import conn, q, s

ac = conn()

def show(title):
    print("\n===== %s =====" % title, flush=True)

def cols(t):
    try:
        rs = q(ac, "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT FROM information_schema.columns "
                   "WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ORDINAL_POSITION", (t,))
        return rs
    except Exception as e:
        print("  %s 列读取失败: %s" % (t, e))
        return []

def dump_cols(t, full=False):
    rs = cols(t)
    if not rs:
        return
    print("-- %s (%d 列)" % (t, len(rs)))
    for r in rs:
        c = s(r.get("COLUMN_COMMENT"))
        if full:
            print("   %-34s %-12s %s" % (r["COLUMN_NAME"], r["DATA_TYPE"], c))

# ---------------- 1. 售车相关表
show("1. 售车/销量相关表")
tabs = q(ac, "SELECT table_name, table_comment FROM information_schema.tables "
             "WHERE table_schema=DATABASE() AND (table_name LIKE '%%sale%%' OR table_name LIKE '%%bike_order%%' "
             "OR table_name LIKE '%%sell%%') ORDER BY table_name")
for t in tabs:
    n = q(ac, "SELECT COUNT(*) n FROM %s" % t["table_name"])[0]["n"]
    print("  %-44s %9d  %s" % (t["table_name"], n, s(t.get("table_comment"))[:30]))

show("2. 售车主表结构候选")
for name in ("t_bike_sale", "t_bike_sale_order", "t_bike_order"):
    dump_cols(name)

# ---------------- 2. 优惠券
show("3. 优惠券表结构")
dump_cols("t_user_coupon")
for r in q(ac, "SELECT * FROM t_user_coupon WHERE is_del=0 LIMIT 2"):
    print("  sample:", {k: str(v)[:60] for k, v in list(r.items())})

show("4. 套餐订单券字段")
dump_cols("t_user_exchange_rent_package_order")
for r in q(ac, "SELECT id, exchange_agreement_id, user_coupon_id, deduct_fee, package_real_fee, pay_time "
               "FROM t_user_exchange_rent_package_order WHERE is_del=0 AND user_coupon_id IS NOT NULL "
               "AND user_coupon_id<>'' LIMIT 5"):
    print("  ", dict(r))

show("5. 多券协议样例")
rs = q(ac, """SELECT exchange_agreement_id, COUNT(*) n, GROUP_CONCAT(user_coupon_id) ids,
              SUM(deduct_fee) fee FROM t_user_exchange_rent_package_order
              WHERE is_del=0 AND user_coupon_id IS NOT NULL AND user_coupon_id<>''
              GROUP BY exchange_agreement_id ORDER BY n DESC LIMIT 5""")
for r in rs:
    print("  ", dict(r))

# ---------------- 3. 补贴
show("6. 补贴表结构")
for name in ("t_bike_sale_rent_subsidy_log", "t_bike_sale_exchange_subsidy_log",
             "t_bike_sale_subsidy_relation"):
    dump_cols(name)

show("7. 补贴样例(退补贴判定字段)")
try:
    for r in q(ac, "SELECT * FROM t_bike_sale_rent_subsidy_log WHERE is_del=0 LIMIT 2"):
        print("  rent:", {k: str(v)[:50] for k, v in list(r.items())})
except Exception as e:
    print("  rent err:", e)
try:
    for r in q(ac, "SELECT * FROM t_bike_sale_exchange_subsidy_log WHERE is_del=0 LIMIT 2"):
        print("  exc:", {k: str(v)[:50] for k, v in list(r.items())})
except Exception as e:
    print("  exc err:", e)

# ---------------- 4. 电池型号与容量
show("8. 电池型号/容量")
dump_cols("t_battery_model")
for r in q(ac, "SELECT * FROM t_battery_model WHERE is_del=0 LIMIT 6"):
    print("  ", {k: str(v)[:40] for k, v in list(r.items())})
dump_cols("t_battery")
dump_cols("t_battery_product")

show("9. 电池 type/device_type_id 与型号对应")
for r in q(ac, "SELECT b.type, b.device_type_id, COUNT(*) n FROM t_battery b WHERE b.is_del=0 "
               "GROUP BY b.type, b.device_type_id ORDER BY n DESC LIMIT 10"):
    print("  ", dict(r))

# ---------------- 5. 仓位与断充
show("10. 仓位 sensor/status 分布")
for r in q(ac, "SELECT status, sensor, COUNT(*) n FROM t_exchange_store WHERE is_del=0 "
               "GROUP BY status, sensor ORDER BY n DESC LIMIT 20"):
    print("  ", dict(r))
show("11. 空仓但 sensor 有值(疑似断充)")
for r in q(ac, """SELECT COUNT(*) n FROM t_exchange_store
                  WHERE is_del=0 AND (battery_sn IS NULL OR battery_sn='')
                  AND sensor IS NOT NULL AND sensor<>''"""):
    print("  empty_battery_with_sensor:", dict(r))
for r in q(ac, "SELECT device_sn, number, status, sensor, battery_sn, error, lock_status FROM t_exchange_store "
               "WHERE is_del=0 AND (battery_sn IS NULL OR battery_sn='') AND sensor IS NOT NULL AND sensor<>'' LIMIT 5"):
    print("  sample:", dict(r))
show("12. 仓位另一枚举: sensor 全量")
for r in q(ac, "SELECT sensor, COUNT(*) n FROM t_exchange_store WHERE is_del=0 GROUP BY sensor ORDER BY n DESC LIMIT 20"):
    print("  ", dict(r))

# ---------------- 6. 电费库
show("13. 电费库 site_info")
p = r"D:\workboddy file\2026-09-07-15-34-16\electricity_fee_system\data\app.db"
print("  exists:", os.path.exists(p))
if os.path.exists(p):
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    names = [r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("  tables:", names)
    for t in names:
        try:
            n = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            print("  %-24s %8d" % (t, n))
        except Exception as e:
            print("  %s err %s" % (t, e))
    try:
        cs = c.execute("PRAGMA table_info(site_info)").fetchall()
        print("  site_info %d 列:" % len(cs))
        for x in cs:
            print("     %-30s %s" % (x["name"], x["type"]))
        r = c.execute("SELECT * FROM site_info LIMIT 1").fetchone()
        if r:
            print("  sample:", {k: str(r[k])[:40] for k in r.keys()})
    except Exception as e:
        print("  site_info err", e)
    c.close()

# ---------------- 7. 费用账单科目
show("14. t_expense_bill 科目与收入方")
for r in q(ac, "SELECT expense_name, COUNT(*) n, SUM(after_taxes_fee) amt FROM t_expense_bill "
               "WHERE is_del=0 GROUP BY expense_name ORDER BY n DESC LIMIT 20"):
    print("   %-30s %9d %16s" % (s(r["expense_name"])[:30], r["n"], r["amt"]))
for r in q(ac, "SELECT in_unit, COUNT(*) n FROM t_expense_bill WHERE is_del=0 GROUP BY in_unit ORDER BY n DESC LIMIT 20"):
    print("   in_unit %-20s %d" % (s(r["in_unit"]), r["n"]))

# ---------------- 8. 网点表可用列（物业/分成等）
show("15. t_site 关键列扫描")
want = ("property", "share", "ratio", "deposit", "electric", "meter", "contract", "fee", "income", "settle")
for r in cols("t_site"):
    nm = r["COLUMN_NAME"].lower()
    if any(w in nm for w in want):
        print("   %-32s %-10s %s" % (r["COLUMN_NAME"], r["DATA_TYPE"], s(r.get("COLUMN_COMMENT"))[:30]))

print("\nDONE", flush=True)
