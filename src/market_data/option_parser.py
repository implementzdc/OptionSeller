
"""
多交易所期权合约代码解析器

============================================================
一、这个文件是干什么的？
============================================================

TqSdk 返回的期权代码，不同交易所的格式并不完全一样。

例如：

1. 中金所 CFFEX
   CFFEX.HO2610-C-2500

2. 大商所 DCE
   DCE.a2611-C-3700

3. 郑商所 CZCE
   CZCE.AP611C6300

4. 上期所 SHFE
   SHFE.ad2611C20400

5. 能源中心 INE
   INE.bc2611C100000

6. 广期所 GFEX
   GFEX.lc2611-C-100000


============================================================
二、这个程序目前负责什么？
============================================================

把上面的“机器代码”转换成程序容易使用的结构：

    原始代码
        ↓
    交易所
        ↓
    品种代码
        ↓
    到期月份
        ↓
    看涨 / 看跌
        ↓
    执行价格
        ↓
    中文名称


例如：

DCE.m2611-C-2700

↓

交易所：大连商品交易所
品种：豆粕
到期月份：2026年11月
类型：看涨期权
执行价：2700


============================================================
三、特别说明
============================================================

目前我们只负责解析“代码本身能够确定的信息”。

具体的：

    期权到期日
    对应期货合约
    期货价格
    行权价
    最后交易日

后面会结合 TqSdk 的合约元数据进一步确认。

这样比单纯通过字符串猜测更加可靠。
"""


from dataclasses import dataclass
from typing import Optional
import re


# ============================================================
# 一、交易所代码 → 中文名称
# ============================================================

EXCHANGE_NAME_MAP = {

    "CFFEX": "中国金融期货交易所",

    "DCE": "大连商品交易所",

    "CZCE": "郑州商品交易所",

    "SHFE": "上海期货交易所",

    "INE": "上海国际能源交易中心",

    "GFEX": "广州期货交易所",
}


# ============================================================
# 二、品种代码 → 中文名称
#
# 注意：
# 这里保存的是“期货品种”的中文名称。
#
# 后面如果发现新的期权品种，只需要继续往这里增加即可。
# ============================================================

PRODUCT_NAME_MAP = {

    # --------------------------------------------------------
    # 中金所
    # --------------------------------------------------------

    "IO": "沪深300股指",

    "HO": "上证50股指",

    "MO": "中证1000股指",


    # --------------------------------------------------------
    # 大连商品交易所
    # --------------------------------------------------------

    "A": "豆一",

    "B": "豆二",

    "C": "玉米",

    "M": "豆粕",

    "Y": "豆油",

    "P": "棕榈油",

    "I": "铁矿石",

    "L": "聚乙烯",

    "V": "聚氯乙烯",

    "PP": "聚丙烯",

    "EG": "乙二醇",

    "EB": "苯乙烯",

    "PG": "液化石油气",

    "JD": "鸡蛋",

    "RR": "粳米",

    "LH": "生猪",


    # --------------------------------------------------------
    # 郑州商品交易所
    # --------------------------------------------------------

    "SR": "白糖",

    "CF": "棉花",

    "TA": "PTA",

    "MA": "甲醇",

    "RM": "菜粕",

    "OI": "菜油",

    "SA": "纯碱",

    "FG": "玻璃",

    "AP": "苹果",

    "PK": "花生",

    "UR": "尿素",

    "SM": "锰硅",

    "SF": "硅铁",

    "CY": "棉纱",

    "PX": "对二甲苯",


    # --------------------------------------------------------
    # 上海期货交易所
    # --------------------------------------------------------

    "CU": "沪铜",

    "AL": "沪铝",

    "ZN": "沪锌",

    "PB": "沪铅",

    "NI": "沪镍",

    "SN": "沪锡",

    "AU": "黄金",

    "AG": "白银",

    "RB": "螺纹钢",

    "RU": "天然橡胶",

    "BU": "石油沥青",

    "FU": "燃料油",

    "SC": "原油",

    "NR": "20号胶",

    "SS": "不锈钢",

    "AO": "氧化铝",

    "BR": "丁二烯橡胶",

    "SP": "纸浆",

    "AD": "铝",


    # --------------------------------------------------------
    # 上海国际能源交易中心
    # --------------------------------------------------------

    "BC": "国际铜",

    "LU": "低硫燃料油",

    "NR": "20号胶",

    "SC": "原油",

    "EC": "集运指数（欧线）",


    # --------------------------------------------------------
    # 广州期货交易所
    # --------------------------------------------------------

    "SI": "工业硅",

    "LC": "碳酸锂",

    "PS": "多晶硅",

    "PT": "铂",

    "AU": "黄金",
}


