import os
from dotenv import load_dotenv
from tqsdk import TqApi, TqAuth

#获取有效的测试数据
load_dotenv()
api = TqApi(auth=TqAuth(os.getenv("TQ_USERNAME"), os.getenv("TQ_PASSWORD")))
for und in ["DCE.m2611", "SHFE.ad2611", "INE.bc2611", "GFEX.lc2611","CZCE.AP612"]:
    opts = api.query_options(und, option_class="PUT", expired=False)
    print(und, len(opts), opts[:6])
api.close()