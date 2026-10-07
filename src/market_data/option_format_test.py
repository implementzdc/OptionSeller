
"""
期权代码格式测试程序

功能：
1. 连接 TqSdk
2. 获取各交易所的期权合约
3. 按交易所分别统计
4. 每个交易所随机/顺序展示一部分真实期权代码
5. 同时查询这些合约的中文名称

目的：
我们暂时不解析期权代码。

先把 TqSdk 真实返回的期权代码格式摸清楚，
然后再针对不同交易所设计正确的解析器。
"""

from collections import defaultdict

from tqsdk import TqApi, TqAuth
from dotenv import load_dotenv
import os


# ============================================================
# 一、读取 .env 中的快期账号
# ============================================================

load_dotenv()

username = os.getenv("TQ_USERNAME")
password = os.getenv("TQ_PASSWORD")


# ============================================================
# 二、检查账号配置
# ============================================================

if not username or not password:

    raise RuntimeError(
        "没有读取到 TQ_USERNAME 或 TQ_PASSWORD，"
        "请检查项目根目录下的 .env 文件。"
    )


# ============================================================
# 三、创建 TqSdk API
# ============================================================

api = TqApi(
    auth=TqAuth(
        username,
        password
    )
)


try:

    print("=" * 80)
    print("正在获取 TqSdk 期权合约...")
    print("=" * 80)

    # ========================================================
    # 四、获取所有期权合约
    #
    # 注意：
    # expired=False 表示只获取没有下市的期权。
    #
    # 这样比之前直接获取全部 22 万多个历史期权更适合
    # 我们后面真正做“期权卖方雷达”。
    # ========================================================

    option_symbols = api.query_quotes(
        ins_class="OPTION",
        expired=False
    )

    print()
    print(f"当前未下市期权数量：{len(option_symbols)}")


    # ========================================================
    # 五、按照交易所分类
    #
    # 例如：
    #
    # CFFEX.IO2606-C-4650
    #
    # ↓
    #
    # CFFEX
    # ========================================================

    exchange_options = defaultdict(list)

    for symbol in option_symbols:

        # 正常格式应该包含 "."
        if "." not in symbol:
            continue

        exchange, contract = symbol.split(
            ".",
            1
        )

        exchange_options[exchange].append(
            symbol
        )


    # ========================================================
    # 六、输出每个交易所的统计数量
    # ========================================================

    print()
    print("=" * 80)
    print("各交易所期权数量")
    print("=" * 80)

    for exchange in sorted(exchange_options):

        symbols = exchange_options[exchange]

        print(
            f"{exchange:<10} "
            f"{len(symbols):>8} 个"
        )


    # ========================================================
    # 七、查询中文合约名称
    #
    # TqSdk 的 query_symbol_info() 可以返回：
    #
    # instrument_name
    #
    # 也就是合约中文名称。
    #
    # 这一点非常重要！
    #
    # 后面我们不一定需要自己维护大量的
    # “代码 → 中文名称”字典。
    # ========================================================

    print()
    print("=" * 80)
    print("各交易所实际期权代码示例")
    print("=" * 80)


    # 每个交易所最多展示 10 个
    sample_count = 10


    for exchange in sorted(exchange_options):

        symbols = exchange_options[exchange]

        print()
        print(f"【{exchange}】")
        print("-" * 80)

        # 只取前 10 个
        samples = symbols[:sample_count]

        try:

            # 查询这些合约的详细信息
            info_df = api.query_symbol_info(
                samples
            )

            # 转成字典，方便后面根据 instrument_id 查询
            info_dict = {}

            for _, row in info_df.iterrows():

                info_dict[
                    row["instrument_id"]
                ] = row


            # ------------------------------------------------
            # 输出
            # ------------------------------------------------

            for symbol in samples:

                row = info_dict.get(symbol)

                if row is None:

                    print(
                        f"{symbol:<35}"
                        f"中文名称：未找到"
                    )

                else:

                    print(
                        f"{symbol:<35}"
                        f"中文名称：{row['instrument_name']}"
                    )

        except Exception as error:

            print(
                f"查询中文名称失败：{error}"
            )


    # ========================================================
    # 八、额外输出：
    # 每个交易所的前 30 个原始代码
    #
    # 这个部分主要是方便我们研究代码结构。
    # ========================================================

    print()
    print("=" * 80)
    print("原始期权代码格式详细观察")
    print("=" * 80)

    for exchange in sorted(exchange_options):

        print()
        print(f"========== {exchange} ==========")

        for symbol in exchange_options[exchange][:30]:

            print(symbol)


finally:

    # ========================================================
    # 九、关闭 TqSdk
    # ========================================================

    api.close()

    print()
    print("=" * 80)
    print("TqSdk 已关闭")
    print("=" * 80)
