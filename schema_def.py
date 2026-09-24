# -*- coding: utf-8 -*-
"""四大菜单字段定义（对齐《表明细.docx》目标字段清单）

字段规格写法：每行 "key|中文名"，# 开头为分组标题（本身也是一列，占 1 行用 "key|中文名"）。
类型由 key 前缀推导：t_ 时间、f_ 金额(分→元)、n_ 数值、c_ 计数/次数、其余文本。
"""

SPEC = {}

# ============================================================ 用户协议
SPEC["agreement"] = """
# 基础信息
id|协议ID
agreement_type|协议类型
status|协议状态
battery_product_name|电池产品
sale_scenario|销售场景
user_id|用户ID
user_name|签约用户
user_phone|签约手机号
cur_phone|当前手机号
phone_area|手机号归属地
company_id|企业ID
company_name|企业名称
company_admin_phone|企业管理员手机号
bike_count|车辆数量
battery_count|电池数量
rent_remain_days|租期剩余时长(天)
package_price|套餐价格(元)
package_name|租期套餐
# 地理与归属
province|省份
city|城市
area|区域
street|街道
community|社区
site_id|签约网点ID
site_name|签约网点名称
business_id|签约业务员ID
business_name|签约业务员
merchant_id|商户ID
merchant_name|商户名称
merchant_phone|商户手机号
guide_id|导购ID
guide_name|导购姓名
guide_phone|导购手机号
# 押金与渠道
deposit_status|押金状态
deposit_pay_way|押金缴纳方式
deposit_fee|押金金额(元)
deposit_deduct_status|押金划扣状态
agency_id|代理商ID
agency_name|代理商名称
distributor_name|网点渠道商
is_first|是否首次签约
promoter_id|推广员ID
promoter_name|推广员名称
# 时间与状态
t_create_time|创建时间
t_activation_time|激活时间
t_stop_time|终止时间
t_rent_expire_time|到期时间
arrears_days|欠租天数
no_swap_days|距今未换电天数
monthly_swap|月均换电频次
swap_cycle_days|换电周期(天)
# 电池与换电
last_op_type|操作类型
battery_sn|电池SN
battery_power|电池电量
battery_status|电池状态
t_battery_last_time|电池最后流通时间
battery_last_loc|电池最后定位
c_15|c_15|15天换电
c_30|30天换电
c_45|45天换电
c_60|60天换电
is_lowfreq|是否低频
lowfreq_level|档位
# 车辆与优惠券
bike_id|车辆ID
bike_sn|车辆SN
auth_user_count|授权人数
coupon_ids|使用优惠券ID
coupon_names|使用优惠券名称
coupon_fee|使用优惠券金额(元)
# 套餐
first_pkg_id|首次签约套餐ID
first_pkg_name|首次签约套餐名称
first_pkg_fee|首次签约套餐原价(元)
first_pkg_real_fee|首次签约套餐实付价格(元)
last_pkg_id|最后购买套餐ID
last_pkg_name|最后购买套餐名称
last_pkg_fee|最后购买套餐原价(元)
last_pkg_real_fee|最后购买套餐实付价格(元)
cur_pkg_id|当前使用套餐ID
cur_pkg_name|当前使用套餐名称
cur_pkg_fee|当前使用套餐原价(元)
cur_pkg_real_fee|当前使用套餐实付价格(元)
t_pkg_expire_time|当前套餐到期时间
# 累计与违约
relet_count|累计续租次数
relet_fee|累计续租金额(元)
svc_pay_fee|累计服务单支付金额(元)
svc_refund_fee|累计服务单退款金额(元)
coupon_pay_fee|累计优惠券支付金额(元)
violate_count|违约次数
violate_hours|违约合计时长(小时)
violate_fee|违约支付金额(元)
# 其他状态
auto_relet|自动续租状态
is_contract_bike|是否合约车
is_replace|是否置换协议
is_long_term|是否长期协议
battery_org|电池租赁机构
# 最近接待
t_last_reception|最近接待
last_solver|接待人
last_reception_type|接待类型
last_reception_detail|接待内容
"""

