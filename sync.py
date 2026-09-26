# -*- coding: utf-8 -*-
"""全量同步 ADB 数据 -> 本地 SQLite，供看板秒级查询。

用法: python sync.py
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (BASE_DB, DAY, NOW, TODAY0, W, YDAY0, conn, init_sqlite, log, n1, ni, q, s, sqlite_conn, stream, ts, ymd, yuan)
from config import LOWFREQ, LOWFREQ_POWER_THRESHOLD
import schema_def as sd

CAP = 24000  # 电池设计容量

# 换电订单状态口径：
#  老数据(2021-09~2023-08) order_status='success'，无 agreement 字段
#  新数据(2023-04~今)     order_status='created'，成败看 exchange_order_status='success'
OKF = "((order_status='success') OR (order_status='created' AND exchange_order_status='success'))"
FAILF = "(order_status='fail' OR exchange_order_status IN ('fail','error','cancel'))"


def pick(cols, *cands):
    cl = [c.lower() for c in cols]
    for c in cands:
        if c.lower() in cl:
            return c
    return None


def ins(sq, menu, rows):
    keys = sd.DATA_KEYS[menu]
    ph = ", ".join("?" * len(keys))
    cols = ", ".join('"%s"' % k for k in keys)
    sq.executemany("INSERT INTO %s (%s) VALUES (%s)" % (menu, cols, ph),
                   [[r.get(k, "") for k in keys] for r in rows])


def batch(sq, menu, gen, size=2000):
    buf, total = [], 0
    for r in gen:
        buf.append(r)
        if len(buf) >= size:
            ins(sq, menu, buf)
            total += len(buf)
            buf = []
    if buf:
        ins(sq, menu, buf)
        total += len(buf)
    return total


# --------------------------------------------------------------------- 维度
def load_dims(ac, bc):
    log("加载维度表 ...")
    d = {}
    d["agency"] = {}
    try:
        for r in q(bc, "SELECT id, name FROM t_cm_agency WHERE is_del=0"):
            d["agency"][int(r["id"])] = s(r["name"])
    except Exception as e:
        log("  t_cm_agency 读取失败: %s" % e)
    for t in ("t_merchant", "t_site_store_employee", "t_distributor", "t_promoter",
              "t_exchange_rent_package", "t_battery_product", "t_battery_series"):
        try:
            rows = q(ac, "SELECT * FROM %s WHERE is_del=0" % t)
            d[t] = {int(r["id"]): r for r in rows}
            log("  %s %d 条" % (t, len(rows)))
        except Exception as e:
            d[t] = {}
            log("  %s 读取失败: %s" % (t, e))
    d["user"] = {}
    for r in q(ac, "SELECT id, phone, username FROM t_user WHERE is_del=0"):
        d["user"][int(r["id"])] = r
    log("  t_user %d 条" % len(d["user"]))
    return d


# --------------------------------------------------------------- 分摊/费用
def load_expense(ac):
    """t_expense_bill 按收入方聚合（累计 / 昨日 / 近3天 / 近7天 / 电费类）。"""
    log("聚合 t_expense_bill 收入方金额 ...")
    sql = """
    SELECT in_unit, in_unit_id,
           SUM(after_taxes_fee) AS total,
           SUM(CASE WHEN create_time>=%s AND create_time< %s THEN after_taxes_fee ELSE 0 END) AS d1,
           SUM(CASE WHEN create_time>=%s THEN after_taxes_fee ELSE 0 END) AS d3,
           SUM(CASE WHEN create_time>=%s THEN after_taxes_fee ELSE 0 END) AS d7,
           SUM(CASE WHEN expense_name LIKE %s THEN after_taxes_fee ELSE 0 END) AS elec,
           SUM(CASE WHEN expense_name LIKE %s THEN after_taxes_fee ELSE 0 END) AS share
    FROM t_expense_bill
    WHERE is_del=0 AND (is_cancel=0 OR is_cancel IS NULL)
    GROUP BY in_unit, in_unit_id
    """
    args = (YDAY0, TODAY0, W["d3"], W["d7"], "%电费%", "%分成%")
    out = {}
    n = 0
    for r in stream(ac, sql, args):
        key = (s(r["in_unit"]), str(r["in_unit_id"]))
        out[key] = r
        n += 1
    log("  收入方 %d 组" % n)
    return out


def agg_by_unit(exp, units):
    """把某类收入方聚合成 {id: {'total':分,'d1':分,'elec':分,'share':分}}"""
    res = {}
    for (u, uid), r in exp.items():
        if u not in units:
            continue
        try:
            k = int(uid)
        except Exception:
            continue
        a = res.setdefault(k, {"total": 0.0, "d1": 0.0, "d3": 0.0, "d7": 0.0, "elec": 0.0, "share": 0.0})
        for f in ("total", "d1", "d3", "d7", "elec", "share"):
            a[f] += float(r.get(f) or 0)
    return res


# ------------------------------------------------------------------- 主流程
def main():
    t0 = time.time()
    ac, bc = conn(), conn(BASE_DB)
    sq = init_sqlite()
    dims = load_dims(ac, bc)
    agency, merchant = dims["agency"], dims["t_merchant"]
    employee, distributor = dims["t_site_store_employee"], dims["t_distributor"]
    promoter, pkg, bprod = dims["t_promoter"], dims["t_exchange_rent_package"], dims["t_battery_product"]
    series = dims.get("t_battery_series", {})
    users = dims["user"]

    # ---- 网点基础
    log("拉取 t_site ...")
    sites = q(ac, "SELECT * FROM t_site WHERE is_del=0")
    site_map = {int(r["id"]): r for r in sites}
    log("  t_site %d 条" % len(sites))

    # ---- 换电柜基础
    log("拉取 t_exchange ...")
    cabs = q(ac, "SELECT * FROM t_exchange WHERE is_del=0")
    cab_map = {int(r["id"]): r for r in cabs}
    cab_by_sn = {s(r["device_sn"]): r for r in cabs}
    log("  t_exchange %d 条" % len(cabs))
    xid2site = {}
    for r in cabs:
        xid2site[int(r["id"])] = int(r["site_id"] or 0)

    # ---- 换电订单聚合（按协议 / 按柜 / 按电池）
    log("聚合 t_exchange_order（按协议）...")
    ag_swap = {}
    for r in stream(ac, """
        SELECT exchange_agreement_id AS aid, COUNT(*) AS c_all,
               SUM(CASE WHEN back_battery_time IS NOT NULL THEN 1 ELSE 0 END) AS back_cnt,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c15,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c30,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c45,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c60,
               MIN(take_battery_time) AS t_first,
               MAX(take_battery_time) AS t_last,
               MAX(back_battery_time) AS t_last_back
        FROM t_exchange_order
        WHERE is_del=0 AND %s AND exchange_agreement_id>0
        GROUP BY exchange_agreement_id
    """ % (W["d15"], W["d30"], W["d45"], W["d60"], OKF)):
        ag_swap[int(r["aid"])] = r
    log("  协议换电 %d 条" % len(ag_swap))

    log("拉取每协议最后一单（电池/柜）...")
    ag_last = {}
    for r in stream(ac, """
        SELECT o.exchange_agreement_id AS aid, o.take_battery_sn, o.take_battery_power,
               o.back_battery_sn, o.back_battery_power, o.take_battery_time, o.back_battery_time,
               o.take_exchange_sn, o.take_exchange_id, o.take_battery_id
        FROM t_exchange_order o
        JOIN (SELECT exchange_agreement_id AS a, MAX(id) AS mid FROM t_exchange_order
              WHERE is_del=0 AND %s AND exchange_agreement_id>0 GROUP BY exchange_agreement_id) t ON o.id=t.mid
    """ % OKF):
        ag_last[int(r["aid"])] = r
    log("  最后订单 %d 条" % len(ag_last))

    log("聚合 t_exchange_order（按换电柜）...")
    cab_swap = {}
    for r in stream(ac, """
        SELECT take_exchange_id AS xid, COUNT(*) AS c_all,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c7,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c30,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c90,
               COUNT(DISTINCT CASE WHEN take_battery_time>=%s THEN take_user_id END) AS u7,
               COUNT(DISTINCT CASE WHEN take_battery_time>=%s THEN take_user_id END) AS u30,
               COUNT(DISTINCT CASE WHEN take_battery_time>=%s THEN take_user_id END) AS u90,
               COUNT(DISTINCT take_user_id) AS u_all,
               MAX(take_battery_time) AS t_last
        FROM t_exchange_order
        WHERE is_del=0 AND %s AND take_exchange_id>0
        GROUP BY take_exchange_id
    """ % (W["d7"], W["d30"], W["d90"], W["d7"], W["d30"], W["d90"], OKF)):
        cab_swap[int(r["xid"])] = r
    log("  换电柜换电 %d 条" % len(cab_swap))

    log("聚合失败订单 ...")
    cab_fail = {}
    for r in stream(ac, """
        SELECT take_exchange_id AS xid, COUNT(*) AS f_all,
               SUM(CASE WHEN create_time>=%s THEN 1 ELSE 0 END) AS f30
        FROM t_exchange_order
        WHERE is_del=0 AND %s AND take_exchange_id>0
        GROUP BY take_exchange_id
    """ % (W["d30"], FAILF)):
        cab_fail[int(r["xid"])] = r
    log("  失败订单 %d 条" % len(cab_fail))

    log("聚合电池借出次数 ...")
    bat_borrow = {}
    for r in stream(ac, """
        SELECT take_battery_id AS bid, COUNT(*) AS c_all,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c30,
               SUM(CASE WHEN take_battery_time>=%s THEN 1 ELSE 0 END) AS c90
        FROM t_exchange_order
        WHERE is_del=0 AND %s AND take_battery_id>0
        GROUP BY take_battery_id
    """ % (W["d30"], W["d90"], OKF)):
        bat_borrow[int(r["bid"])] = r
    log("  电池借出 %d 条" % len(bat_borrow))

    # ---- 租金/套餐订单
    log("聚合租期套餐订单 ...")
    ag_rent = {}
    ag_pkg_first, ag_pkg_last = {}, {}
    for r in stream(ac, """
        SELECT exchange_agreement_id AS aid, COUNT(*) AS cnt,
               SUM(COALESCE(package_real_fee,0)) AS real_fee,
               SUM(COALESCE(package_total_fee,0)) AS total_fee,
               SUM(COALESCE(refund_fee,0)) AS refund_fee,
               SUM(COALESCE(combo_pay_fee,0)) AS combo_fee,
               SUM(COALESCE(deduct_fee,0)) AS deduct_fee,
               MIN(pay_time) AS t_first, MAX(pay_time) AS t_last
        FROM t_user_exchange_rent_package_order
        WHERE is_del=0 AND exchange_agreement_id IS NOT NULL
        GROUP BY exchange_agreement_id
    """):
        ag_rent[int(r["aid"])] = r
    log("  租期订单 %d 组" % len(ag_rent))

    log("拉取首/末套餐订单明细 ...")
    for r in stream(ac, """
        SELECT t.aid, o.package_id, o.package_name, o.package_total_fee, o.package_real_fee,
               o.pay_time, o.bike_id, o.bike_sn, o.user_coupon_id, o.deduct_fee
        FROM t_user_exchange_rent_package_order o
        JOIN (SELECT exchange_agreement_id AS aid, MIN(id) AS mid FROM t_user_exchange_rent_package_order
              WHERE is_del=0 GROUP BY exchange_agreement_id) t ON o.id=t.mid
    """):
        ag_pkg_first[int(r["aid"])] = r
    for r in stream(ac, """
        SELECT t.aid, o.package_id, o.package_name, o.package_total_fee, o.package_real_fee,
               o.pay_time, o.bike_id, o.bike_sn, o.user_coupon_id, o.deduct_fee
        FROM t_user_exchange_rent_package_order o
        JOIN (SELECT exchange_agreement_id AS aid, MAX(id) AS mid FROM t_user_exchange_rent_package_order
              WHERE is_del=0 GROUP BY exchange_agreement_id) t ON o.id=t.mid
    """):
        ag_pkg_last[int(r["aid"])] = r
    log("  首%d / 末%d" % (len(ag_pkg_first), len(ag_pkg_last)))

    # ---- 违约
    log("聚合违约订单 ...")
    ag_viol = {}
    for r in stream(ac, """
        SELECT l.exchange_agreement_id AS aid, COUNT(*) AS cnt, SUM(COALESCE(o.pay_fee,0)) AS fee,
               SUM(CASE WHEN l.expire_time IS NOT NULL AND l.expire_time>0
                        THEN (COALESCE(l.solve_time, %s) - l.expire_time) ELSE 0 END) AS hours
        FROM t_user_exchange_rent_violated_order o
        JOIN t_user_exchange_rent_violated_log l ON l.id=o.violated_log_id
        WHERE o.is_del=0 AND l.exchange_agreement_id IS NOT NULL
        GROUP BY l.exchange_agreement_id
    """, (NOW,)):
        ag_viol[int(r["aid"])] = r
    log("  违约 %d 组" % len(ag_viol))

    # ---- 接待
    log("拉取最近接待 ...")
    ag_rec = {}
    for r in stream(ac, """
        SELECT t.aid, o.solver_user_name, o.type, o.detail, o.create_time
        FROM t_reception_log o
        JOIN (SELECT agreement_id AS aid, MAX(id) AS mid FROM t_reception_log
              WHERE is_del=0 GROUP BY agreement_id) t ON o.id=t.mid
    """):
        ag_rec[int(r["aid"])] = r
    log("  接待 %d 组" % len(ag_rec))

    # ---- 车辆授权
    log("聚合车辆授权人数 ...")
    bike_auth = {}
    for r in q(ac, "SELECT bike_id, COUNT(*) AS n FROM t_bike_user_relation WHERE is_del=0 AND bike_id>0 GROUP BY bike_id"):
        bike_auth[int(r["bike_id"])] = int(r["n"])
    log("  授权车辆 %d 台" % len(bike_auth))

    # ---- 电池按车辆统计（协议电池数量）
    log("聚合电池归属车辆 ...")
    bat_by_bike = {}
    for r in q(ac, "SELECT bike_sn, COUNT(*) AS n FROM t_battery WHERE is_del=0 AND bike_sn IS NOT NULL AND bike_sn<>'' GROUP BY bike_sn"):
        bat_by_bike[s(r["bike_sn"])] = int(r["n"])
    log("  电池归属车辆 %d 台" % len(bat_by_bike))

    # ---- 电费结算
    log("聚合电费结算 ...")
    elec = {}
    for r in q(ac, """
        SELECT site_id, MAX(settle_time) AS t_settle, SUM(COALESCE(settle_amount,0)) AS amount,
               MAX(total_electric_usage) AS degree
        FROM t_exchange_electric_settlement WHERE is_del=0 GROUP BY site_id
    """):
        elec[int(r["site_id"])] = r
    log("  电费结算 %d 网点" % len(elec))

    # ---- 费用账单
    exp = load_expense(ac)
    site_income = agg_by_unit(exp, ("swapSite", "signSite"))
    merchant_income = agg_by_unit(exp, ("swapSiteChannel", "signSiteChannel", "merchant"))
    promoter_income = agg_by_unit(exp, ("promoter", "l2_promoter", "maker"))
    log("  网点%d 商户%d 推广%d" % (len(site_income), len(merchant_income), len(promoter_income)))

    # ============================================================== 用户协议
    log("生成【用户协议】...")
    today_ms = NOW

    def gen_agreement():
        sql = "SELECT * FROM t_exchange_agreement WHERE is_del=0"
        for r in stream(ac, sql):
            aid = int(r["id"])
            site = site_map.get(int(r["site_id"] or 0), {})
            sw = ag_swap.get(aid) or {}
            lo = ag_last.get(aid) or {}
            rt = ag_rent.get(aid) or {}
            p1 = ag_pkg_first.get(aid) or {}
            p2 = ag_pkg_last.get(aid) or {}
            v = ag_viol.get(aid) or {}
            rc = ag_rec.get(aid) or {}
            u = users.get(int(r["user_id"] or 0), {})
            pk = pkg.get(int(r["rent_package_id"] or 0), {})
            emp = employee.get(int(r["sign_site_store_employee_id"] or 0), {})
            ago = agency.get(int(r["agency_id"] or 0), "")
            dis = distributor.get(int(r["distributor_id"] or 0), {})
            mch = merchant.get(int(site.get("merchant_id") or 0), {})
            pro = promoter.get(int(r["promoter_id"] or 0), {})
            bp = bprod.get(int(r["battery_product_id"] or 0), {})

            # 到期 / 欠租 / 未换电
            exp_ms = int(r["rent_expire_time"] or 0)
            st = s(r["status"])
            arrears = ""
            if st in ("arrears", "欠租") or (exp_ms and exp_ms < today_ms and st not in ("stop", "已终止")):
                if exp_ms:
                    arrears = round((today_ms - exp_ms) / float(DAY), 1)
            last_take = int(sw.get("t_last") or 0)
            base = last_take or int(r["activation_time"] or 0)
            no_swap = round((today_ms - base) / float(DAY), 1) if base else ""
            # 月均换电频次
            act = int(r["activation_time"] or 0)
            months = max((today_ms - act) / float(DAY) / 30.0, 1.0) if act else 1.0
            back_cnt = int(sw.get("back_cnt") or 0)
            monthly = round(back_cnt / months, 2) if act else ""
            # 换电周期
            cycle = ""
            if last_take and act and int(sw.get("c_all") or 0) > 1:
                cycle = round((last_take - act) / float(DAY) / max(int(sw["c_all"]) - 1, 1), 1)
            # 低频 / 档位
            lf, lv = "否", ""
            days = no_swap if no_swap != "" else None
            if days is not None and days > LOWFREQ["protected_days"]:
                if days <= 30 and back_cnt < 1:
                    lf, lv = "是", "L1"
                elif days <= 45 and back_cnt < 2:
                    lf, lv = "是", "L2"
                elif days <= 60 and back_cnt < 3:
                    lf, lv = "是", "L3"
                elif days > 60 and back_cnt < 4:
                    lf, lv = "是", "L4"
            bp_now = lo.get("take_battery_sn") if not lo.get("back_battery_time") else lo.get("back_battery_sn")
            bpower = lo.get("take_battery_power") if not lo.get("back_battery_time") else lo.get("back_battery_power")
            if bpower is None:
                bpower = ""
            if bpower != "" and float(bpower or 0) > 0 and bp_now and float(bpower) < LOWFREQ_POWER_THRESHOLD:
                lv = lv or "L5"
            if lv:
                lf = "是"
            pkg_fee_first = yuan(p1.get("package_real_fee"))
            yield {
                "id": aid,
                "agreement_type": s(r.get("type")),
                "status": st,
                "battery_product_name": s(bp.get("name")),
                "sale_scenario": s(r.get("site_sale_scenario_name")),
                "user_id": r.get("user_id"), "user_name": s(r.get("user_name")),
                "user_phone": s(r.get("user_phone")), "cur_phone": s(u.get("phone")),
                "company_id": r.get("company_id"), "company_name": s(r.get("company_name")),
                "company_admin_phone": s(r.get("company_super_admin_consumer_phone")),
                "bike_count": ni(r.get("bike_count")),
                "battery_count": bat_by_bike.get(s((p2 or p1).get("bike_sn")), ""),
                "rent_remain_days": round((exp_ms - today_ms) / float(DAY), 1) if exp_ms > today_ms else 0,
                "package_price": yuan(pk.get("real_fee") or pk.get("fee")),
                "package_name": s(pk.get("name")) or s(p1.get("package_name")),
                "province": s(r.get("t_city_name")), "city": s(site.get("city")),
                "area": s(site.get("area")), "street": s(site.get("street")),
                "community": s(site.get("community")),
                "site_id": r.get("site_id"), "site_name": s(site.get("name")),
                "business_id": r.get("sign_site_business_id"),
                "business_name": s(r.get("sign_site_business_name")),
                "merchant_id": site.get("merchant_id"), "merchant_name": s(mch.get("name")),
                "merchant_phone": s(mch.get("lp_phone")),
                "guide_id": r.get("sign_site_store_employee_id"), "guide_name": s(emp.get("name")),
                "guide_phone": s(emp.get("phone")),
                "deposit_status": s(r.get("deposit_status")),
                "deposit_pay_way": s(r.get("deposit_payway")),
                "deposit_fee": yuan(r.get("deposit_fee")),
                "deposit_deduct_status": ("已划扣" if float(r.get("deposit_real_fee") or 0) > 0 else "未划扣"),
                "agency_id": r.get("agency_id"), "agency_name": ago,
                "distributor_name": s(dis.get("name")),
                "is_first": ("是" if r.get("is_first") == 1 else "否"),
                "promoter_id": r.get("promoter_id"), "promoter_name": s(pro.get("name")),
                "t_create_time": ts(r.get("create_time")),
                "t_activation_time": ts(r.get("activation_time")),
                "t_stop_time": ts(r.get("stop_time")),
                "t_rent_expire_time": ts(exp_ms),
                "arrears_days": arrears, "no_swap_days": no_swap,
                "monthly_swap": monthly, "swap_cycle_days": cycle,
                "last_op_type": ("柜内归还电池" if lo.get("back_battery_time") else ("柜内借出电池" if lo else "")),
                "battery_sn": s(bp_now), "battery_power": bpower,
                "battery_status": ("在位" if bp_now else ""),
                "t_battery_last_time": ts(max(int(lo.get("take_battery_time") or 0), int(lo.get("back_battery_time") or 0))),
                "battery_last_loc": s(lo.get("take_exchange_sn")),
                "c_15": ni(sw.get("c15")), "c_30": ni(sw.get("c30")),
                "c_45": ni(sw.get("c45")), "c_60": ni(sw.get("c60")),
                "is_lowfreq": lf, "lowfreq_level": lv,
                "bike_id": p2.get("bike_id") or p1.get("bike_id"),
                "bike_sn": s(p2.get("bike_sn") or p1.get("bike_sn")),
                "auth_user_count": (bike_auth.get(int(p2.get("bike_id") or p1.get("bike_id") or 0), "")
                                    if (p2.get("bike_id") or p1.get("bike_id")) else ""),
                "coupon_ids": p2.get("user_coupon_id") or p1.get("user_coupon_id"),
                "coupon_names": "", "coupon_fee": yuan(p2.get("deduct_fee") or p1.get("deduct_fee")),
                "first_pkg_id": p1.get("package_id"), "first_pkg_name": s(p1.get("package_name")),
                "first_pkg_fee": yuan(p1.get("package_total_fee")), "first_pkg_real_fee": pkg_fee_first,
                "last_pkg_id": p2.get("package_id"), "last_pkg_name": s(p2.get("package_name")),
                "last_pkg_fee": yuan(p2.get("package_total_fee")), "last_pkg_real_fee": yuan(p2.get("package_real_fee")),
                "cur_pkg_id": r.get("rent_package_id"), "cur_pkg_name": s(pk.get("name")),
                "cur_pkg_fee": yuan(pk.get("fee")), "cur_pkg_real_fee": yuan(pk.get("real_fee")),
                "t_pkg_expire_time": ts(exp_ms),
                "relet_count": max(int(rt.get("cnt") or 0) - 1, 0),
                "relet_fee": round(float(rt.get("real_fee") or 0) / 100.0 - float(p1.get("package_real_fee") or 0) / 100.0, 2) if rt else "",
                "svc_pay_fee": yuan(rt.get("combo_fee")), "svc_refund_fee": yuan(rt.get("refund_fee")),
                "coupon_pay_fee": yuan(rt.get("deduct_fee")),
                "violate_count": ni(v.get("cnt")), "violate_hours": n1(float(v.get("hours") or 0) / 3600000.0) if v else 0,
                "violate_fee": yuan(v.get("fee")),
                "auto_relet": ("开启" if r.get("is_auto_pay") == 1 else "关闭"),
                "is_contract_bike": ("是" if r.get("is_bike_share") == 1 else "否"),
                "is_replace": ("是" if r.get("is_replacement") == 1 else "否"),
                "is_long_term": ("是" if r.get("is_rent_permanent_valid") == 1 else "否"),
                "battery_org": s(r.get("battery_lessor")),
                "t_last_reception": ts(rc.get("create_time")),
                "last_solver": s(rc.get("solver_user_name")),
                "last_reception_type": s(rc.get("type")),
                "last_reception_detail": s(rc.get("detail")),
            }

    n = batch(sq, "agreement", gen_agreement())
    log("  用户协议写入 %d 行" % n)
    sq.commit()

    # ================================================================ 网点
    log("生成【网点】...")
    site_sign, site_unsub = {}, {}
    for r in q(ac, """SELECT site_id, COUNT(*) AS n,
                            SUM(CASE WHEN create_time>=%s THEN 1 ELSE 0 END) AS m1,
                            SUM(CASE WHEN create_time>=%s THEN 1 ELSE 0 END) AS m3
                      FROM t_exchange_agreement WHERE is_del=0 GROUP BY site_id""", (W["d30"], W["d90"])):
        site_sign[int(r["site_id"])] = r
    for r in q(ac, """SELECT site_id, COUNT(*) AS n,
                            SUM(CASE WHEN stop_time>=%s THEN 1 ELSE 0 END) AS m1,
                            SUM(CASE WHEN stop_time>=%s THEN 1 ELSE 0 END) AS m3
                      FROM t_exchange_agreement WHERE is_del=0 AND stop_time>0 GROUP BY site_id""", (W["d30"], W["d90"])):
        site_unsub[int(r["site_id"])] = r

    site_cab = {}
    for r in cabs:
        sid = int(r["site_id"] or 0)
        a = site_cab.setdefault(sid, {"n": 0, "online": 0, "offline": 0, "slots": 0, "bat": 0, "sns": []})
        a["n"] += 1
        if s(r["online_status"]) in ("1", "online", "Online"):
            a["online"] += 1
        else:
            a["offline"] += 1
        a["sns"].append(s(r["device_sn"]))

    log("  聚合柜内仓位（按柜）...")
    store_agg = {}
    bat_slot = {}
    for r in stream(ac, """SELECT device_sn, COUNT(*) AS total,
                                  SUM(CASE WHEN battery_sn IS NOT NULL AND battery_sn<>'' THEN 1 ELSE 0 END) AS bat,
                                  SUM(CASE WHEN status='full' THEN 1 ELSE 0 END) AS full,
                                  SUM(CASE WHEN status='none' THEN 1 ELSE 0 END) AS none,
                                  SUM(CASE WHEN status='charging' THEN 1 ELSE 0 END) AS charging,
                                  SUM(CASE WHEN status='error' OR (error IS NOT NULL AND error<>'') THEN 1 ELSE 0 END) AS err,
                                  SUM(CASE WHEN lock_status='lock' AND battery_sn<>'' THEN 1 ELSE 0 END) AS lock
                           FROM t_exchange_store WHERE is_del=0 GROUP BY device_sn"""):
        store_agg[s(r["device_sn"])] = r
    for r in stream(ac, """SELECT battery_sn, device_sn, number, status FROM t_exchange_store
                           WHERE is_del=0 AND battery_sn IS NOT NULL AND battery_sn<>''"""):
        bat_slot[s(r["battery_sn"])] = r
    log("  仓位聚合 %d 柜 / %d 电池位" % (len(store_agg), len(bat_slot)))

    log("  拉取柜机上报 ...")
    upl = {}
    for r in stream(ac, "SELECT * FROM t_exchange_last_upload WHERE is_del=0"):
        upl[s(r["device_sn"])] = r
    log("  上报 %d 柜" % len(upl))

    site_swap = {}
    for xid, r in cab_swap.items():
        sid = xid2site.get(xid, 0)
        a = site_swap.setdefault(sid, {"c_all": 0, "c7": 0, "c30": 0, "c90": 0, "t_last": 0})
        a["c_all"] += int(r.get("c_all") or 0)
        for f, k in (("c7", "c7"), ("c30", "c30"), ("c90", "c90")):
            a[f] += int(r.get(k) or 0)
        a["t_last"] = max(a["t_last"], int(r.get("t_last") or 0))

    def gen_site():
        for r in sites:
            sid = int(r["id"])
            inc = site_income.get(sid, {})
            cab = site_cab.get(sid, {})
            sw = site_swap.get(sid, {})
            sign = site_sign.get(sid, {}) or {}
            uns = site_unsub.get(sid, {}) or {}
            el = elec.get(sid, {}) or {}
            mch = merchant.get(int(r.get("merchant_id") or 0), {})
            ago = agency.get(int(r.get("agency_id") or 0), "")
            dis = distributor.get(int(r.get("distributor_id") or 0), {})
            mgr = employee.get(int(r.get("store_manager_maker_id") or 0), {})
            # 商户/导购分成：该网点商户名下全部网点 + 导购(maker) 收入方
            m_total = 0.0
            if mch.get("maker_id"):
                m_total = promoter_income.get(int(mch.get("maker_id")), {}).get("total", 0.0)
            g_total = promoter_income.get(int(r.get("store_manager_maker_id") or 0), {}).get("total", 0.0)
            t_last_ex = max(int(sw.get("t_last") or 0), 0)
            yield {
                "id": sid, "name": s(r.get("name")), "image": s(r.get("logo")),
                "industry": s(r.get("industry_id")), "site_type": s(r.get("type")),
                "cabinet_status": ("有柜" if cab.get("n") else "无柜"),
                "exchange_total": cab.get("n", 0), "exchange_online": cab.get("online", 0),
                "exchange_offline": cab.get("offline", 0),
                "battery_total": cab.get("bat", ""), "battery_available": cab.get("full", ""),
                "slot_used": "", "slot_total": "",
                "agency_id": r.get("agency_id"), "agency_name": ago,
                "distributor_id": r.get("distributor_id"), "distributor_name": s(dis.get("name")),
                "merchant_id": r.get("merchant_id"), "merchant_name": s(mch.get("name")),
                "business_id": r.get("business_id"), "business_name": s(r.get("business_name")),
                "battery_product": s(bprod.get(int(r.get("battery_product_id") or 0), {}).get("name")),
                "battery_series": s(series.get(int(r.get("battery_series_id") or 0), {}).get("name")),
                "site_status": s(r.get("site_status")),
                "address": s(r.get("union_address") or r.get("address")),
                "has_monitor": ("是" if r.get("alone_meter_status") not in (None, "") else ""),
                "is_promotion": ("是" if r.get("is_promoter") == 1 else "否"),
                "sale_qrcode": "", "independent_meter": s(r.get("alone_meter_number")),
                "electric_settle_type": s(r.get("electric_settle_way")),
                "electric_settle_cycle": s(r.get("electric_settle_cycle")),
                "t_last_settle": ts(el.get("t_settle")),
                "province": s(r.get("province")), "city": s(r.get("city")), "area": s(r.get("area")),
                "street": s(r.get("street")), "community": s(r.get("community")),
                "detail_address": s(r.get("address")),
                "t_create": ts(r.get("create_time")), "t_open": ts(r.get("start_open_time")),
                "t_close": ts(r.get("close_time")),
                "show_in_app": ("是" if r.get("is_show") == 1 else "否"),
                "income_owner": s(mgr.get("name")) or s(mch.get("name")),
                "income_owner_phone": s(mgr.get("phone")) or s(mch.get("lp_phone")),
                "cabinet_sn": ",".join(cab.get("sns", [])[:5]),
                "c_15": "", "c_30": "", "c_45": "", "c_60": "",
                "c_all": sw.get("c_all", 0), "has_exchange": ("是" if sw.get("c_all") else "否"),
                "has_sale": "", "indoor": s(r.get("site_placement")),
                "sign_user_all": sign.get("n", 0), "unsub_user_all": uns.get("n", 0),
                "sign_user_1m": sign.get("m1", 0), "unsub_user_1m": uns.get("m1", 0),
                "sign_user_3m": sign.get("m3", 0), "unsub_user_3m": uns.get("m3", 0),
                "c_3d": "", "c_7d": sw.get("c7", 0),
                "c_1m": sw.get("c30", 0), "c_3m": sw.get("c90", 0),
                "c_total": sw.get("c_all", 0),
                "t_last_exchange": ts(t_last_ex),
                "sale_1d": "", "sale_3d": "", "sale_7d": "", "sale_30d": "", "sale_all": "",
                "income_yesterday": yuan(inc.get("d1")), "income_total": yuan(inc.get("total")),
                "charge_rule": "", "merchant_share_total": yuan(m_total), "guide_share_total": yuan(g_total),
                "warn_time": "", "electric_price": "", "last_settle_degree": n1(el.get("degree")),
                "t_last_settle2": ts(el.get("t_settle")), "t_next_settle": "",
                "need_settle": "", "settle_cycle": s(r.get("electric_settle_cycle")),
                "settle_fee": yuan(el.get("amount")), "year_place_fee": "", "share_ratio": "",
                "meter_status": s(r.get("alone_meter_status")),
                "settle_type2": s(r.get("electric_settle_way")), "fee_plan_detail": "",
                "t_open2": ts(r.get("start_open_time")),
                "battery_product_name": s(bprod.get(int(r.get("battery_product_id") or 0), {}).get("name")),
                "property_company": "", "t_cooperate": "", "contract_period": "",
                "pay_account": "", "cabinet_type": "",
                "service_price": "", "place_deposit": "", "total_fee": "",
                "cabinet_offline_cnt": cab.get("offline", 0),
                "cabinet_status2": ("有柜" if cab.get("n") else "无柜"),
                "income_item": "", "charge_standard": "",
                "c_total2": sw.get("c_all", 0), "battery_in_cabinet": cab.get("bat", ""),
                "c_3m2": sw.get("c90", 0), "c_1m2": sw.get("c30", 0),
                "c_7d2": sw.get("c7", 0), "c_3d2": "",
                "has_exchange2": ("是" if sw.get("c_all") else "否"), "has_sale2": "",
                "indoor2": s(r.get("site_placement")),
                "is_24h": ("是" if r.get("is_all_day_open") == 1 else "否"),
                "sign_user_all2": sign.get("n", 0), "unsub_user_all2": uns.get("n", 0),
                "sign_user_1m2": sign.get("m1", 0), "unsub_user_1m2": uns.get("m1", 0),
                "sign_user_3m2": sign.get("m3", 0), "unsub_user_3m2": uns.get("m3", 0),
                "t_last_exchange2": ts(t_last_ex),
                "meter_degree_now": n1(el.get("degree")), "power_consume": "",
                "order_count": sw.get("c_all", 0), "order_fee": yuan(inc.get("total")),
            }

    n = batch(sq, "site", gen_site())
    log("  网点写入 %d 行" % n)
    sq.commit()

    # ============================================================== 换电柜
    log("生成【换电柜】...")
    ckeys = sd.DATA_KEYS["cabinet"]

    def jload(raw):
        if not raw:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def jget(obj, *path, **kw):
        """按路径取值，缺失返回 kw.get('default','')"""
        cur = obj
        for p in path:
            if not isinstance(cur, dict):
                return kw.get("default", "")
            cur = cur.get(p)
            if cur is None:
                return kw.get("default", "")
        if isinstance(cur, (dict, list)):
            return json.dumps(cur, ensure_ascii=False)
        return cur

    def sc(v):
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return v

    def jnorm(raw):
        """把柜机两种上报报文（新 ds 结构 / 老平铺结构）归一成统一的 ds 结构。"""
        j = jload(raw)

        def ad(x):
            return x if isinstance(x, dict) else {}

        ds = ad(j.get("ds"))
        if ds:
            out = dict(ds)
            out.setdefault("sn", j.get("sn") or ds.get("sn"))
            out["slots"] = ds.get("slots") if isinstance(ds.get("slots"), list) else []
            out["adaps"] = ds.get("adaps") if isinstance(ds.get("adaps"), list) else []
            out["alarms"] = ad(ds.get("alarms"))
            out["main"] = ad(ds.get("main"))
            out["acq"] = ad(ds.get("acq"))
            out["params"] = ad(ds.get("params"))
            out["vers"] = ad(ds.get("vers"))
            return {"c": j.get("c"), "t": j.get("t"), "ds": out}

        # ---- 老平铺结构 ----
        slots = []
        for st0 in (j.get("stores") or []):
            st0 = ad(st0)
            bat = ad(st0.get("battery"))
            chg = s(st0.get("charging"))
            slots.append({
                "idx": st0.get("index"), "sn": s(bat.get("sn")),
                "soc": ni(bat.get("power")) if bat.get("power") not in (None, "") else -1,
                "voltage": (chg.split("|")[1] if chg.count("|") >= 2 else ""),
                "current": (chg.split("|")[0] if chg.count("|") >= 2 else ""),
                "temp": (chg.split("|")[2] if chg.count("|") >= 2 else ""),
                "status": s(st0.get("status")), "sensor": s(st0.get("sensor")),
                "alarm": s(st0.get("errors")),
            })
        conns = j.get("connections") if isinstance(j.get("connections"), list) else []
        c0 = ad(conns[0]) if conns else {}
        vers = {}
        for v in (j.get("versions") or []):
            p = s(v).split("|")
            if len(p) >= 2:
                key = {"MAIN": "main", "NETWORK": "module", "MCU": "ctrls"}.get(p[0].upper(), p[0].lower())
                vers[key] = p[1]
        setting = ad(j.get("setting"))
        stat = j.get("status")
        meter = {}
        if isinstance(stat, dict) and isinstance(stat.get("eMeter"), list) and stat["eMeter"] and isinstance(stat["eMeter"][0], dict):
            meter = stat["eMeter"][0]
        ds = {
            "sn": s(j.get("sn") or j.get("deviceName")), "slots": slots,
            "adaps": j.get("adaps") if isinstance(j.get("adaps"), list) else [],
            "alarms": ad(j.get("alarms")), "main": c0, "params": setting,
            "acq": {"eMeter": meter, "backupVolt": stat.get("wh") if isinstance(stat, dict) else ""},
            "vers": vers,
        }
        return {"c": j.get("c"), "t": j.get("t"), "ds": ds}

    def gen_cabinet():
        for c in cabs:
            cid = int(c["id"])
            sn = s(c["device_sn"])
            site = site_map.get(int(c["site_id"] or 0), {})
            st = store_agg.get(sn) or {}
            sw = cab_swap.get(cid) or {}
            fl = cab_fail.get(cid) or {}
            up = upl.get(sn) or {}
            raw = up.get("last_upload_data")
            j = jnorm(raw)
            ds = j.get("ds") or {}
            jslots = ds.get("slots") or []
            slots_n = int(st.get("total") or 0) or len(jslots)
            bat_n = int(st.get("bat") or 0) or sum(1 for x in jslots if s((x or {}).get("sn")))
            row = dict.fromkeys(ckeys, "")
            extra = {
                "sn": sn, "id": cid, "name": s(up.get("device_name")) or s(c.get("device_sn")),
                "model": s(c.get("device_type_id")), "series": s(c.get("brand_id")),
                "protocol_version": s(c.get("scheme_version")),
                "slot_total": slots_n, "slot_battery": bat_n,
                "slot_available": ni(st.get("full")), "slot_backable": max(slots_n - bat_n, 0),
                "slot_empty": ni(st.get("none")), "slot_error": ni(st.get("err")),
                "slot_lock": ni(st.get("lock")),
                "online_status": s(c.get("online_status")),
                "voltage": up.get("e_meter_v"), "current": up.get("e_meter_a"),
                "meter_degree": up.get("e_meter_wh") or c.get("meter_value"),
                "site_id": c.get("site_id"), "site_name": s(site.get("name")),
                "agency_id": c.get("agency_id"), "agency_name": agency.get(int(c.get("agency_id") or 0), ""),
                "province": s(site.get("province")), "city": s(site.get("city")),
                "area": s(site.get("area")), "street": s(site.get("street")),
                "community": s(site.get("community")),
                "detail_address": s(c.get("last_location_address")) or s(site.get("union_address")),
                "business_id": site.get("business_id"), "business_name": s(site.get("business_name")),
                "site_contact": s(site.get("contact_person_name")), "site_contact_phone": s(site.get("contact_person_tel")),
                "c_7d": ni(sw.get("c7")), "u_7d": ni(sw.get("u7")),
                "c_30d": ni(sw.get("c30")), "u_30d": ni(sw.get("u30")),
                "c_90d": ni(sw.get("c90")), "u_90d": ni(sw.get("u90")),
                "c_all": ni(sw.get("c_all")),
                "t_last_online": ts(c.get("last_online_time")), "t_last_offline": ts(c.get("last_offline_time")),
                "t_last_upload": ts(c.get("last_upload_time")),
                "smoke": s(up.get("smoke")), "flooded": s(up.get("flooded")),
                "fire_extinguisher": s(up.get("fire")), "csq": s(up.get("csq")),
                "slot_state_desc": "总%d/有电池%d/满电%d/异常%s" % (slots_n, bat_n, int(st.get("full") or 0), int(st.get("err") or 0)),
                "main_soft_ver": s(up.get("main_soft_ver")), "main_hard_ver": s(up.get("main_hard_ver")),
                "detect_soft_ver": s(up.get("acq_soft_ver")), "detect_hard_ver": s(up.get("acq_hard_ver")),
                "slot_total2": slots_n, "slot_battery2": bat_n,
                "slot_available2": ni(st.get("full")), "slot_backable2": max(slots_n - bat_n, 0),
                "slot_empty2": ni(st.get("none")), "slot_lock2": ni(st.get("lock")),
                "slot_error2": ni(st.get("err")),
                "rt_voltage": up.get("e_meter_v"), "rt_current": up.get("e_meter_a"),
                "rt_meter_degree": up.get("e_meter_wh"),
                "backup_power": s(up.get("backup_power")), "backup_voltage": s(up.get("backup_volt")),
                "back_door": s(up.get("back_door")), "smoke2": s(up.get("smoke")),
                "flooded2": s(up.get("flooded")), "fire_extinguisher2": s(up.get("fire")),
                "c_1m": ni(sw.get("c30")), "u_1m": ni(sw.get("u30")),
                "c_3m": ni(sw.get("c90")), "u_3m": ni(sw.get("u90")),
                "u_all": ni(sw.get("u_all")), "c_total": ni(sw.get("c_all")),
                "fail_1m": ni(fl.get("f30")), "fail_all": ni(fl.get("f_all")),
                "bind_info": s(c.get("site_bind_time")) and ts(c.get("site_bind_time")) or "",
                "slot_state_desc2": "", "fee_info": "", "exchange_desc": "",
                "base_command": s(j.get("c")), "t_last_report": ts(c.get("last_upload_time")),
                "device_sn": sn, "device_status": s(c.get("oem_device_status")),
                "net_signal": s(up.get("csq")), "signal_level": s(up.get("csq")),
                "imei": s(up.get("imei")), "iccid": s(up.get("iccid")),
                "sim_platform": "", "sim_flow_used": "", "sim_flow_total": "", "sim_flow_type": "",
                "t_sim_sync": "", "imsi": s(up.get("imsi")),
                "gps_type": jget(j, "ds", "main", "location"), "gps_sat": "", "gps_signal": "",
                "raw_data": s(raw),
                "fan_status": s(up.get("fan")), "pump_status": s(up.get("pump")),
                "board_temp": up.get("temp"),
                "meter_phase_voltage": up.get("e_meter_v"), "meter_phase_current": up.get("e_meter_a"),
                "meter_phase_power": up.get("e_meter_w"), "meter_phase_energy": up.get("e_meter_wh"),
                "slot_temp_high_disarm": jget(j, "ds", "alarms", "slotHighTemp"),
                "slot_temp_high_arm": "", "cell_temp_high_disarm": jget(j, "ds", "alarms", "bmsCellHighTemp"),
                "cell_temp_high_arm": "", "mos_temp_high_disarm": jget(j, "ds", "alarms", "bmsMosHighTemp"),
                "mos_temp_high_arm": "", "total_voltage_disarm": "", "total_voltage_arm": "",
                "cell_voltage_disarm": "", "cell_voltage_arm": "",
                "slot_info": jget(j, "ds", "slots"), "adapter_info": jget(j, "ds", "adaps"),
                "vers": jget(j, "ds", "vers"),
                "comm_soft_ver": s(up.get("module_soft_ver")), "comm_hard_ver": s(up.get("module_hard_ver")),
                "slot_ctl_ver": "", "adapter_ver": "",
                "slot_count_cfg": jget(j, "ds", "params", "slotNum"),
                "back_timeout": jget(j, "ds", "params", "putInTiming"),
                "take_timeout": jget(j, "ds", "params", "takeOutTiming"),
                "attr_report_period": jget(j, "ds", "params", "attrTiming"),
                "alarm_report_period": jget(j, "ds", "params", "alarmTiming"),
                "whole_report_period": jget(j, "ds", "params", "infoTiming"),
                "detect_online_period": jget(j, "ds", "params", "checkTiming"),
                "alarm_switch": jget(j, "ds", "params", "alarm"),
                "log_switch": jget(j, "ds", "params", "mainLog"),
                "lendable_power": jget(j, "ds", "params", "takeOutSoc"),
                "battery_in_cabinet2": bat_n,
                "t_restart": "", "restart_reason": "", "restart_alarm_reason": "", "t_restart_alarm": "",
                "rent_status": jget(j, "ds", "main", "leaseStatus"),
            }
            row.update(extra)
            yield row

    n = batch(sq, "cabinet", gen_cabinet())
    log("  换电柜写入 %d 行" % n)
    sq.commit()

    # ================================================================ 电池
    log("生成【电池】...")
    bkeys = sd.DATA_KEYS["battery"]

    def gen_battery():
        sql = """
        SELECT b.id, b.device_sn, b.device_id, b.type, b.agency_id, b.bike_sn, b.bike_id,
               b.online_status, b.last_online_time, b.last_offline_time,
               b.last_upload_exchange_sn, b.last_take_exchange_sn, b.last_take_time, b.last_back_time,
               b.last_battery_upload_time, b.last_upload_time, b.last_location_address, b.location_type,
               b.lat, b.lng, b.oem_device_status,
               u.power, u.charging, u.discharge, u.cycle, u.voltage, u.current,
               u.cell_temp_max, u.cell_temp_min, u.charging_temp, u.discharge_temp, u.mos_temp,
               u.soh, u.main_s, u.main_h, u.module_s, u.module_h, u.bms_s, u.bms_h,
               u.source_data, u.update_time AS u_update_time, u.battery_sn AS u_sn
        FROM t_battery b
        LEFT JOIN t_battery_last_upload u ON u.battery_id=b.id AND u.is_del=0
        WHERE b.is_del=0
        """
        for r in stream(ac, sql):
            sn = s(r["device_sn"]) or s(r["u_sn"])
            slot = bat_slot.get(sn) or {}
            cab_sn = s(r["last_upload_exchange_sn"]) or s(slot.get("device_sn"))
            cab = cab_by_sn.get(cab_sn, {})
            sid = int(cab.get("site_id") or 0)
            site = site_map.get(sid, {})
            bw = bat_borrow.get(int(r["id"])) or {}
            chg = s(r["charging"])
            row = dict.fromkeys(bkeys, "")
            row.update({
                "sn": sn, "device_id": r.get("device_id"), "model": s(r["type"]),
                "product": "", "power": r.get("power"),
                "online_status": s(r["online_status"]),
                "charge_status": ({"1": "充电中", "0": "未充电"}.get(chg, chg)),
                "discharge_status": ({"1": "放电中", "0": "未放电"}.get(s(r["discharge"]), s(r["discharge"]))),
                "cycle": ni(r.get("cycle")), "voltage": r.get("voltage"), "current": r.get("current"),
                "cell_temp_max": r.get("cell_temp_max"), "cell_temp_min": r.get("cell_temp_min"),
                "charge_temp": r.get("charging_temp"), "discharge_temp": r.get("discharge_temp"),
                "cabinet_sn": cab_sn,
                "province": s(site.get("province")), "city": s(site.get("city")),
                "area": s(site.get("area")), "street": s(site.get("street")),
                "agency_id": r.get("agency_id"), "site_id": sid or "",
                "site_name": s(site.get("name")),
                "slot_name": s(slot.get("number")),
                "slot_type": {"full": "满电", "charging": "充电中", "none": "空仓", "error": "异常",
                              "empty": "空仓"}.get(s(slot.get("status")), s(slot.get("status"))),
                "t_last_flow": ts(max(int(r["last_take_time"] or 0), int(r["last_back_time"] or 0))),
                "t_last_online": ts(r.get("last_online_time")),
                "t_last_offline": ts(r.get("last_offline_time")),
                "t_last_upload": ts(r.get("last_battery_upload_time") or r.get("last_upload_time") or r.get("u_update_time")),
                "last_location": s(r.get("last_location_address")),
                "gps_type": s(r.get("location_type")),
                "borrow_30d": ni(bw.get("c30")), "borrow_90d": ni(bw.get("c90")),
                "soft_ver": s(r.get("main_s")), "hard_ver": s(r.get("main_h")),
                "location_desc": s(r.get("last_location_address")),
            })
            yield row

    n = batch(sq, "battery", gen_battery())
    log("  电池写入 %d 行" % n)

    sq.execute("INSERT OR REPLACE INTO meta VALUES ('sync_time', ?)", (ts(NOW) or "",))
    sq.commit()
    sq.close()
    try:
        log("建立索引与行数缓存 ...")
        from build_index import build as build_indexes
        build_indexes()
    except Exception:
        log("索引建立失败(不影响数据)：%s" % traceback.format_exc().splitlines()[-1])
    log("完成，用时 %.1f 分钟" % ((time.time() - t0) / 60.0))


if __name__ == "__main__":
    main()
