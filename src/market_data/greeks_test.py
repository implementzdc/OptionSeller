# -*- coding: utf-8 -*-

"""
greeks_test.py
========================================================
功能：
    测试 TqSdk 是否可以直接获取期权 Greeks。

测试指标：
    1. Delta
    2. Gamma
    3. Theta
    4. Vega
    5. Rho

同时测试：
    1. 剩余到期天数
    2. 行权价
    3. 标的合约
    4. 期权类型
    5. TqSdk 返回的其他 Greeks 信息

说明：
    本程序只是测试程序，不进行任何交易。

认证方式：
    与项目中的 quote_monitor.py 保持一致：
        .env
            TQ_USERNAME=你的快期账号
            TQ_PASSWORD=你的快期密码

作者说明：
    本程序采用详细中文注释，方便后续学习和维护。
"""

import os
import pandas as pd

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


# ========================================================
# 1. 测试期权
# ========================================================

"""
这里使用我们之前已经成功获取行情的 6 个期权。

它们分别来自不同交易所：

    CFFEX
        上证50股指期权

    DCE
        豆粕期权

    CZCE
        苹果期权

    SHFE
        铝合金期权

    INE
        国际铜期权

    GFEX
        碳酸锂期权
"""

TEST_OPTION_SYMBOLS = [

    "CFFEX.HO2610-C-2500",

    "DCE.m2611-P-2700",

    "CZCE.AP611C6300",

    "SHFE.ad2611C20400",

    "INE.bc2611C100000",

    "GFEX.lc2611-C-100000",

]


