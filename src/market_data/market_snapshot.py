"""
OptionSeller - 标准化行情快照 V2

本模块目前只负责：

1. 获取期权 Greeks
2. 获取期权行情
3. 获取期权对应的标的行情
4. 标准化行情字段
5. 检查数据质量
6. 检查行情时效性
7. 检查期权盘口和流动性
8. 分析期货价格与持仓量的关系

注意：
本模块暂时不负责：
- 下单
- 保证金计算
- 策略判断
- 是否真正卖出期权

它只是整个量化系统的“数据基础层”。

作者说明：
后续策略模块应该尽量只读取本模块产生的标准化数据，
不要自己重复从 TqSdk 读取行情。
"""

import math
import os
import time
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


# ============================================================
# 一、测试用期权合约
# ============================================================

TEST_OPTION_SYMBOLS = [
    "CFFEX.HO2610-C-2500",
    "DCE.m2611-P-2700",
    "SHFE.ad2611C20400",
    "INE.bc2611C100000",
    "GFEX.lc2611-C-100000",
]


# ============================================================
# 二、基础工具函数
# ============================================================

def is_valid_number(value):
    """
    判断一个值是不是有效的数字。

    注意：
    - None      -> False
    - NaN       -> False
    - inf       -> False
    - -inf      -> False
    - 正常数字   -> True

    后面的数据质量检查大量依赖这个函数。
    """

    if value is None:
        return False

    try:
        value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(value)


def get_value(row, field: str, default=None):
    """
    从 TqSdk 行情对象或者 pandas Series 中安全读取字段。

    为什么要专门写这个函数？

    因为：
    - TqSdk 的 get_quote() 返回的是 Entity 对象
    - query_option_greeks() 返回的是 pandas DataFrame / Series

    两种对象的读取方式并不完全一样。

    因此统一通过这个函数读取，避免后面到处写各种判断。
    """

    try:
        # ----------------------------------------------------
        # 情况1：pandas Series
        # ----------------------------------------------------
        if isinstance(row, pd.Series):

            if field not in row.index:
                return default

            value = row[field]

        # ----------------------------------------------------
        # 情况2：TqSdk Entity
        # ----------------------------------------------------
        else:

            try:
                value = row[field]

            except (KeyError, TypeError, AttributeError):

                value = getattr(row, field, default)

        # ----------------------------------------------------
        # 如果是 pandas 的 NaN / NaT，则返回默认值
        # ----------------------------------------------------
        try:
            if pd.isna(value):
                return default
        except (TypeError, ValueError):
            pass

        return value

    except Exception:
        return default


def safe_float(value, default=None):
    """
    尝试把数据转换成 float。

    转换失败或者数据无效时返回 default。
    """

    if not is_valid_number(value):
        return default

    return float(value)


# ============================================================
# 三、期权盘口计算
# ============================================================

def calculate_mid_price(bid_price, ask_price):
    """
    计算买卖价中间价。

    Mid = (Bid + Ask) / 2

    只有 Bid 和 Ask 都有效，并且 > 0 时才计算。
    """

    if not is_valid_number(bid_price):
        return None

    if not is_valid_number(ask_price):
        return None

    if bid_price <= 0 or ask_price <= 0:
        return None

    if ask_price < bid_price:
        return None

    return (bid_price + ask_price) / 2


def calculate_spread(bid_price, ask_price):
    """
    计算绝对买卖价差。

    Spread = Ask - Bid
    """

    if not is_valid_number(bid_price):
        return None

    if not is_valid_number(ask_price):
        return None

    if ask_price < bid_price:
        return None

    return ask_price - bid_price


def calculate_spread_ratio(bid_price, ask_price):
    """
    计算买卖价差比例。

    Spread Ratio = (Ask - Bid) / Mid

    例如：

    Bid = 100
    Ask = 102

    Mid = 101

    Spread Ratio = 2 / 101 ≈ 1.98%
    """

    mid_price = calculate_mid_price(bid_price, ask_price)

    if mid_price is None:
        return None

    spread = ask_price - bid_price

    return spread / mid_price


# ============================================================
# 四、Greeks 数据质量检查
# ============================================================