# ============================================================
# 三、期权类型
# ============================================================

OPTION_TYPE_NAME_MAP = {

    "C": "看涨期权",

    "P": "看跌期权",
}


# ============================================================
# 四、统一的数据结构
# ============================================================

@dataclass
class OptionContract:
    """
    一个标准化的期权合约。

    无论来自哪个交易所，最终都转换成这个结构。

    例如：

        DCE.m2611-C-2700

    会变成：

        exchange = "DCE"
        exchange_name = "大连商品交易所"

        product_code = "M"
        product_name = "豆粕"

        expiry_month = "2611"

        option_type = "C"
        option_type_name = "看涨期权"

        strike = 2700

    """

    # --------------------------------------------------------
    # 原始合约代码
    # --------------------------------------------------------

    symbol: str

    # --------------------------------------------------------
    # 交易所代码
    # --------------------------------------------------------

    exchange: str

    # --------------------------------------------------------
    # 交易所中文名称
    # --------------------------------------------------------

    exchange_name: str

    # --------------------------------------------------------
    # 品种代码
    # --------------------------------------------------------

    product_code: str

    # --------------------------------------------------------
    # 品种中文名称
    # --------------------------------------------------------

    product_name: str

    # --------------------------------------------------------
    # 到期月份
    #
    # 例如：
    #
    # 2611
    #
    # 表示：
    #
    # 2026年11月
    # --------------------------------------------------------

    expiry_month: str

    # --------------------------------------------------------
    # 期权类型
    #
    # C = 看涨
    # P = 看跌
    # --------------------------------------------------------

    option_type: str

    # --------------------------------------------------------
    # 期权类型中文
    # --------------------------------------------------------

    option_type_name: str

    # --------------------------------------------------------
    # 执行价格
    # --------------------------------------------------------

    strike: float

    # --------------------------------------------------------
    # 对应的期货合约
    #
    # 当前暂时不通过字符串猜。
    #
    # 后面从 TqSdk 合约信息中获取。
    # --------------------------------------------------------

    underlying_symbol: Optional[str] = None


# ============================================================
# 五、交易所中文名称
# ============================================================

def get_exchange_name(exchange: str) -> str:
    """
    根据交易所代码获取中文名称。

    例如：

        DCE → 大连商品交易所
    """

    return EXCHANGE_NAME_MAP.get(
        exchange,
        "未知交易所"
    )


# ============================================================
# 六、品种中文名称
# ============================================================

def get_product_name(product_code: str) -> str:
    """
    根据品种代码获取中文名称。

    如果暂时没有配置，则返回：

        未知品种（代码）

    """

    # 统一转换成大写。
    # 因为 TqSdk 中可能出现小写：
    #
    # m
    # lc
    # bc
    #
    # 而我们的字典使用大写。

    product_code = product_code.upper()

    return PRODUCT_NAME_MAP.get(
        product_code,
        f"未知品种（{product_code}）"
    )


# ============================================================
# 七、将两位年份月份转换成人类容易看的格式
# ============================================================

def format_expiry_month(expiry_month: str) -> str:
    """
    将：

        2611

    转换成：

        2026年11月

    注意：

    这里只负责显示。

    真正的到期日，后面还是应该从 TqSdk 获取。
    """

    if len(expiry_month) != 4:
        return expiry_month

    year = expiry_month[:2]

    month = expiry_month[2:]

    try:

        year_number = int(year)

        month_number = int(month)

    except ValueError:

        return expiry_month

    # 当前项目运行时间是 20xx 年，
    # 因此暂时按照 2000 + 两位年份处理。

    full_year = 2000 + year_number

    return f"{full_year}年{month_number:02d}月"


# ============================================================
# 八、解析 CFFEX
# ============================================================