def main():

    # ====================================================
    # 1. 读取 .env
    # ====================================================

    print("=" * 70)
    print("正在读取 TqSdk 登录配置...")
    print("=" * 70)

    # ----------------------------------------------------
    # 从项目环境变量中读取：
    #
    # TQ_USERNAME
    # TQ_PASSWORD
    #
    # 这样账号密码就不会直接写进 Python 代码。
    # ----------------------------------------------------

    load_dotenv()

    username = os.getenv(
        "TQ_USERNAME"
    )

    password = os.getenv(
        "TQ_PASSWORD"
    )

    # ----------------------------------------------------
    # 检查账号密码是否成功读取
    # ----------------------------------------------------

    if not username or not password:

        raise RuntimeError(
            "没有读取到 TQ_USERNAME / TQ_PASSWORD，"
            "请检查项目根目录下的 .env 文件。"
        )

    print(
        "✅ 已成功读取 TqSdk 登录配置。"
    )

    # ====================================================
    # 2. 登录天勤
    # ====================================================

    print()
    print("=" * 70)
    print("正在连接天勤量化...")
    print("=" * 70)

    # ----------------------------------------------------
    # 创建认证对象
    # ----------------------------------------------------

    auth = TqAuth(
        username,
        password
    )

    # ----------------------------------------------------
    # 创建 TqSdk API
    # ----------------------------------------------------

    api = TqApi(
        auth=auth
    )

    print(
        "✅ TqSdk API 创建成功。"
    )

    try:

        # =================================================
        # 3. 输出测试合约
        # =================================================

        print()
        print("=" * 70)
        print("准备测试以下期权：")
        print("=" * 70)

        for symbol in TEST_OPTION_SYMBOLS:

            print(
                f"  {symbol}"
            )

        # =================================================
        # 4. 查询 Greeks
        # =================================================

        print()
        print("=" * 70)
        print("正在调用 TqSdk query_option_greeks()...")
        print("=" * 70)

        print()
        print(
            "说明："
        )

        print(
            "v=None → 让 TqSdk 使用隐含波动率计算 Greeks"
        )

        print(
            "r=0.025 → 无风险利率暂时使用 2.5%"
        )

        print()

        # ------------------------------------------------
        # 调用 TqSdk 官方 Greeks 接口
        #
        # query_option_greeks()
        #
        # 可以一次查询多个期权。
        # ------------------------------------------------

        greeks_df = api.query_option_greeks(
            TEST_OPTION_SYMBOLS,
            v=None,
            r=0.025
        )

        # =================================================
        # 5. 检查返回结果
        # =================================================

        print()
        print("=" * 70)
        print("TqSdk Greeks 返回结果")
        print("=" * 70)

        # ------------------------------------------------
        # 判断是否返回 DataFrame
        # ------------------------------------------------

        print()
        print(
            "返回数据类型：",
            type(greeks_df)
        )

        print(
            "数据行数：",
            len(greeks_df)
        )

        print(
            "数据列数：",
            len(greeks_df.columns)
        )

        # =================================================
        # 6. 查看所有字段
        # =================================================

        print()
        print("=" * 70)
        print("TqSdk 返回字段")
        print("=" * 70)

        for column in greeks_df.columns:

            print(
                f"  {column}"
            )

        # =================================================
        # 7. 输出完整数据
        # =================================================

        print()
        print("=" * 70)
        print("完整 Greeks 数据")
        print("=" * 70)

        print()

        # ------------------------------------------------
        # to_string()
        #
        # 防止 pandas 因为终端宽度不够而省略数据。
        # ------------------------------------------------

        print(
            greeks_df.to_string(
                index=False
            )
        )

        # =================================================
        # 8. 提取我们最关心的数据
        # =================================================

        print()
        print("=" * 70)
        print("重点 Greeks 数据")
        print("=" * 70)

        # ------------------------------------------------
        # 这些是我们期权卖方策略最关心的数据。
        # ------------------------------------------------

        important_columns = [

            "instrument_id",

            "instrument_name",

            "option_class",

            "underlying_symbol",

            "strike_price",

            "expire_rest_days",

            "delta",

            "gamma",

            "theta",

            "vega",

            "rho",

        ]

        # ------------------------------------------------
        # 只选择实际存在的字段。
        #
        # 这样即使当前 TqSdk 某些字段名称不同，
        # 程序也不会直接崩溃。
        # ------------------------------------------------

        available_columns = [

            column

            for column in important_columns

            if column in greeks_df.columns

        ]

        # ------------------------------------------------
        # 输出重点字段
        # ------------------------------------------------

        if available_columns:

            print()

            print(
                greeks_df[
                    available_columns
                ].to_string(
                    index=False
                )
            )

        else:

            print(
                "⚠️ 没有找到预期的 Greeks 字段。"
            )

        # =================================================
        # 9. 单独检查 Delta
        # =================================================

        print()
        print("=" * 70)
        print("Delta 检查")
        print("=" * 70)

        if "delta" in greeks_df.columns:

            for _, row in greeks_df.iterrows():

                symbol = row.get(
                    "instrument_id",
                    "未知合约"
                )

                delta = row[
                    "delta"
                ]

                # ----------------------------------------
                # 判断是否为 NaN
                # ----------------------------------------

                if pd.isna(delta):

                    print(
                        f"{symbol:<35} → Delta = NaN"
                    )

                else:

                    print(
                        f"{symbol:<35} → Delta = {delta}"
                    )

        else:

            print(
                "❌ 返回结果中没有 delta 字段。"
            )

        # =================================================
        # 10. 检查 Gamma / Theta / Vega
        # =================================================

        print()
        print("=" * 70)
        print("Gamma / Theta / Vega 检查")
        print("=" * 70)

        greek_columns = [

            "gamma",

            "theta",

            "vega",

            "rho",

        ]

        for _, row in greeks_df.iterrows():

            symbol = row.get(
                "instrument_id",
                "未知合约"
            )

            print()
            print(
                f"【{symbol}】"
            )

            for greek in greek_columns:

                # ----------------------------------------
                # 如果字段不存在
                # ----------------------------------------

                if greek not in greeks_df.columns:

                    print(
                        f"  {greek.upper():<8} → 字段不存在"
                    )

                    continue

                value = row[
                    greek
                ]

                # ----------------------------------------
                # 判断是否为 NaN
                # ----------------------------------------

                if pd.isna(value):

                    print(
                        f"  {greek.upper():<8} → NaN"
                    )

                else:

                    print(
                        f"  {greek.upper():<8} → {value}"
                    )

        # =================================================
        # 11. 最终结论提示
        # =================================================

        print()
        print("=" * 70)
        print("Greeks 测试完成")
        print("=" * 70)

        print()
        print(
            "下一步需要重点观察："
        )

        print(
            "1. Delta 是否正常返回"
        )

        print(
            "2. Gamma 是否正常返回"
        )

        print(
            "3. Theta 是否正常返回"
        )

        print(
            "4. Vega 是否正常返回"
        )

        print(
            "5. 哪些低流动性期权返回 NaN"
        )

        print()
        print(
            "请把本次程序的完整输出发给我，"
            "我们再决定正式行情模块如何接入 Greeks。"
        )

    finally:

        # =================================================
        # 12. 关闭 TqSdk
        # =================================================

        print()
        print(
            "=" * 70
        )

        print(
            "正在关闭 TqSdk API..."
        )

        api.close()

        print(
            "✅ TqSdk API 已关闭。"
        )

        print(
            "=" * 70
        )


# ========================================================
# 程序入口
# ========================================================

if __name__ == "__main__":

    main()