def check_greeks(greeks_row):
    """
    检查 Greeks 是否完整以及基础数值是否合理。

    返回：

    {
        "greeks_valid": True / False,
        "greeks_reason": [...]
    }

    注意：

    这里只做“数据质量检查”。

    不会因为 Delta 很高就认为风险高，
    也不会因为 Theta 很低就认为适合卖出。

    那些属于策略层。
    """

    reasons = []

    delta = get_value(greeks_row, "delta")
    gamma = get_value(greeks_row, "gamma")
    theta = get_value(greeks_row, "theta")
    vega = get_value(greeks_row, "vega")
    rho = get_value(greeks_row, "rho")

    # --------------------------------------------------------
    # 1. 五个 Greeks 必须全部存在
    # --------------------------------------------------------

    greeks = {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
    }

    for name, value in greeks.items():

        if not is_valid_number(value):
            reasons.append(f"{name} 为 NaN 或无效值")

    # 如果已经存在缺失，后面的范围检查没有必要继续。
    if reasons:
        return False, reasons

    # --------------------------------------------------------
    # 2. Delta 基础合理性
    # --------------------------------------------------------

    option_class = str(
        get_value(greeks_row, "option_class", "")
    ).upper()

    if option_class == "CALL":

        if not 0 <= delta <= 1:
            reasons.append(
                f"CALL Delta 超出正常范围：{delta}"
            )

    elif option_class == "PUT":

        if not -1 <= delta <= 0:
            reasons.append(
                f"PUT Delta 超出正常范围：{delta}"
            )

    # --------------------------------------------------------
    # 3. Gamma 基础检查
    # --------------------------------------------------------

    if gamma < 0:
        reasons.append(
            f"Gamma 出现负值：{gamma}"
        )

    # --------------------------------------------------------
    # 4. Vega 基础检查
    # --------------------------------------------------------

    if vega < 0:
        reasons.append(
            f"Vega 出现负值：{vega}"
        )

    # --------------------------------------------------------
    # 最终结果
    # --------------------------------------------------------

    return len(reasons) == 0, reasons


# ============================================================
# 五、期权盘口 / 流动性检查
# ============================================================

def check_option_liquidity(
    last_price,
    bid_price,
    ask_price,
    volume,
    open_interest,
):
    """
    检查期权基本流动性。

    注意：
    这里暂时不设最终的“严格交易阈值”。

    例如我们暂时不会写死：

        volume >= 100
        OI >= 500
        spread_ratio <= 5%

    原因是：

    不同品种的正常流动性差异非常大。

    我们后面需要先收集数据，再统计不同品种的分布。

    目前这里只做基础判断。
    """

    reasons = []

    # --------------------------------------------------------
    # 1. Bid / Ask
    # --------------------------------------------------------

    has_bid = (
        is_valid_number(bid_price)
        and bid_price > 0
    )

    has_ask = (
        is_valid_number(ask_price)
        and ask_price > 0
    )

    if not has_bid or not has_ask:

        reasons.append("缺少完整买卖盘口")

    # --------------------------------------------------------
    # 2. Bid <= Ask
    # --------------------------------------------------------

    if has_bid and has_ask:

        if ask_price < bid_price:

            reasons.append(
                f"盘口异常：Ask({ask_price}) < Bid({bid_price})"
            )

    # --------------------------------------------------------
    # 3. Last Price
    # --------------------------------------------------------

    if is_valid_number(last_price):

        if last_price < 0:

            reasons.append(
                f"最新价出现负值：{last_price}"
            )

    # --------------------------------------------------------
    # 4. Volume
    # --------------------------------------------------------

    has_volume = (
        is_valid_number(volume)
        and volume > 0
    )

    if not has_volume:

        reasons.append("成交量为0")

    # --------------------------------------------------------
    # 5. Open Interest
    # --------------------------------------------------------

    has_open_interest = (
        is_valid_number(open_interest)
        and open_interest > 0
    )

    if not has_open_interest:

        reasons.append("持仓量为0")

    # --------------------------------------------------------
    # 6. Spread
    # --------------------------------------------------------

    spread = calculate_spread(
        bid_price,
        ask_price
    )

    mid_price = calculate_mid_price(
        bid_price,
        ask_price
    )

    spread_ratio = calculate_spread_ratio(
        bid_price,
        ask_price
    )

    return {
        "has_quote": has_bid and has_ask,
        "has_volume": has_volume,
        "has_open_interest": has_open_interest,

        "mid_price": mid_price,
        "spread": spread,
        "spread_ratio": spread_ratio,

        "liquidity_reasons": reasons,
    }