# ============================================================ 网点
SPEC["site"] = """
# 基础信息
id|网点ID
name|网点名称
image|网点图片
industry|网点行业
site_type|网点类型
cabinet_status|换电柜状态
exchange_total|换电柜数量
exchange_online|在线换电柜数
exchange_offline|离线换电柜数
battery_total|电池数量(全部)
battery_available|电池数量(可换)
slot_used|电池/仓位(已用)
slot_total|电池/仓位(总数)
agency_id|代理商ID
agency_name|代理商名称
distributor_id|渠道商ID
distributor_name|渠道商名称
merchant_id|商家信息ID
merchant_name|商家信息名称
business_id|业务员ID
business_name|业务员名称
battery_product|电池产品
battery_series|电池系列
site_status|网点状态
address|柜机位置
has_monitor|是否有监控
is_promotion|是否推广
sale_qrcode|售车二维码
independent_meter|独立电表
electric_settle_type|电费结算方式
electric_settle_cycle|电费结算周期
t_last_settle|最近结算时间
# 地理
province|城市(省)
city|城市
area|区域
street|街道
community|社区
detail_address|详细地址
t_create|创建时间
t_open|开业时间
t_close|关闭时间
show_in_app|消费者端显示
income_owner|收益人
income_owner_phone|收益人手机号
cabinet_sn|换电柜sn
# 换电与销售
c_15|15天换电
c_30|30天换电
c_45|45天换电
c_60|60天换电
c_all|全部换电次数
has_exchange|是否换电
has_sale|是否售车
indoor|室内/室外
sign_user_all|累计签约用户数
unsub_user_all|累计退订用户数
sign_user_1m|近1个月签约用户数
unsub_user_1m|近1个月退订用户数
sign_user_3m|近3个月签约用户数
unsub_user_3m|近3个月退订用户数
c_3d|近3天换电次数
c_7d|近7天换电次数
c_1m|近1个月换电次数
c_3m|近3个月换电次数
c_total|总换电数
t_last_exchange|最后一次换电时间
sale_1d|昨日销量
sale_3d|近3天销量
sale_7d|近7天销量
sale_30d|近30天销量
sale_all|全部销量
income_yesterday|网点昨日收益(元)
income_total|网点累计收益(元)
charge_rule|换电计费
merchant_share_total|商户累计分成金额(元)
guide_share_total|导购累计分成金额(元)
# 电费与结算
warn_time|预警时间
electric_price|电费单价
last_settle_degree|最后一次结算度数
t_last_settle2|最近结算时间(电)
t_next_settle|下次结算时间
need_settle|是否要结算电费
settle_cycle|电费结算周期
settle_fee|结算金额(元)
year_place_fee|年度场地费(元)
share_ratio|分成比例
meter_status|独立电表状态
settle_type2|电费结算方式
fee_plan_detail|费用方案明细
# 场地与合同
t_open2|开业时间
battery_product_name|电池产品名称
property_company|物业公司名称
t_cooperate|合作时间
contract_period|合同期限
pay_account|收款账户信息
cabinet_type|换电柜类型
service_price|服务费单价(元)
place_deposit|场地/电费押金(元)
total_fee|总金额(元)
cabinet_offline_cnt|换电柜离线数量
cabinet_status2|换电柜状态
income_item|收入项
charge_standard|换电收费标准
c_total2|总换电数
battery_in_cabinet|柜内电池数量
c_3m2|近3个月换电次数
c_1m2|近1个月换电次数
c_7d2|近7天换电次数
c_3d2|近3天换电次数
has_exchange2|是否换电
has_sale2|是否售车
indoor2|室内/室外
is_24h|是否24小时
sign_user_all2|累计签约用户数
unsub_user_all2|累计退订用户数
sign_user_1m2|近1个月签约用户数
unsub_user_1m2|近1个月退订用户数
sign_user_3m2|近3个月签约用户数
unsub_user_3m2|近3个月退订用户数
t_last_exchange2|最后一次换电时间
meter_degree_now|柜机当前度数
power_consume|耗电量
order_count|订单笔数
order_fee|订单金额(元)
"""