def parse_cffex(symbol: str) -> OptionContract:
    """
    解析中金所期权。

    示例：

        CFFEX.HO2610-C-2500

    结构：

        HO
        2610
        C
        2500
    """

    exchange = "CFFEX"

    # 去掉交易所部分
    contract = symbol.split(".", 1)[1]

    # 使用 - 分隔
    parts = contract.split("-")

    if len(parts) != 3:

        raise ValueError(
            f"CFFEX期权代码格式错误：{symbol}"
        )

    contract_base = parts[0]

    option_type = parts[1]

    strike_text = parts[2]

    # 检查 C / P

    if option_type not in ("C", "P"):

        raise ValueError(
            f"无法识别期权方向：{symbol}"
        )

    # 找到第一个数字

    match = re.match(
        r"^([A-Za-z]+)(\d{4})$",
        contract_base
    )

    if not match:

        raise ValueError(
            f"无法解析CFFEX标的和月份：{symbol}"
        )

    product_code = match.group(1)

    expiry_month = match.group(2)

    strike = float(strike_text)

    return OptionContract(

        symbol=symbol,

        exchange=exchange,

        exchange_name=get_exchange_name(exchange),

        product_code=product_code.upper(),

        product_name=get_product_name(product_code),

        expiry_month=expiry_month,

        option_type=option_type,

        option_type_name=OPTION_TYPE_NAME_MAP[option_type],

        strike=strike,
    )


# ============================================================
# 九、解析 DCE / GFEX
# ============================================================

def parse_dash_exchange(symbol: str) -> OptionContract:
    """
    解析使用 “-” 分隔的交易所。

    当前包括：

        DCE
        GFEX

    示例：

        DCE.m2611-C-3700

        GFEX.lc2611-C-100000
    """

    exchange, contract = symbol.split(
        ".",
        1
    )

    parts = contract.split("-")

    if len(parts) != 3:

        raise ValueError(
            f"{exchange}期权代码格式错误：{symbol}"
        )

    contract_base = parts[0]

    option_type = parts[1]

    strike_text = parts[2]

    if option_type not in ("C", "P"):

        raise ValueError(
            f"无法识别期权方向：{symbol}"
        )

    # 品种 + 四位年月
    #
    # m2611
    # lc2611

    match = re.match(
        r"^([A-Za-z]+)(\d{4})$",
        contract_base
    )

    if not match:

        raise ValueError(
            f"无法解析品种和到期月份：{symbol}"
        )

    product_code = match.group(1)

    expiry_month = match.group(2)

    strike = float(strike_text)

    return OptionContract(

        symbol=symbol,

        exchange=exchange,

        exchange_name=get_exchange_name(exchange),

        product_code=product_code.upper(),

        product_name=get_product_name(product_code),

        expiry_month=expiry_month,

        option_type=option_type,

        option_type_name=OPTION_TYPE_NAME_MAP[option_type],

        strike=strike,
    )


# ============================================================
# 十、解析 SHFE / INE
# ============================================================

def parse_shfe_ine(symbol: str) -> OptionContract:
    """
    解析 SHFE / INE 期权。

    示例：

        SHFE.ad2611C20400

        INE.bc2611C100000

    结构：

        品种 + 年月 + C/P + 执行价
    """

    exchange, contract = symbol.split(
        ".",
        1
    )

    # 使用正则表达式一次性拆分。

    match = re.match(
        r"^([A-Za-z]+)(\d{4})(C|P)(\d+(?:\.\d+)?)$",
        contract
    )

    if not match:

        raise ValueError(
            f"{exchange}期权代码格式错误：{symbol}"
        )

    product_code = match.group(1)

    expiry_month = match.group(2)

    option_type = match.group(3)

    strike = float(
        match.group(4)
    )

    return OptionContract(

        symbol=symbol,

        exchange=exchange,

        exchange_name=get_exchange_name(exchange),

        product_code=product_code.upper(),

        product_name=get_product_name(product_code),

        expiry_month=expiry_month,

        option_type=option_type,

        option_type_name=OPTION_TYPE_NAME_MAP[option_type],

        strike=strike,
    )


# ============================================================
# 十一、解析 CZCE
# ============================================================