# ============================================================
# 六、行情时效性检查
# ============================================================

def check_quote_freshness(
    quote_datetime,
    max_age_seconds=30,
):
    """
    检查行情时间。

    注意：

    这里的 max_age_seconds 只是一个基础参考值，
    不是最终交易阈值。

    真正的策略系统还应该结合：
    - 当前是否交易时间
    - 交易所交易时段
    - 是否收盘
    - 是否节假日

    当前阶段先把“行情时间”完整记录下来。
    """

    if quote_datetime is None:

        return {
            "quote_age_seconds": None,
            "quote_fresh": False,
            "quote_fresh_reason": "缺少行情时间",
        }

    try:

        # TqSdk 的 datetime 通常是 datetime 对象
        if isinstance(quote_datetime, datetime):

            now = datetime.now(
                tz=quote_datetime.tzinfo
            )

            age_seconds = (
                now - quote_datetime
            ).total_seconds()

        else:

            # 如果不是 datetime，则尝试 pandas 转换
            quote_time = pd.to_datetime(
                quote_datetime
            )

            now = pd.Timestamp.now(
                tz=quote_time.tz
            )

            age_seconds = (
                now - quote_time
            ).total_seconds()

        # ----------------------------------------------------
        # 如果行情时间比当前时间还晚
        # ----------------------------------------------------

        if age_seconds < 0:

            return {
                "quote_age_seconds": age_seconds,
                "quote_fresh": False,
                "quote_fresh_reason": "行情时间晚于当前时间，时间异常",
            }

        # ----------------------------------------------------
        # 判断是否超过基础阈值
        # ----------------------------------------------------

        is_fresh = (
            age_seconds <= max_age_seconds
        )

        return {
            "quote_age_seconds": age_seconds,
            "quote_fresh": is_fresh,
            "quote_fresh_reason": (
                "行情时间在基础允许范围内"
                if is_fresh
                else f"行情已经过期 {age_seconds:.0f} 秒"
            ),
        }

    except Exception as e:

        return {
            "quote_age_seconds": None,
            "quote_fresh": False,
            "quote_fresh_reason": f"无法解析行情时间：{e}",
        }


# ============================================================
# 七、期货 Price / Open Interest 分析
# ============================================================