# ============================================================ 换电柜
SPEC["cabinet"] = """
# 基础信息
sn|换电柜SN
id|换电柜ID
name|换电柜名称
model|换电柜型号
series|换电柜系列
protocol_version|协议版本
slot_total|总仓位
slot_battery|有电池
slot_available|可换
slot_backable|可还
slot_empty|空仓
slot_error|故障仓
slot_lock|锁仓
online_status|在线状态
voltage|电压
current|电流
meter_degree|电表度数
site_id|归属网点ID
site_name|归属网点
agency_id|归属代理商ID
agency_name|归属代理商
province|城市(省)
city|城市
area|区
street|街道
community|社区
detail_address|详细地址
business_id|业务员ID
business_name|业务员
site_contact|网点联系人
site_contact_phone|联系人电话
# 换电统计
c_7d|7天换电次数
u_7d|7天换电用户数
c_30d|30天换电次数
u_30d|30天换电用户数
c_90d|90天换电次数
u_90d|90天换电用户数
c_all|全部换电次数
t_last_online|最后上线
t_last_offline|最后离线
t_last_upload|最新上报时间
smoke|烟感
flooded|水浸
fire_extinguisher|灭火器
csq|信号值
slot_state_desc|仓位状态
main_soft_ver|主控软件版本
main_hard_ver|主控硬件版本
detect_soft_ver|检测板软件版本
detect_hard_ver|检测板硬件版本
# 实时状态
slot_total2|总仓位数
slot_battery2|有电池仓位数
slot_available2|可换仓位数
slot_backable2|可还仓位数
slot_empty2|空仓仓位数
slot_lock2|锁仓仓位数
slot_error2|充电异常仓位数
rt_voltage|实时电压
rt_current|实时电流
rt_meter_degree|电表度数
backup_power|备电状态
backup_voltage|备电电压
back_door|后仓门状态
smoke2|烟感检测
flooded2|水浸检测
fire_extinguisher2|灭火器
c_1m|近1个月换电次数
u_1m|近1个月换电用户数
c_3m|近3个月换电次数
u_3m|近3个月换电用户数
u_all|累计换电用户数
c_total|累计换电次数
fail_1m|近1个月换电失败订单数
fail_all|累计换电失败订单数
bind_info|绑定信息
slot_state_desc2|仓位状态(明细)
fee_info|电费信息
exchange_desc|换电数据
# 设备上报（协议）
base_command|baseCommand
t_last_report|最后上报时间
device_sn|设备SN
device_status|设备状态
net_signal|网络信号强度
signal_level|信号强度等级
imei|国际移动设备识别码
iccid|SIM卡卡号
sim_platform|SIM卡平台
sim_flow_used|SIM卡当月流量已用(M)
sim_flow_total|SIM卡当月流量总量(M)
sim_flow_type|SIM卡当月流量类型
t_sim_sync|SIM卡同步时间
imsi|国际移动用户识别码
gps_type|定位类型
gps_sat|定位卫星
gps_signal|定位信号
raw_data|检测原始数据
fan_status|风扇状态
pump_status|水泵状态
board_temp|检测板温度
meter_phase_voltage|电表相电压
meter_phase_current|电表相电流
meter_phase_power|电表相总功率
meter_phase_energy|电表相总电能
slot_temp_high_disarm|仓位高温(撤防值)
slot_temp_high_arm|仓位高温(设防值)
cell_temp_high_disarm|电芯高温(撤防值)
cell_temp_high_arm|电芯高温(设防值)
mos_temp_high_disarm|MOS高温(撤防值)
mos_temp_high_arm|MOS高温(设防值)
total_voltage_disarm|总电压(撤防值)
total_voltage_arm|总电压(设防值)
cell_voltage_disarm|单体电压(撤防值)
cell_voltage_arm|单体电压(设防值)
slot_info|仓位信息
adapter_info|适配器信息
vers|vers
comm_soft_ver|通讯模块软件版本
comm_hard_ver|通讯模块硬件版本
slot_ctl_ver|仓控板版本
adapter_ver|适配器版本
slot_count_cfg|仓位数量
back_timeout|归还电池超时时间
take_timeout|取出电池超时时间
attr_report_period|属性上报周期
alarm_report_period|报警上报周期
whole_report_period|整机上报周期
detect_online_period|检测设备在线周期
alarm_switch|报警开关
log_switch|日志开关
lendable_power|可借电量
battery_in_cabinet2|柜中电池数量
t_restart|重启时间
restart_reason|重启原因
restart_alarm_reason|重启的告警原因
t_restart_alarm|重启的告警时间
rent_status|租借状态
"""

# ============================================================ 电池
SPEC["battery"] = """
# 基础信息
sn|电池SN
device_id|设备ID
model|型号
product|电池产品
power|电量
online_status|网络状态
charge_status|充电状态
discharge_status|放电状态
cycle|循环次数
voltage|电压
current|电流
cell_temp_max|BMS最高温
cell_temp_min|BMS最低温
charge_temp|充电口温度
discharge_temp|放电口温度
cabinet_sn|所属柜SN
province|城市(省)
city|城市
area|区
street|街道
agency_id|代理商ID
site_id|网点ID
site_name|网点
slot_name|仓位名
slot_type|仓位类型
t_last_flow|最后流通
t_last_online|最后上线
t_last_offline|最后离线
t_last_upload|最后上报
last_location|最后定位
gps_type|定位类型
borrow_30d|30天借出
borrow_90d|90天借出
soft_ver|软件版本
hard_ver|硬件版本
location_desc|当前位置
"""


def parse(spec_text):
    cols = []
    for raw in spec_text.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            cols.append({"k": "__group__" + str(len(cols)), "n": line.lstrip("# ").strip(),
                         "g": "group", "t": "group"})
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            k, key, name = parts[0], parts[1], parts[2]
            k = key
        else:
            k, name = parts[0], parts[1]
        k = k.strip()
        t = "text"
        if k.startswith("t_"):
            t = "time"
        elif k.startswith("f_"):
            t = "money"
        elif k.startswith("c_"):
            t = "int"
        elif k.startswith("n_"):
            t = "num"
        cols.append({"k": k, "n": name.strip(), "g": "data", "t": t})
    return cols


COLUMNS = {menu: parse(txt) for menu, txt in SPEC.items()}
DATA_KEYS = {menu: [c["k"] for c in cols if c["t"] != "group"] for menu, cols in COLUMNS.items()}

MENU_TITLE = {"agreement": "用户协议", "site": "网点", "cabinet": "换电柜", "battery": "电池"}
