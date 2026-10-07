
# -*- coding: utf-8 -*-

"""
quote_monitor.py
================

功能：
1. 连接天勤 TqSdk
2. 获取测试期权的基本信息
3. 获取期权对应的标的
4. 一次性订阅期权和标的行情
5. 等待行情更新
6. 输出期权 + 标的的行情快照

目前：
    只测试行情获取

暂时不做：
    - IV
    - Delta
    - Gamma
    - Theta
    - 策略筛选
    - 自动交易

后续会在这个基础上逐步扩展。
"""

import os
import math
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth

# ------------------------------------------------------------
# 导入我们之前已经验证成功的：
#
# 期权 → 标的
#
# 映射模块
# ------------------------------------------------------------
from underlying_mapper import query_underlying


# ============================================================
# 一、测试期权
# ============================================================

# 当前阶段只测试 6 个期权。
#
# 等行情模块稳定以后，
# 再把这里改成自动扫描全部期权。
TEST_OPTION_SYMBOLS = [
    "CFFEX.HO2610-C-2500",
    "DCE.m2611-P-2700",
    "CZCE.AP611C6300",
    "SHFE.ad2611C20400",
    "INE.bc2611C100000",
    "GFEX.lc2611-C-100000",
]


# ============================================================
# 二、行情数据结构
# ============================================================

@dataclass
class QuoteSnapshot:
    """
    保存某一个合约的行情快照。

    以后我们可以很方便地把这个结构：

        → 保存成 Excel
        → 保存成 CSV
        → 保存到数据库
        → 用于策略计算
        → 用于回测
    """

    symbol: str
    datetime: str

    last_price: Optional[float]

    bid_price1: Optional[float]
    ask_price1: Optional[float]

    bid_volume1: Optional[int]
    ask_volume1: Optional[int]

    volume: Optional[int]
    open_interest: Optional[int]

    settlement: Optional[float]
    pre_settlement: Optional[float]


# ============================================================
# 三、数据转换函数
# ============================================================

def safe_float(value) -> Optional[float]:
    """
    安全地把数据转换成 float。

    如果 TqSdk 当前没有提供有效数据，
    就返回 None。

    例如：

        NaN
        ""
        None

    都不会导致程序崩溃。
    """

    try:

        value = float(value)

        if math.isnan(value):
            return None

        return value

    except (TypeError, ValueError):

        return None


def safe_int(value) -> Optional[int]:
    """
    安全地把数据转换成整数。
    """

    try:

        value = float(value)

        if math.isnan(value):
            return None

        return int(value)

    except (TypeError, ValueError):

        return None


# ============================================================
# 四、把 TqSdk 行情转换成自己的行情结构
# ============================================================

def make_quote_snapshot(
        symbol: str,
        quote
) -> QuoteSnapshot:
    """
    将 TqSdk 的 Quote 对象转换成统一的 QuoteSnapshot。

    注意：

    不同交易所、不同品种，
    某些字段可能没有有效数据。

    所以这里全部使用安全读取。
    """

    return QuoteSnapshot(

        symbol=symbol,

        datetime=str(
            getattr(
                quote,
                "datetime",
                ""
            )
        ),

        last_price=safe_float(
            getattr(
                quote,
                "last_price",
                None
            )
        ),

        bid_price1=safe_float(
            getattr(
                quote,
                "bid_price1",
                None
            )
        ),

        ask_price1=safe_float(
            getattr(
                quote,
                "ask_price1",
                None
            )
        ),

        bid_volume1=safe_int(
            getattr(
                quote,
                "bid_volume1",
                None
            )
        ),

        ask_volume1=safe_int(
            getattr(
                quote,
                "ask_volume1",
                None
            )
        ),

        volume=safe_int(
            getattr(
                quote,
                "volume",
                None
            )
        ),

        open_interest=safe_int(
            getattr(
                quote,
                "open_interest",
                None
            )
        ),

        settlement=safe_float(
            getattr(
                quote,
                "settlement",
                None
            )
        ),

        pre_settlement=safe_float(
            getattr(
                quote,
                "pre_settlement",
                None
            )
        ),
    )


# ============================================================
# 五、打印行情
# ============================================================

def print_quote(
        title: str,
        snapshot: QuoteSnapshot
):
    """
    将行情打印成容易阅读的格式。
    """

    print()
    print("=" * 70)

    print(title)

    print(
        f"合约：{snapshot.symbol}"
    )

    print(
        f"时间：{snapshot.datetime}"
    )

    print("-" * 70)

    print(
        f"最新价：{snapshot.last_price}"
    )

    print(
        f"买一：{snapshot.bid_price1}"
    )

    print(
        f"卖一：{snapshot.ask_price1}"
    )

    print(
        f"买一量：{snapshot.bid_volume1}"
    )

    print(
        f"卖一量：{snapshot.ask_volume1}"
    )

    print(
        f"成交量：{snapshot.volume}"
    )

    print(
        f"持仓量：{snapshot.open_interest}"
    )

    print(
        f"结算价：{snapshot.settlement}"
    )

    print(
        f"昨结算：{snapshot.pre_settlement}"
    )

    print("=" * 70)


# ============================================================
# 六、主程序
# ============================================================

