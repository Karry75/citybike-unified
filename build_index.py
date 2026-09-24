# -*- coding: utf-8 -*-
"""为看板库建立索引与行数缓存（sync.py 结束时会自动调用，也可单独运行）。

用法: python build_index.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import log, sqlite_conn
import schema_def as sd

IDX_COLS = {
    "agreement": ["is_lowfreq", "lowfreq_level", "city", "site_name", "agency_name",
                  "agreement_type", "status", "merchant_name", "user_phone", "id", "battery_sn"],
    "site": ["city", "site_type", "site_status", "agency_name", "merchant_name", "name", "id", "area"],
    "cabinet": ["online_status", "device_status", "city", "site_name", "agency_name", "sn", "id"],
    "battery": ["online_status", "charge_status", "discharge_status", "city", "site_name",
                "sn", "model", "product", "slot_type"],
}


def build():
    t0 = time.time()
    sq = sqlite_conn()
    for menu, cols in IDX_COLS.items():
        keys = set(sd.DATA_KEYS[menu])
        for c in cols:
            if c not in keys:
                continue
            name = "idx_%s_%s" % (menu, c)
            sq.execute('CREATE INDEX IF NOT EXISTS %s ON %s("%s")' % (name, menu, c))
        log("  索引 %s 完成 (%d 列)" % (menu, len(cols)))
    sq.commit()
    for menu in sd.DATA_KEYS:
        n = sq.execute("SELECT COUNT(*) FROM %s" % menu).fetchone()[0]
        sq.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("count_" + menu, str(n)))
        log("  行数缓存 %s = %d" % (menu, n))
    sq.execute("INSERT OR REPLACE INTO meta VALUES ('index_time', ?)",
               (time.strftime("%Y-%m-%d %H:%M:%S"),))
    sq.commit()
    sq.close()
    log("索引与缓存完成，用时 %.1f 秒" % (time.time() - t0))


if __name__ == "__main__":
    build()
