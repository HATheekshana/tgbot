import requests
import aiohttp
CHARACTER_MAP={"10000002":"Ayaka","10000003":"Jean","10000005":"Aether","10000006":"Lisa","10000007":"Lumine","10000014":"Barbara","10000015":"Kaeya","10000016":"Diluc","10000020":"Razor","10000021":"Amber","10000022":"Venti","10000023":"Xiangling","10000024":"Beidou","10000025":"Xingqiu","10000026":"Xiao","10000027":"Ningguang","10000029":"Klee","10000030":"Zhongli","10000031":"Fischl","10000032":"Bennett","10000033":"Tartaglia","10000034":"Noelle","10000035":"Qiqi","10000036":"Chongyun","10000037":"Ganyu","10000038":"Albedo","10000039":"Diona","10000041":"Mona","10000042":"Keqing","10000043":"Sucrose","10000044":"Xinyan","10000045":"Rosaria","10000046":"HuTao","10000047":"Kazuha","10000048":"Yanfei","10000049":"Yoimiya","10000050":"Thoma","10000051":"Eula","10000052":"RaidenShogun","10000053":"Sayu","10000054":"Kokomi","10000055":"Gorou","10000056":"Sara","10000057":"Itto","10000058":"YaeMiko","10000059":"Heizou","10000060":"Yelan","10000061":"Kirara","10000062":"Aloy","10000063":"Shenhe","10000064":"YunJin","10000065":"KukiShinobu","10000066":"Ayato","10000067":"Collei","10000068":"Dori","10000069":"Tighnari","10000070":"Nilou","10000071":"Cyno","10000072":"Candace","10000073":"Nahida","10000074":"Layla","10000075":"Wanderer","10000076":"Faruzan","10000077":"Yaoyao","10000078":"Alhaitham","10000079":"Dehya","10000080":"Mika","10000081":"Kaveh","10000082":"Baizhu","10000083":"Lynette","10000084":"Lyney","10000085":"Freminet","10000086":"Wriothesley","10000087":"Neuvillette","10000088":"Charlotte","10000089":"Furina","10000090":"Chevreuse","10000091":"Navia","10000092":"Gaming","10000093":"Xianyun","10000094":"Chiori","10000095":"Sigewinne","10000096":"Arlecchino","10000097":"Sethos","10000098":"Clorinde","10000099":"Emilie","10000100":"Kachina","10000101":"Kinich","10000102":"Mualani","10000103":"Xilonen","10000104":"Chasca","10000105":"Olorun","10000106":"Mavuika","10000107":"Citlali","10000108":"Lanyan","10000109":"Mizuki","10000110":"Iansan","10000111":"Varesa","10000112":"Escoffier","10000113":"Ifa","10000114":"Skirk","10000115":"Dahlia","10000116":"Ineffa","10000117":"Unknown","10000118":"Unknown","10000119":"Lauma","10000120":"Flins","10000121":"Aino","10000122":"Nefer","10000123":"Durin","10000124":"Jahoda","10000901":"Mavuika","10000902":"HuTao","10000903":"Ineffa","10000904":"Columbina","10000998":"Unknown","10000999":"Unknown","11000046":"Jean","11000998":"Unknown","11000999":"Unknown"}
weapons3 = {
    "magicguide":"Magic Guide", "blacktassel":"Black Tassel", "bloodtainted":"Bloodtainted Greatsword",
    "coolsteel":"Coolsteel", "debate":"Debate Club", "emerald":"Emerald", "ferrousshadow":"Ferrous Shadow",
    "harbinger":"Harbinger Of Dawn", "ravenbow":"Raven Bow", "skyridergreat":"Skyrider Greatsword",
    "skyridersword":"Skyrider Sword", "slingshot":"Slingshot", "thrillingtales":"Thrilling Tales"
}
characters4 = {
    "shikanoin-heizou":"Shikanoin Heizou", "xinyan":"Xinyan", "yaoyao":"YaoYao", "ororon":"Ororon",
    "sethos":"Sethos", "mika":"Mika", "lynette":"Lynette", "layla":"Layla", "lan-yan":"Lan Yan",
    "kuki-shinobu":"Kuki Shinobu", "gaming":"Gaming", "iansan":"Iansan", "ifa":"Ifa", "illuga":"Illuga",
    "jahoda":"Jahoda", "kachina":"Kachina", "kaveh":"Kaveh", "kirara":"Kirara", "kujou-sara":"Kujou Sara",
    "freminet":"freminet", "faruzan":"Faruzan", "dori":"Dori", "chongyun":"Chongyun", "collei":"Collei",
    "dahlia":"Dahlia", "chevreuse":"Chevreuse", "charlotte":"charlotte", "candace":"Candace", "aino":"Aino",
    "yun-jin":"Yun Jin", "yanfei":"Yanfei", "xingqiu":"Xingqiu", "xiangling":"Xiangling", "thoma":"Thoma",
    "sucrose":"Sucrose", "diona":"Diona", "noelle":"Noelle", "sayu":"Sayu", "rosaria":"Rosaria",
    "barbara":"Barbara", "amber":"Amber", "beidou":"Beidou", "bennett":"Bennett", "fischl":"Fischl",
    "gorou":"Gorou", "kaeya":"Kaeya", "lisa":"Lisa", "ningguang":"Ningguang", "razor":"Razor"
}

