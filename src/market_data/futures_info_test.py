"""
futures_info_test.py
====================

功能：
    测试 TqSdk 对期货合约提供了哪些信息。

    这一阶段我们暂时不修改 underlying_mapper.py，
    先把 TqSdk 实际返回的数据看清楚。

    重点寻找：
        1. 期货合约代码
        2. 品种名称
        3. 交易所
        4. 合约月份
        5. 其他可能有用的信息
"""

import os

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


def main():

    print("=" * 70)
    print("TqSdk 期货合约信息测试")
    print("=" * 70)

    # ========================================================
    # 1. 读取 .env 中的天勤账号
    # ========================================================

    load_dotenv()

    username = os.getenv("TQ_USERNAME")
    password = os.getenv("TQ_PASSWORD")

    if not username or not password:
        print("错误：没有读取到 TQ_USERNAME / TQ_PASSWORD")
        return

    # ========================================================
    # 2. 登录 TqSdk
    # ========================================================

    api = TqApi(
        auth=TqAuth(
            username,
            password
        )
    )

    # ========================================================
    # 3. 使用我们已经验证过的期货合约
    #
    # 这些合约正好对应前面的期权标的。
    # ========================================================

    test_symbols = [
        "DCE.m2611",
        "CZCE.AP611",
        "SHFE.ad2611",
        "INE.bc2611",
        "GFEX.lc2611",
    ]

    try:

        for symbol in test_symbols:

            print()
            print("-" * 70)
            print(f"正在查询：{symbol}")
            print("-" * 70)

            # ------------------------------------------------
            # 查询期货合约信息
            # ------------------------------------------------

            info = api.query_symbol_info(symbol)

            # ------------------------------------------------
            # 判断是否查询成功
            # ------------------------------------------------

            if info is None or info.empty:
                print("没有查询到该合约的信息。")
                continue

            # ------------------------------------------------
            # query_symbol_info 返回 pandas DataFrame
            #
            # 我们取第一行。
            # ------------------------------------------------

            row = info.iloc[0]

            # ------------------------------------------------
            # 打印 DataFrame 中所有字段
            #
            # 这样我们可以确认 TqSdk 到底给了我们什么。
            # ------------------------------------------------

            print()

            for field in info.columns:

                try:
                    value = row[field]
                except Exception:
                    value = None

                print(
                    f"{field:<30} : {value}"
                )

    finally:

        # ====================================================
        # 4. 关闭 TqSdk
        # ====================================================

        api.close()

        print()
        print("=" * 70)
        print("TqSdk 已关闭")
        print("=" * 70)


if __name__ == "__main__":
    main()