def analyze_price_open_interest(quote):
    """
    分析期货价格变化和持仓量变化之间的关系。

    当前版本使用：

        当前价格 vs 前收盘价
        当前持仓量 vs 前持仓量

    因此得到的是：

        “相对于上一交易时段”的 Price/OI 状态。

    注意：

    这不是“多空绝对判断”。

    例如：

        价格上涨 + OI下降

    我们只标记：

        PRICE_UP_OI_DOWN

    不直接说：

        “空头回补”

    因为仅凭总持仓量无法确定具体是哪一方在平仓。

    --------------------------------------------------------
    四种基础状态
    --------------------------------------------------------

    价格上涨 + OI上涨
        PRICE_UP_OI_UP

    价格上涨 + OI下降
        PRICE_UP_OI_DOWN

    价格下跌 + OI上涨
        PRICE_DOWN_OI_UP

    价格下跌 + OI下降
        PRICE_DOWN_OI_DOWN

    另外还会存在：

        PRICE_FLAT
        OI_FLAT
        DATA_UNAVAILABLE
    """

    last_price = safe_float(
        get_value(quote, "last_price")
    )

    pre_close = safe_float(
        get_value(quote, "pre_close")
    )

    open_interest = safe_float(
        get_value(quote, "open_interest")
    )
    ins_class = str(get_value(quote, "ins_class", "")).upper()
    if ins_class == "INDEX":
        # 指数没有持仓量概念，Price/OI 象限不适用
        return {
            "underlying_last_price": safe_float(get_value(quote, "last_price")),
            "underlying_pre_close": safe_float(get_value(quote, "pre_close")),
            "underlying_price_change": None,
            "underlying_price_change_pct": None,
            "underlying_open_interest": None,
            "underlying_pre_open_interest": None,
            "underlying_oi_change": None,
            "underlying_oi_change_pct": None,
            "price_direction": "UNKNOWN",
            "oi_direction": "UNKNOWN",
            "price_oi_state": "OI_NOT_APPLICABLE",
        }
    pre_open_interest = safe_float(
        get_value(quote, "pre_open_interest")
    )

    # --------------------------------------------------------
    # 计算价格变化
    # --------------------------------------------------------

    if (
        last_price is not None
        and pre_close is not None
    ):

        price_change = (
            last_price - pre_close
        )

        if pre_close != 0:

            price_change_pct = (
                price_change / pre_close
            )

        else:

            price_change_pct = None

    else:

        price_change = None
        price_change_pct = None

    # --------------------------------------------------------
    # 计算持仓变化
    # --------------------------------------------------------

    if (
        open_interest is not None
        and pre_open_interest is not None
    ):

        oi_change = (
            open_interest - pre_open_interest
        )

        if pre_open_interest != 0:

            oi_change_pct = (
                oi_change / pre_open_interest
            )

        else:

            oi_change_pct = None

    else:

        oi_change = None
        oi_change_pct = None

    # --------------------------------------------------------
    # 判断价格方向
    # --------------------------------------------------------

    if price_change is None:

        price_direction = "UNKNOWN"

    elif price_change > 0:

        price_direction = "UP"

    elif price_change < 0:

        price_direction = "DOWN"

    else:

        price_direction = "FLAT"

    # --------------------------------------------------------
    # 判断持仓方向
    # --------------------------------------------------------

    if oi_change is None:

        oi_direction = "UNKNOWN"

    elif oi_change > 0:

        oi_direction = "UP"

    elif oi_change < 0:

        oi_direction = "DOWN"

    else:

        oi_direction = "FLAT"

    # --------------------------------------------------------
    # Price/OI 四象限
    # --------------------------------------------------------

    if (
        price_direction == "UP"
        and oi_direction == "UP"
    ):

        price_oi_state = "PRICE_UP_OI_UP"

    elif (
        price_direction == "UP"
        and oi_direction == "DOWN"
    ):

        price_oi_state = "PRICE_UP_OI_DOWN"

    elif (
        price_direction == "DOWN"
        and oi_direction == "UP"
    ):

        price_oi_state = "PRICE_DOWN_OI_UP"

    elif (
        price_direction == "DOWN"
        and oi_direction == "DOWN"
    ):

        price_oi_state = "PRICE_DOWN_OI_DOWN"

    elif (
        price_direction == "FLAT"
        and oi_direction == "UP"
    ):

        price_oi_state = "PRICE_FLAT_OI_UP"

    elif (
        price_direction == "FLAT"
        and oi_direction == "DOWN"
    ):

        price_oi_state = "PRICE_FLAT_OI_DOWN"

    elif (
        price_direction == "UP"
        and oi_direction == "FLAT"
    ):

        price_oi_state = "PRICE_UP_OI_FLAT"

    elif (
        price_direction == "DOWN"
        and oi_direction == "FLAT"
    ):

        price_oi_state = "PRICE_DOWN_OI_FLAT"

    elif (
        price_direction == "FLAT"
        and oi_direction == "FLAT"
    ):

        price_oi_state = "PRICE_FLAT_OI_FLAT"

    else:

        price_oi_state = "DATA_UNAVAILABLE"

    return {
        "underlying_last_price": last_price,
        "underlying_pre_close": pre_close,

        "underlying_price_change": price_change,
        "underlying_price_change_pct": price_change_pct,

        "underlying_open_interest": open_interest,
        "underlying_pre_open_interest": pre_open_interest,

        "underlying_oi_change": oi_change,
        "underlying_oi_change_pct": oi_change_pct,

        "price_direction": price_direction,
        "oi_direction": oi_direction,
        "price_oi_state": price_oi_state,
    }


# ============================================================
# 八、建立单个期权标准化快照
# ============================================================

