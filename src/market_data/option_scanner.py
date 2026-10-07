"""
期权合约扫描器

功能：
1. 连接天勤 TqSdk
2. 查询当前市场中的期权合约
3. 筛选出指定期权品种
4. 输出期权的基本信息

目前阶段：
    只负责“发现市场上的期权”。

暂时不做：
    - 下单
    - 实盘交易
    - 策略判断
    - 自动卖出期权

后续我们会在这个模块的基础上继续增加：
    - 到期日
    - 执行价
    - Call / Put
    - 最新价
    - Bid / Ask
    - 成交量
    - 持仓量
    - IV
    - Greeks
"""

import os

from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth


def create_tq_api():
    """
    创建 TqApi 连接。

    为什么单独写这个函数？

    因为以后项目中可能有很多地方需要使用 TqApi。
    如果每个文件都重复写账号密码读取和连接代码，
    后期会非常难维护。

    所以这里先把“创建天勤连接”独立出来。
    """

    # ------------------------------------------------------------
    # 读取项目根目录下的 .env 文件
    # ------------------------------------------------------------
    load_dotenv()

    # 从环境变量读取快期账号
    username = os.getenv("TQ_USERNAME")

    # 从环境变量读取快期密码
    password = os.getenv("TQ_PASSWORD")

    # ------------------------------------------------------------
    # 检查账号密码
    # ------------------------------------------------------------
    if not username or not password:
        raise ValueError(
            "没有读取到快期账号信息，请检查项目根目录下的 .env 文件。"
        )

    # ------------------------------------------------------------
    # 创建 TqApi
    # ------------------------------------------------------------
    api = TqApi(
        auth=TqAuth(
            username,
            password
        )
    )

    return api


def find_option_quotes(api):
    """
    查询市场中的期权合约。

    参数：
        api：
            已经创建好的 TqApi 对象。

    返回：
        期权合约代码列表。
    """

    print("=" * 70)
    print("正在查询期权合约……")
    print("=" * 70)

    # ------------------------------------------------------------
    # 查询期权合约
    #
    # ins_class="OPTION"
    #
    # 表示：
    #     只查询期权，不查询普通期货。
    # ------------------------------------------------------------
    option_quotes = api.query_quotes(
        ins_class="OPTION"
    )

    print()
    print("查询成功！")
    print("期权合约总数量：", len(option_quotes))

    return option_quotes


def print_option_quotes(option_quotes, max_count=50):
    """
    打印期权合约。

    参数：
        option_quotes：
            期权合约列表。

        max_count：
            最多打印多少个。
            默认打印 50 个。

    注意：
        我们目前只是为了观察 TqSdk 返回的数据格式。
    """

    print()
    print("=" * 70)
    print(f"前 {min(max_count, len(option_quotes))} 个期权合约")
    print("=" * 70)

    for index, symbol in enumerate(
        option_quotes[:max_count],
        start=1
    ):
        print(f"{index:03d}. {symbol}")

    print("=" * 70)


def main():
    """
    主程序。
    """

    print()
    print("=" * 70)
    print("OptionSeller —— 期权合约扫描器")
    print("=" * 70)

    # ------------------------------------------------------------
    # 创建 TqApi
    # ------------------------------------------------------------
    api = create_tq_api()

    try:

        # --------------------------------------------------------
        # 查询期权
        # --------------------------------------------------------
        option_quotes = find_option_quotes(api)

        # --------------------------------------------------------
        # 打印期权合约
        # --------------------------------------------------------
        print_option_quotes(
            option_quotes,
            max_count=50
        )

        print()
        print("期权合约扫描完成！")

    finally:

        # --------------------------------------------------------
        # 无论程序是否正常结束，都关闭 TqApi
        # --------------------------------------------------------
        api.close()

        print("TqSdk 连接已经关闭。")


if __name__ == "__main__":
    main()