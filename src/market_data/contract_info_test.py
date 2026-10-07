
"""
contract_info_test.py

作用：
    查询 TqSdk 中真实期权合约的详细信息。

本程序目前只做一个事情：

    查看 TqSdk 对一个期权合约到底提供了哪些真实字段。

重点观察：
    1. underlying_symbol      → 对应的标的合约
    2. instrument_id          → 当前期权代码
    3. product_id             → 品种代码
    4. strike_price           → 执行价格
    5. expire_datetime        → 到期时间
    6. expire_rest_days       → 剩余到期天数
    7. option_class           → 看涨/看跌
    8. exchange_id            → 交易所

注意：
    这一步暂时不做任何策略计算。
    我们先把 TqSdk 的真实数据结构搞清楚，
    再设计后面的代码。
"""

import os

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


# ============================================================
# 1. 读取 .env
# ============================================================

# 从项目根目录的 .env 文件中读取天勤账号和密码
load_dotenv()

username = os.getenv("TQ_USERNAME")
password = os.getenv("TQ_PASSWORD")


# 如果没有读取到账号或密码，直接提示
if not username or not password:
    raise RuntimeError(
        "没有读取到 TQ_USERNAME 或 TQ_PASSWORD，"
        "请检查 OptionSeller 项目根目录下的 .env 文件。"
    )


# ============================================================
# 2. 创建 TqSdk API
# ============================================================

api = TqApi(
    auth=TqAuth(
        username,
        password
    )
)


# ============================================================
# 3. 准备测试期权
# ============================================================

# 这里继续使用我们前面已经确认存在的真实期权。
#
# 故意选择不同交易所，
# 观察不同交易所的 underlying_symbol 是否都能正确返回。

test_symbols = [
    "CFFEX.HO2610-C-2500",
    "DCE.m2611-C-2700",
    "CZCE.AP611C6300",
    "SHFE.ad2611C20400",
    "INE.bc2611C100000",
    "GFEX.lc2611-C-100000",
]


# ============================================================
# 4. 我们真正关心的字段
# ============================================================

# 只打印这些关键字段。
#
# 这样不会被 TqSdk 大量内部字段干扰，
# 我们也可以非常直观地看到：
#
#       期权 → 对应期货
#
# 到底是什么关系。

important_fields = [
    "instrument_id",
    "instrument_name",
    "underlying_symbol",
    "strike_price",
    "exchange_id",
    "product_id",
    "expire_datetime",
    "expire_rest_days",
    "delivery_year",
    "delivery_month",
    "last_exercise_datetime",
    "exercise_year",
    "exercise_month",
    "option_class",
    "expired",
]


# ============================================================
# 5. 查询并打印
# ============================================================

try:

    print("=" * 100)
    print("TqSdk 期权 → 对应期货字段探测")
    print("=" * 100)

    for symbol in test_symbols:

        print()
        print("-" * 100)
        print(f"正在查询：{symbol}")
        print("-" * 100)

        # query_symbol_info() 返回的是 DataFrame。
        info = api.query_symbol_info(symbol)

        # ----------------------------------------------------
        # 判断是否查询到了数据
        # ----------------------------------------------------

        if info.empty:
            print("没有查询到该合约的信息。")
            continue

        # ----------------------------------------------------
        # DataFrame 只有一行。
        #
        # iloc[0] 就是取得第一行数据。
        # ----------------------------------------------------

        row = info.iloc[0]

        print()

        # ----------------------------------------------------
        # 逐个打印我们关心的字段
        # ----------------------------------------------------

        for field in important_fields:

            # 如果字段存在，就读取它。
            if field in info.columns:

                value = row[field]

                print(f"{field:25} = {value}")

            else:

                # 如果未来 TqSdk 改变字段名称，
                # 我们也能马上发现。
                print(f"{field:25} = 【字段不存在】")


finally:

    # ========================================================
    # 6. 关闭 TqSdk
    # ========================================================

    api.close()

    print()
    print("=" * 100)
    print("字段探测完成")
    print("=" * 100)