def build_option_snapshot(
    option_symbol,
    greeks_row,
    option_quote,
    underlying_quote,
):
    """
    把：

        期权合约信息
        +
        期权行情
        +
        Greeks
        +
        标的行情
        +
        Price/OI

    统一转换成一条标准化记录。
    """

    # ========================================================
    # 1. 基础信息
    # ========================================================
    print(option_symbol, "bid1=", get_value(option_quote, "bid_price1"),
          "ask1=", get_value(option_quote, "ask_price1"))
    option_class = get_value(
        greeks_row,
        "option_class"
    )

    underlying_symbol = get_value(
        greeks_row,
        "underlying_symbol"
    )

    strike_price = safe_float(
        get_value(greeks_row, "strike_price")
    )

    expire_rest_days = safe_float(
        get_value(greeks_row, "expire_rest_days")
    )

    expire_datetime = get_value(
        greeks_row,
        "expire_datetime"
    )

    # ========================================================
    # 2. 期权行情
    # ========================================================

    last_price = safe_float(
        get_value(option_quote, "last_price")
    )

    bid_price = safe_float(
        get_value(option_quote, "bid_price1")
    )

    ask_price = safe_float(
        get_value(option_quote, "ask_price1")
    )

    volume = safe_float(
        get_value(option_quote, "volume")
    )

    open_interest = safe_float(
        get_value(option_quote, "open_interest")
    )

    quote_datetime = get_value(
        option_quote,
        "datetime"
    )

    # ========================================================
    # 3. Greeks
    # ========================================================

    delta = safe_float(
        get_value(greeks_row, "delta")
    )

    gamma = safe_float(
        get_value(greeks_row, "gamma")
    )

    theta = safe_float(
        get_value(greeks_row, "theta")
    )

    vega = safe_float(
        get_value(greeks_row, "vega")
    )

    rho = safe_float(
        get_value(greeks_row, "rho")
    )

    greeks_valid, greeks_reasons = check_greeks(
        greeks_row
    )

    # ========================================================
    # 4. 流动性
    # ========================================================

    liquidity = check_option_liquidity(
        last_price=last_price,
        bid_price=bid_price,
        ask_price=ask_price,
        volume=volume,
        open_interest=open_interest,
    )

    # ========================================================
    # 5. 行情时效
    # ========================================================

    freshness = check_quote_freshness(
        quote_datetime
    )

    # ========================================================
    # 6. 标的行情
    # ========================================================

    underlying_last_price = safe_float(
        get_value(
            underlying_quote,
            "last_price"
        )
    )

    underlying_quote_datetime = get_value(
        underlying_quote,
        "datetime"
    )

    underlying_freshness = check_quote_freshness(
        underlying_quote_datetime
    )

    underlying_price_oi = (
        analyze_price_open_interest(
            underlying_quote
        )
    )

    # ========================================================
    # 7. 合约有效性
    # ========================================================

    contract_valid = True
    contract_reasons = []

    if strike_price is None or strike_price <= 0:

        contract_valid = False
        contract_reasons.append(
            "执行价无效"
        )

    if expire_rest_days is None:

        contract_valid = False
        contract_reasons.append(
            "缺少剩余到期日"
        )

    elif expire_rest_days < 0:

        contract_valid = False
        contract_reasons.append(
            "合约已经到期"
        )

    # ========================================================
    # 8. 标的行情有效性
    # ========================================================

    underlying_valid = (
        underlying_last_price is not None
    )

    underlying_reasons = []

    if not underlying_valid:

        underlying_reasons.append(
            "标的最新价无效"
        )

    # ========================================================
    # 9. 最终基础数据有效性
    # ========================================================

    data_valid = (
        contract_valid
        and greeks_valid
        and underlying_valid
    )

    data_reasons = []

    data_reasons.extend(
        contract_reasons
    )

    data_reasons.extend(
        greeks_reasons
    )

    data_reasons.extend(
        underlying_reasons
    )

    # ========================================================
    # 10. 交易候选状态
    # ========================================================

    # 注意：
    #
    # 这里暂时没有使用严格的流动性阈值。
    #
    # 只是要求：
    #
    # - 基础数据完整
    # - 盘口完整
    # - 有成交量
    # - 有持仓量
    #
    # 后面我们统计不同品种的数据分布后，
    # 再正式建立 liquidity_score / liquidity_filter。

    liquidity_valid = (
        liquidity["has_quote"]
        and liquidity["has_volume"]
        and liquidity["has_open_interest"]
    )

    tradeable = (
        data_valid
        and liquidity_valid
    )

    trade_reasons = []

    if not data_valid:
        trade_reasons.extend(
            data_reasons
        )

    if not liquidity_valid:
        trade_reasons.extend(
            liquidity["liquidity_reasons"]
        )

    # 去重，保持原来的顺序
    trade_reasons = list(
        dict.fromkeys(trade_reasons)
    )

    # ========================================================
    # 11. 返回标准化记录
    # ========================================================

    return {
        # ----------------------------------------------------
        # 合约
        # ----------------------------------------------------
        "option_symbol": option_symbol,
        "option_class": option_class,
        "underlying_symbol": underlying_symbol,
        "strike_price": strike_price,
        "expire_rest_days": expire_rest_days,
        "expire_datetime": expire_datetime,

        # ----------------------------------------------------
        # 期权行情
        # ----------------------------------------------------
        "option_last_price": last_price,
        "option_bid_price": bid_price,
        "option_ask_price": ask_price,

        "option_mid_price": liquidity["mid_price"],
        "option_spread": liquidity["spread"],
        "option_spread_ratio": liquidity["spread_ratio"],

        "option_volume": volume,
        "option_open_interest": open_interest,

        # ----------------------------------------------------
        # Greeks
        # ----------------------------------------------------
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,

        "greeks_valid": greeks_valid,

        # ----------------------------------------------------
        # 期权行情时间
        # ----------------------------------------------------
        "quote_datetime": quote_datetime,
        "quote_age_seconds": freshness[
            "quote_age_seconds"
        ],
        "quote_fresh": freshness[
            "quote_fresh"
        ],

        # ----------------------------------------------------
        # 标的行情
        # ----------------------------------------------------
        "underlying_last_price":
            underlying_last_price,

        "underlying_quote_datetime":
            underlying_quote_datetime,

        "underlying_quote_age_seconds":
            underlying_freshness[
                "quote_age_seconds"
            ],

        "underlying_quote_fresh":
            underlying_freshness[
                "quote_fresh"
            ],

        "underlying_valid":
            underlying_valid,

        # ----------------------------------------------------
        # 标的 Price/OI
        # ----------------------------------------------------
        **underlying_price_oi,

        # ----------------------------------------------------
        # 数据质量
        # ----------------------------------------------------
        "contract_valid":
            contract_valid,

        "data_valid":
            data_valid,

        "liquidity_valid":
            liquidity_valid,

        "tradeable":
            tradeable,

        # ----------------------------------------------------
        # 原因
        # ----------------------------------------------------
        "data_reasons":
            data_reasons,

        "liquidity_reasons":
            liquidity[
                "liquidity_reasons"
            ],

        "trade_reasons":
            trade_reasons,
    }