characters5 = {
    "albedo":"Albedo", "alhaitham":"Alhaitham", "arataki-itto":"AratakiItto", "arlecchino":"Arlecchino", 
    "baizhu":"Baizhu", "chasca":"Chasca", "chiori":"Chiori", "citlali":"Citlali", "clorinde":"Clorinde", 
    "columbina":"Columbina", "cyno":"Cyno", "dehya":"Dehya", "diluc":"Diluc", "durin":"Durin", 
    "emilie":"Emilie", "escoffier":"Escoffier", "eula":"Eula", "flins":"Flins", "furina":"Furina", 
    "ganyu":"Ganyu", "hu-tao":"HuTao", "ineffa":"Ineffa", "jean":"Jean", "kaedehara-kazuha":"Kaedehara Kazuha", 
    "kamisato-ayaka":"Kamisato Ayaka", "kamisato-ayato":"Kamisato Ayato", "keqing":"Keqing", "kinich":"Kinich", 
    "klee":"Klee", "lauma":"Lauma", "lyney":"Lyney", "mavuika":"Mavuika", "mona":"Mona", "mualani":"Mualani", 
    "nahida":"Nahida", "navia":"Navia", "nefer":"Nefer", "neuvillette":"Neuvillette", "nilou":"Nilou", 
    "qiqi":"Qiqi", "raiden-shogun":"Raiden Shogun", "sangonomiya-kokomi":"Sangonomiya Kokomi", "shenhe":"Shenhe", 
    "sigewinne":"Sigewinne", "skirk":"Skirk", "tartaglia":"Tartaglia", "tighnari":"Tighnari", "varesa":"Varesa", 
    "varka":"Varka", "venti":"Venti", "wanderer":"Wanderer", "wriothesley":"Wriothesley", "xianyun":"Xianyun", 
    "xiao":"Xiao", "xilonen":"Xilonen", "yae-miko":"YaeMiko", "yelan":"Yelan", "yoimiya":"Yoimiya", 
    "yumemizuki-mizuki":"Yumemizuki Mizuki", "zhongli":"Zhongli", "zibai":"Zibai"
}
rare = {
    "r-barbara":"Summertime Barbara","r-ayaka":"Springbloom Ayaka","r-lisa":"Under Shade Lisa","r-jean":"Dandelion Jean",
}
TEAMS_DB = {
    "Flins": {
        "premium": "images/teams/flins_premium.jpg",
        "f2p": "images/teams/flins_f2p.jpg",
        "without columbina": "images/teams/flins_nc.jpg",
        "without ineffa": "images/teams/flins_ic.jpg"
    },
    "nefer": {
        "premium": "images/teams/nefer_premium.jpg",
        
    },
    "zibai": {
        "premium": "images/teams/zibai_premium.jpg"
                }
}