def main():

    # ========================================================
    # 1. 读取 .env
    # ========================================================

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

    # ========================================================
    # 2. 登录天勤
    # ========================================================

    auth = TqAuth(
        username,
        password
    )

    api = TqApi(
        auth=auth
    )

    # ========================================================
    # 3. 准备保存行情对象
    # ========================================================

    # 期权行情
    option_quotes = {}

    # 标的行情
    underlying_quotes = {}

    # --------------------------------------------------------
    # 非常重要：
    #
    # 保存：
    #
    # 期权 → 标的信息
    #
    # 后面不再重复 query_underlying()
    # --------------------------------------------------------

    option_underlyings = {}

    try:

        # ====================================================
        # 4. 建立期权 → 标的关系
        # ====================================================

        print()
        print(
            "正在建立期权与标的的对应关系..."
        )
        print()

        for option_symbol in TEST_OPTION_SYMBOLS:

            try:

                # ------------------------------------------------
                # 查询一次标的信息
                # ------------------------------------------------

                underlying_info = query_underlying(
                    api,
                    option_symbol
                )

                if underlying_info is None:

                    print(
                        f"❌ 无法找到标的："
                        f"{option_symbol}"
                    )

                    continue

                # ------------------------------------------------
                # 保存映射关系
                #
                # 后面直接使用，
                # 不再重复查询。
                # ------------------------------------------------

                option_underlyings[
                    option_symbol
                ] = underlying_info

                underlying_symbol = (
                    underlying_info.underlying_symbol
                )

                print(
                    f"{option_symbol}"
                    f"  →  "
                    f"{underlying_symbol}"
                    f"  →  "
                    f"{underlying_info.underlying_name}"
                )

            except Exception as e:

                print(
                    f"❌ 查询 {option_symbol} "
                    f"标的信息失败：{e}"
                )

        # ====================================================
        # 5. 订阅行情
        # ====================================================

        print()
        print(
            "正在订阅期权和标的行情..."
        )
        print()

        # ----------------------------------------------------
        # 订阅期权行情
        # ----------------------------------------------------

        for option_symbol in option_underlyings:

            try:

                option_quotes[
                    option_symbol
                ] = api.get_quote(
                    option_symbol
                )

            except Exception as e:

                print(
                    f"❌ 订阅期权失败："
                    f"{option_symbol}"
                )

                print(
                    f"   原因：{e}"
                )

        # ----------------------------------------------------
        # 订阅标的行情
        # ----------------------------------------------------

        for option_symbol, underlying_info in (
                option_underlyings.items()
        ):

            underlying_symbol = (
                underlying_info.underlying_symbol
            )

            # ----------------------------------------------
            # 如果多个期权对应同一个标的，
            # 只订阅一次。
            # ----------------------------------------------

            if underlying_symbol in underlying_quotes:
                continue

            try:

                underlying_quotes[
                    underlying_symbol
                ] = api.get_quote(
                    underlying_symbol
                )

            except Exception as e:

                print(
                    f"❌ 订阅标的失败："
                    f"{underlying_symbol}"
                )

                print(
                    f"   原因：{e}"
                )

        # ====================================================
        # 6. 等待行情更新
        # ====================================================

        print()
        print("=" * 70)
        print(
            "正在等待行情数据..."
        )
        print(
            "TqSdk 会自动更新已订阅的行情。"
        )
        print("=" * 70)
        print()

        # ----------------------------------------------------
        # 第一次等待行情
        # ----------------------------------------------------

        deadline = time.time() + 10

        updated = api.wait_update(
            deadline=deadline
        )
        if updated:

            print(
                "✅ 收到新的行情更新。"
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
        # 7. 输出行情
        # ====================================================

        print()
        print(
            "########################"
        )
        print(
            "#     当前行情快照     #"
        )
        print(
            "########################"
        )

        # ----------------------------------------------------
        # 一个一个期权输出
        # ----------------------------------------------------

        for option_symbol in option_underlyings:

            # =================================================
            # A. 获取期权行情
            # =================================================

            if option_symbol not in option_quotes:

                continue

            option_quote = option_quotes[
                option_symbol
            ]

            option_snapshot = make_quote_snapshot(
                option_symbol,
                option_quote
            )

            print_quote(
                "【期权行情】",
                option_snapshot
            )

            # =================================================
            # B. 找到对应标的
            # =================================================

            underlying_info = (
                option_underlyings[
                    option_symbol
                ]
            )

            underlying_symbol = (
                underlying_info.underlying_symbol
            )

            # =================================================
            # C. 获取标的行情
            # =================================================

            if underlying_symbol not in underlying_quotes:

                print(
                    f"⚠️ 没有成功订阅标的："
                    f"{underlying_symbol}"
                )

                continue

            underlying_quote = (
                underlying_quotes[
                    underlying_symbol
                ]
            )

            # -------------------------------------------------
            # 生成标的行情快照
            # -------------------------------------------------

            underlying_snapshot = (
                make_quote_snapshot(
                    underlying_symbol,
                    underlying_quote
                )
            )

            print_quote(
                "【标的行情】",
                underlying_snapshot
            )

        # ====================================================
        # 8. 完成
        # ====================================================

        print()
        print("=" * 70)
        print(
            "行情测试完成。"
        )
        print("=" * 70)

    finally:

        # ----------------------------------------------------
        # 关闭 TqSdk
        # ----------------------------------------------------

        api.close()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    main()