# ============================================================
# 九、主程序
# ============================================================

def main():

    print("=" * 70)
    print("OptionSeller - 标准化行情快照 V2")
    print("=" * 70)

    # ========================================================
    # 1. 读取 TqSdk 登录配置
    # ========================================================

    print("\n正在读取 TqSdk 登录配置...")

    load_dotenv()

    username = os.getenv(
        "TQ_USERNAME"
    )

    password = os.getenv(
        "TQ_PASSWORD"
    )

    if not username or not password:

        raise RuntimeError(
            "没有读取到 TQ_USERNAME / TQ_PASSWORD，"
            "请检查项目根目录下的 .env 文件。"
        )

    print("✅ 已成功读取 TqSdk 登录配置。")

    # ========================================================
    # 2. 创建 API
    # ========================================================

    print("\n" + "=" * 70)
    print("正在连接天勤量化...")
    print("=" * 70)

    auth = TqAuth(
        username,
        password
    )

    api = TqApi(
        auth=auth
    )

    print("✅ TqSdk API 创建成功。")

    try:

        # ====================================================
        # 3. 获取 Greeks
        # ====================================================

        print("\n" + "=" * 70)
        print("正在获取 Greeks...")
        print("=" * 70)

        greeks_df = api.query_option_greeks(
            TEST_OPTION_SYMBOLS,
            v=None,
            r=0.025
        )

        print(
            f"✅ Greeks 获取完成，共 {len(greeks_df)} 条。"
        )

        # ====================================================
        # 4. 获取对应标的
        # ====================================================

        underlying_symbols = (
            greeks_df["underlying_symbol"]
            .dropna()
            .unique()
            .tolist()
        )

        print("\n对应的标的：")

        for symbol in underlying_symbols:

            print(f"  {symbol}")

        # ====================================================
        # 5. 订阅行情
        # ====================================================

        print("\n" + "=" * 70)
        print("正在订阅期权 + 标的行情...")
        print("=" * 70)

        quote_objects = {}

        all_symbols = (
            TEST_OPTION_SYMBOLS
            + underlying_symbols
        )

        for symbol in all_symbols:

            quote_objects[symbol] = (
                api.get_quote(symbol)
            )

            print(
                f"  ✅ 已订阅：{symbol}"
            )

        # ====================================================
        # 6. 等待行情
        # ====================================================

        print("\n正在等待行情数据...")
        print(
            "TqSdk 会自动更新已订阅的行情。"
        )
        print("=" * 70)

        # ----------------------------------------------------
        # 重要：
        #
        # wait_update 的 deadline 是“绝对时间点”，
        # 不是等待秒数。
        #
        # 所以必须：
        #
        # time.time() + 10
        #
        # 而不是：
        #
        # deadline=10
        # ----------------------------------------------------

        deadline = (
            time.time() + 10
        )

        updated = api.wait_update(
            deadline=deadline
        )

        if updated:

            print(
                "✅ 收到行情更新。"
            )

        else:

            print(
                "⚠️ 10 秒内没有收到新的行情更新。"
            )

            print(
                "   当前可能处于非交易时间，"
                "将继续读取 TqSdk 当前缓存的行情快照。"
            )

        # ====================================================
        # 7. 构建标准化快照
        # ====================================================

        snapshots = []

        for option_symbol in TEST_OPTION_SYMBOLS:

            # -----------------------------------------------
            # 找到对应 Greeks
            # -----------------------------------------------

            matched_rows = greeks_df[
                greeks_df["instrument_id"]
                == option_symbol
            ]

            if matched_rows.empty:

                print(
                    f"⚠️ 找不到 Greeks："
                    f"{option_symbol}"
                )

                continue

            greeks_row = (
                matched_rows.iloc[0]
            )

            underlying_symbol = (
                get_value(
                    greeks_row,
                    "underlying_symbol"
                )
            )

            option_quote = (
                quote_objects[
                    option_symbol
                ]
            )

            underlying_quote = (
                quote_objects[
                    underlying_symbol
                ]
            )

            snapshot = build_option_snapshot(
                option_symbol=option_symbol,
                greeks_row=greeks_row,
                option_quote=option_quote,
                underlying_quote=underlying_quote,
            )

            snapshots.append(
                snapshot
            )

        # ====================================================
        # 8. 转换成 DataFrame
        # ====================================================

        snapshot_df = pd.DataFrame(
            snapshots
        )

        # ====================================================
        # 9. 打印核心快照
        # ====================================================

        print("\n" + "=" * 70)
        print("标准化行情快照")
        print("=" * 70)

        display_columns = [
            "option_symbol",
            "option_class",
            "underlying_symbol",
            "strike_price",
            "expire_rest_days",

            "option_last_price",
            "option_bid_price",
            "option_ask_price",
            "option_mid_price",
            "option_spread",
            "option_spread_ratio",

            "option_volume",
            "option_open_interest",

            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",

            "greeks_valid",

            "quote_datetime",
            "quote_age_seconds",
            "quote_fresh",

            "underlying_last_price",
            "underlying_price_change",
            "underlying_price_change_pct",

            "underlying_open_interest",
            "underlying_oi_change",
            "underlying_oi_change_pct",

            "price_oi_state",

            "contract_valid",
            "data_valid",
            "liquidity_valid",
            "tradeable",
        ]

        print(
            snapshot_df[
                display_columns
            ].to_string(
                index=False
            )
        )

        # ====================================================
        # 10. 数据质量检查
        # ====================================================

        print("\n" + "=" * 70)
        print("数据质量检查")
        print("=" * 70)

        for _, row in snapshot_df.iterrows():

            print(
                f"\n【{row['option_symbol']}】"
            )

            print(
                "  合约有效："
                + (
                    "✅"
                    if row["contract_valid"]
                    else "❌"
                )
            )

            print(
                "  Greeks有效："
                + (
                    "✅"
                    if row["greeks_valid"]
                    else "❌"
                )
            )

            print(
                "  买卖盘口："
                + (
                    "✅"
                    if (
                        pd.notna(
                            row["option_bid_price"]
                        )
                        and
                        pd.notna(
                            row["option_ask_price"]
                        )
                    )
                    else "❌"
                )
            )

            print(
                "  有成交量："
                + (
                    "✅"
                    if row["option_volume"] is not None
                    and pd.notna(
                        row["option_volume"]
                    )
                    and row["option_volume"] > 0
                    else "❌"
                )
            )

            print(
                "  有持仓量："
                + (
                    "✅"
                    if row["option_open_interest"] is not None
                    and pd.notna(
                        row["option_open_interest"]
                    )
                    and row["option_open_interest"] > 0
                    else "❌"
                )
            )

            if pd.notna(
                row["option_spread_ratio"]
            ):

                print(
                    "  买卖价差比例："
                    f"{row['option_spread_ratio']:.2%}"
                )

            else:

                print(
                    "  买卖价差比例：无法计算"
                )

            print(
                "  行情新鲜："
                + (
                    "✅"
                    if row["quote_fresh"]
                    else "❌"
                )
            )

        # ====================================================
        # 11. Price/OI 分析
        # ====================================================

        print("\n" + "=" * 70)
        print("标的期货 Price / Open Interest 分析")
        print("=" * 70)

        # ----------------------------------------------------
        # 注意：
        #
        # 当前版本是“相对前一交易时段”的变化。
        #
        # 后面我们还会增加：
        #
        # 5分钟
        # 15分钟
        # 30分钟
        # 60分钟
        #
        # 的真正盘中 Price/OI 变化。
        # ----------------------------------------------------

        for _, row in snapshot_df.iterrows():

            print(
                f"\n【{row['underlying_symbol']}】"
            )

            print(
                f"  当前价格："
                f"{row['underlying_last_price']}"
            )

            print(
                f"  价格变化："
                f"{row['underlying_price_change']}"
            )

            if pd.notna(
                row["underlying_price_change_pct"]
            ):

                print(
                    f"  价格变化率："
                    f"{row['underlying_price_change_pct']:.2%}"
                )

            print(
                f"  当前持仓量："
                f"{row['underlying_open_interest']}"
            )

            print(
                f"  持仓变化："
                f"{row['underlying_oi_change']}"
            )

            if pd.notna(
                row["underlying_oi_change_pct"]
            ):

                print(
                    f"  持仓变化率："
                    f"{row['underlying_oi_change_pct']:.2%}"
                )

            print(
                f"  Price/OI 状态："
                f"{row['price_oi_state']}"
            )

        # ====================================================
        # 12. 基础候选池
        # ====================================================

        print("\n" + "=" * 70)
        print("基础数据过滤结果")
        print("=" * 70)

        for _, row in snapshot_df.iterrows():

            symbol = row[
                "option_symbol"
            ]

            if row["tradeable"]:

                print(
                    f"\n✅ {symbol}"
                )

                print(
                    "   基础数据完整，"
                    "可以进入后续策略候选池。"
                )

            else:

                print(
                    f"\n❌ {symbol}"
                )

                for reason in row[
                    "trade_reasons"
                ]:

                    print(
                        f"   - {reason}"
                    )

        # ====================================================
        # 13. 测试完成
        # ====================================================

        print("\n" + "=" * 70)
        print("标准化行情快照测试完成")
        print("=" * 70)

    finally:

        # ====================================================
        # 无论程序中间是否发生异常，
        # 最后都尝试关闭 API。
        # ====================================================

        print("\n正在关闭 TqSdk API...")

        api.close()

        print(
            "✅ TqSdk API 已关闭。"
        )


# ============================================================
# 十、程序入口
# ============================================================

if __name__ == "__main__":
    main()