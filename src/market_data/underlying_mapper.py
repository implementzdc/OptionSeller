"""
underlying_mapper.py
====================

功能：
    将期权合约与它对应的标的进行关联。

核心逻辑：

    期权合约
        ↓
    TqSdk 查询
        ↓
    underlying_symbol
        ↓
    查询对应的标的合约
        ↓
    instrument_name / product_id
        ↓
    得到中文标的信息


例如：

    DCE.m2611-P-2700
            ↓
    underlying_symbol
            ↓
        DCE.m2611
            ↓
    instrument_name
            ↓
        豆粕2611


注意：
    本模块不再自己猜测期货品种中文名称。

    直接使用 TqSdk 返回的：
        instrument_name
        product_id
        exchange_id

    这样可以减少人工维护错误。
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


# ============================================================
# 一、交易所中文名称
# ============================================================

EXCHANGE_NAME_MAP = {
    "CFFEX": "中国金融期货交易所",
    "CZCE": "郑州商品交易所",
    "DCE": "大连商品交易所",
    "GFEX": "广州期货交易所",
    "INE": "上海国际能源交易中心",
    "SHFE": "上海期货交易所",
    "SSE": "上海证券交易所",
    "SZSE": "深圳证券交易所",
}


# ============================================================
# 二、已经确认的指数中文名称
# ============================================================

INDEX_NAME_MAP = {
    "SSE.000016": "上证50指数",
    "SSE.000300": "沪深300指数",
    "SSE.000852": "中证1000指数",
}


# ============================================================
# 三、统一的标的信息
# ============================================================

@dataclass
class UnderlyingInfo:
    """
    保存一个期权对应的标的信息。

    例如：

        option_symbol
            DCE.m2611-P-2700

        underlying_symbol
            DCE.m2611

        underlying_type
            期货

        underlying_name
            豆粕2611

        product_id
            m

        product_name
            豆粕

        exchange
            DCE

        exchange_name
            大连商品交易所

        delivery_year
            2026

        delivery_month
            11
    """

    # --------------------------------------------------------
    # 原始期权代码
    # --------------------------------------------------------

    option_symbol: str

    # --------------------------------------------------------
    # 标的代码
    # --------------------------------------------------------

    underlying_symbol: Optional[str]

    # --------------------------------------------------------
    # 标的类型
    #
    # 期货 / 指数 / 证券 / 未知
    # --------------------------------------------------------

    underlying_type: str

    # --------------------------------------------------------
    # 标的完整名称
    #
    # 例如：
    #     豆粕2611
    # --------------------------------------------------------

    underlying_name: str

    # --------------------------------------------------------
    # 品种代码
    #
    # 例如：
    #     m
    # --------------------------------------------------------

    product_id: Optional[str]

    # --------------------------------------------------------
    # 品种中文名称
    #
    # 例如：
    #     豆粕
    # --------------------------------------------------------

    product_name: str

    # --------------------------------------------------------
    # 交易所代码
    #
    # 例如：
    #     DCE
    # --------------------------------------------------------

    exchange: Optional[str]

    # --------------------------------------------------------
    # 交易所中文名称
    # --------------------------------------------------------

    exchange_name: str

    # --------------------------------------------------------
    # 交割年份
    # --------------------------------------------------------

    delivery_year: Optional[int]

    # --------------------------------------------------------
    # 交割月份
    # --------------------------------------------------------

    delivery_month: Optional[int]


# ============================================================
# 四、判断标的类型
# ============================================================

def get_underlying_type(
    underlying_symbol: Optional[str]
) -> str:
    """
    根据标的代码判断标的类型。

    例如：

        DCE.m2611
        CZCE.AP611
        SHFE.ad2611

    都是期货。

        SSE.000016

    是指数。
    """

    if not underlying_symbol:
        return "未知"

    # --------------------------------------------------------
    # 已知指数
    # --------------------------------------------------------

    if underlying_symbol in INDEX_NAME_MAP:
        return "指数"

    # --------------------------------------------------------
    # SSE / SZSE
    # --------------------------------------------------------

    if underlying_symbol.startswith("SSE."):
        return "证券"

    if underlying_symbol.startswith("SZSE."):
        return "证券"

    # --------------------------------------------------------
    # 六个期货相关交易所
    # --------------------------------------------------------

    futures_exchanges = {
        "CFFEX",
        "CZCE",
        "DCE",
        "GFEX",
        "INE",
        "SHFE",
    }

    exchange = underlying_symbol.split(".", 1)[0]

    if exchange in futures_exchanges:
        return "期货"

    return "未知"


# ============================================================
# 五、把 pandas / numpy 的数值安全转换成 int
# ============================================================

def safe_int(value) -> Optional[int]:
    """
    将 TqSdk 返回的年份、月份等数据安全转换成 int。

    例如：

        2026.0 → 2026
        11.0   → 11

    如果数据为空，则返回 None。
    """

    if value is None:
        return None

    try:

        # 处理 NaN
        if str(value).lower() == "nan":
            return None

        return int(value)

    except (ValueError, TypeError):

        return None


# ============================================================
# 六、获取指数名称
# ============================================================

def get_index_name(
    underlying_symbol: str
) -> str:
    """
    获取指数中文名称。

    目前先处理已经验证过的几个股指期权标的。
    """

    return INDEX_NAME_MAP.get(
        underlying_symbol,
        underlying_symbol
    )


# ============================================================
# 七、查询期权对应的标的
# ============================================================

def query_underlying(
    api: TqApi,
    option_symbol: str
) -> UnderlyingInfo:
    """
    查询一个期权的完整标的信息。

    第一步：

        查询期权

    第二步：

        获取 underlying_symbol

    第三步：

        如果标的是期货，
        再查询对应的期货合约。

    第四步：

        获取：
            instrument_name
            product_id
            exchange_id
            delivery_year
            delivery_month
    """

    # ========================================================
    # 1. 查询期权信息
    # ========================================================

    option_info = api.query_symbol_info(
        option_symbol
    )

    if option_info is None or option_info.empty:

        return UnderlyingInfo(
            option_symbol=option_symbol,
            underlying_symbol=None,
            underlying_type="未知",
            underlying_name="未知",
            product_id=None,
            product_name="未知",
            exchange=None,
            exchange_name="未知",
            delivery_year=None,
            delivery_month=None,
        )

    # 取第一行
    option_row = option_info.iloc[0]

    # ========================================================
    # 2. 获取 underlying_symbol
    # ========================================================

    underlying_symbol = option_row.get(
        "underlying_symbol"
    )

    # 处理 NaN
    if underlying_symbol is not None:

        if str(underlying_symbol).lower() == "nan":
            underlying_symbol = None

    # ========================================================
    # 3. 判断标的类型
    # ========================================================

    underlying_type = get_underlying_type(
        underlying_symbol
    )

    # ========================================================
    # 4. 如果没有标的
    # ========================================================

    if not underlying_symbol:

        return UnderlyingInfo(
            option_symbol=option_symbol,
            underlying_symbol=None,
            underlying_type="未知",
            underlying_name="未知",
            product_id=None,
            product_name="未知",
            exchange=None,
            exchange_name="未知",
            delivery_year=None,
            delivery_month=None,
        )

    # ========================================================
    # 5. 如果是指数
    # ========================================================

    if underlying_type == "指数":

        exchange = underlying_symbol.split(
            ".", 1
        )[0]

        return UnderlyingInfo(
            option_symbol=option_symbol,
            underlying_symbol=underlying_symbol,
            underlying_type="指数",
            underlying_name=get_index_name(
                underlying_symbol
            ),
            product_id=None,
            product_name=get_index_name(
                underlying_symbol
            ),
            exchange=exchange,
            exchange_name=EXCHANGE_NAME_MAP.get(
                exchange,
                exchange
            ),
            delivery_year=None,
            delivery_month=None,
        )

    # ========================================================
    # 6. 如果是期货
    #
    # 这是最重要的一步。
    #
    # 例如：
    #
    # DCE.m2611
    #
    # 再查询：
    #
    # api.query_symbol_info("DCE.m2611")
    # ========================================================

    if underlying_type == "期货":

        future_info = api.query_symbol_info(
            underlying_symbol
        )

        if (
            future_info is None
            or future_info.empty
        ):

            exchange = underlying_symbol.split(
                ".",
                1
            )[0]

            return UnderlyingInfo(
                option_symbol=option_symbol,
                underlying_symbol=underlying_symbol,
                underlying_type="期货",
                underlying_name=underlying_symbol,
                product_id=None,
                product_name="未知",
                exchange=exchange,
                exchange_name=EXCHANGE_NAME_MAP.get(
                    exchange,
                    exchange
                ),
                delivery_year=None,
                delivery_month=None,
            )

        # 取第一行
        future_row = future_info.iloc[0]

        # ----------------------------------------------------
        # 获取期货合约完整名称
        #
        # 例如：
        #
        # DCE.m2611 → 豆粕2611
        # ----------------------------------------------------

        instrument_name = future_row.get(
            "instrument_name"
        )

        if instrument_name is None:
            instrument_name = underlying_symbol

        # ----------------------------------------------------
        # 获取品种代码
        #
        # 例如：
        #
        # m
        # AP
        # ad
        # bc
        # lc
        # ----------------------------------------------------

        product_id = future_row.get(
            "product_id"
        )

        if product_id is not None:

            if str(product_id).lower() == "nan":
                product_id = None
            else:
                product_id = str(product_id)

        # ----------------------------------------------------
        # 获取交易所
        # ----------------------------------------------------

        exchange = future_row.get(
            "exchange_id"
        )

        if exchange is not None:
            exchange = str(exchange)

        # ----------------------------------------------------
        # 获取交割年份和月份
        # ----------------------------------------------------

        delivery_year = safe_int(
            future_row.get(
                "delivery_year"
            )
        )

        delivery_month = safe_int(
            future_row.get(
                "delivery_month"
            )
        )

        # ----------------------------------------------------
        # 获取品种名称
        #
        # 例如：
        #
        # 豆粕2611
        #
        # 我们把最后的 4 位月份数字去掉，
        # 得到：
        #
        # 豆粕
        #
        # 但这里不直接强制截取，
        # 后面我们还会进一步完善。
        # ----------------------------------------------------

        product_name = instrument_name

        # 常见形式：
        #
        # 豆粕2611
        # 苹果2611
        # 碳酸锂2611
        #
        # 去掉最后4位数字。
        match = re.match(
            r"^(.*?)(\d{4})$",
            str(instrument_name)
        )

        if match:

            product_name = match.group(1)

        return UnderlyingInfo(
            option_symbol=option_symbol,
            underlying_symbol=underlying_symbol,
            underlying_type="期货",
            underlying_name=str(
                instrument_name
            ),
            product_id=product_id,
            product_name=str(
                product_name
            ),
            exchange=exchange,
            exchange_name=EXCHANGE_NAME_MAP.get(
                exchange,
                exchange if exchange else "未知"
            ),
            delivery_year=delivery_year,
            delivery_month=delivery_month,
        )

    # ========================================================
    # 7. 其他类型
    # ========================================================

    exchange = underlying_symbol.split(
        ".",
        1
    )[0]

    return UnderlyingInfo(
        option_symbol=option_symbol,
        underlying_symbol=underlying_symbol,
        underlying_type=underlying_type,
        underlying_name=underlying_symbol,
        product_id=None,
        product_name=underlying_symbol,
        exchange=exchange,
        exchange_name=EXCHANGE_NAME_MAP.get(
            exchange,
            exchange
        ),
        delivery_year=None,
        delivery_month=None,
    )


# ============================================================
# 八、批量查询
# ============================================================

def query_underlyings(
    api: TqApi,
    option_symbols: list[str]
) -> list[UnderlyingInfo]:
    """
    批量查询多个期权对应的标的信息。
    """

    results = []

    for option_symbol in option_symbols:

        print(
            f"正在查询：{option_symbol}"
        )

        try:

            result = query_underlying(
                api,
                option_symbol
            )

            results.append(result)

        except Exception as e:

            print(
                f"查询失败：{option_symbol}"
            )

            print(
                f"错误信息：{e}"
            )

            results.append(
                UnderlyingInfo(
                    option_symbol=option_symbol,
                    underlying_symbol=None,
                    underlying_type="未知",
                    underlying_name="未知",
                    product_id=None,
                    product_name="未知",
                    exchange=None,
                    exchange_name="未知",
                    delivery_year=None,
                    delivery_month=None,
                )
            )

    return results


# ============================================================
# 九、测试程序
# ============================================================

def main():

    print("=" * 70)
    print("期权 → 标的信息映射测试")
    print("=" * 70)

    # --------------------------------------------------------
    # 读取 .env
    # --------------------------------------------------------

    load_dotenv()

    username = os.getenv(
        "TQ_USERNAME"
    )

    password = os.getenv(
        "TQ_PASSWORD"
    )

    if not username or not password:

        print(
            "错误：没有读取到 TqSdk 登录信息。"
        )

        return

    # --------------------------------------------------------
    # 登录 TqSdk
    # --------------------------------------------------------

    api = TqApi(
        auth=TqAuth(
            username,
            password
        )
    )

    # --------------------------------------------------------
    # 已经验证过的测试期权
    # --------------------------------------------------------

    test_symbols = [

        "CFFEX.HO2610-C-2500",

        "DCE.m2611-P-2700",

        "CZCE.AP611C6300",

        "SHFE.ad2611C20400",

        "INE.bc2611C100000",

        "GFEX.lc2611-C-100000",
    ]

    try:

        results = query_underlyings(
            api,
            test_symbols
        )

        print()
        print("=" * 70)
        print("最终结果")
        print("=" * 70)

        for item in results:

            print()

            print(
                f"期权代码：{item.option_symbol}"
            )

            print(
                f"标的代码：{item.underlying_symbol}"
            )

            print(
                f"标的类型：{item.underlying_type}"
            )

            print(
                f"标的名称：{item.underlying_name}"
            )

            print(
                f"品种代码：{item.product_id}"
            )

            print(
                f"品种名称：{item.product_name}"
            )

            print(
                f"交易所：{item.exchange_name}"
            )

            print(
                f"交割月份："
                f"{item.delivery_year}-"
                f"{item.delivery_month}"
            )

    finally:

        api.close()

        print()
        print("TqSdk 已关闭。")


# ============================================================
# 十、程序入口
# ============================================================

if __name__ == "__main__":
    main()