def parse_czce(symbol: str) -> OptionContract:
    """
    解析郑商所期权。

    示例：

        CZCE.AP611C6300

    郑商所的代码比较特殊。

    AP611C6300

    可以理解成：

        AP
        6
        11
        C
        6300

    其中年份只有一位。

    当前按照 TqSdk 实际返回格式进行解析。
    """

    exchange = "CZCE"

    contract = symbol.split(
        ".",
        1
    )[1]

    # --------------------------------------------------------
    # 正则表达式
    #
    # 品种：字母
    # 年份：1位
    # 月份：2位
    # C/P
    # 执行价
    # --------------------------------------------------------

    match = re.match(
        r"^([A-Za-z]+)(\d)(\d{2})(C|P)(\d+(?:\.\d+)?)$",
        contract
    )

    if not match:

        raise ValueError(
            f"CZCE期权代码格式错误：{symbol}"
        )

    product_code = match.group(1)

    year = match.group(2)

    month = match.group(3)

    option_type = match.group(4)

    strike = float(
        match.group(5)
    )

    # --------------------------------------------------------
    # 郑商所只有一位年份。
    #
    # 当前我们把：
    #
    # 6 → 2026
    #
    # 进行转换。
    #
    # 注意：
    # 这是为了当前项目展示。
    # 后续仍建议使用 TqSdk 到期日字段进行最终确认。
    # --------------------------------------------------------

    expiry_month = (
        f"202{year}{month}"
    )

    # 为了和其他交易所统一，
    # 这里最终保存成四位：
    #
    # 2611

    expiry_month = (
        f"2{year}{month}"
    )

    return OptionContract(

        symbol=symbol,

        exchange=exchange,

        exchange_name=get_exchange_name(exchange),

        product_code=product_code.upper(),

        product_name=get_product_name(product_code),

        expiry_month=expiry_month,

        option_type=option_type,

        option_type_name=OPTION_TYPE_NAME_MAP[option_type],

        strike=strike,
    )


# ============================================================
# 十二、统一入口
# ============================================================

def parse_option_symbol(symbol: str) -> OptionContract:
    """
    自动判断交易所，然后调用对应解析器。

    以后我们的其他程序只需要调用：

        parse_option_symbol(symbol)

    不需要关心具体是哪个交易所。
    """

    # --------------------------------------------------------
    # 检查基本格式
    # --------------------------------------------------------

    if "." not in symbol:

        raise ValueError(
            f"期权代码缺少交易所信息：{symbol}"
        )

    exchange = symbol.split(
        ".",
        1
    )[0]

    # --------------------------------------------------------
    # 根据交易所选择解析器
    # --------------------------------------------------------

    if exchange == "CFFEX":

        return parse_cffex(symbol)

    elif exchange in ("DCE", "GFEX"):

        return parse_dash_exchange(symbol)

    elif exchange in ("SHFE", "INE"):

        return parse_shfe_ine(symbol)

    elif exchange == "CZCE":

        return parse_czce(symbol)

    else:

        raise ValueError(
            f"暂不支持的期权交易所：{exchange}"
        )


# ============================================================
# 十三、测试程序
# ============================================================

def main():

    """
    测试六个交易所。

    这些代码全部来自你刚才实际运行 TqSdk 得到的数据。
    """

    test_symbols = [

        # 中金所
        "CFFEX.HO2610-C-2500",

        # 大商所
        "DCE.a2611-C-3700",

        "DCE.m2611-P-2700",

        # 郑商所
        "CZCE.AP611C6300",

        # 上期所
        "SHFE.ad2611C20400",

        # 能源中心
        "INE.bc2611C100000",

        # 广期所
        "GFEX.lc2611-C-100000",
    ]

    print("=" * 80)

    print("多交易所期权代码解析测试")

    print("=" * 80)

    for symbol in test_symbols:

        print()

        print("-" * 80)

        print(
            f"原始代码：{symbol}"
        )

        try:

            contract = parse_option_symbol(
                symbol
            )

            print(
                f"交易所："
                f"{contract.exchange_name}"
                f"（{contract.exchange}）"
            )

            print(
                f"品种："
                f"{contract.product_name}"
                f"（{contract.product_code}）"
            )

            print(
                f"到期月份："
                f"{format_expiry_month(contract.expiry_month)}"
                f"（{contract.expiry_month}）"
            )

            print(
                f"期权类型："
                f"{contract.option_type_name}"
                f"（{contract.option_type}）"
            )

            print(
                f"执行价格："
                f"{contract.strike}"
            )

            print(
                f"对应期货合约："
                f"{contract.underlying_symbol}"
            )

        except Exception as error:

            print(
                f"解析失败：{error}"
            )

    print()

    print("=" * 80)

    print("测试完成")

    print("=" * 80)


# ============================================================
# 十四、程序入口
# ============================================================

if __name__ == "__main__":

    main()
