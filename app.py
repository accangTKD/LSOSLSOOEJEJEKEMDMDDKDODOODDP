# app.py
import warnings
warnings.filterwarnings("ignore")

import asyncio
import json
import re
from typing import Any, Awaitable, Callable

import httpx
from flask import Flask, jsonify, request

app = Flask(__name__)

# ═════════════════════════════════════════════════════════════
# Utils
# ═════════════════════════════════════════════════════════════

CODA_URL = "https://order-sg.codashop.com/initPayment.action"


async def hit_coda(client: httpx.AsyncClient, body: str) -> Any:
    r = await client.post(
        CODA_URL, content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        return r.json()
    except Exception:
        return {}


def _get_username(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    cf = data.get("confirmationFields")
    return cf.get("username") if isinstance(cf, dict) else None


def _get_role(data: Any, index: int = 0) -> dict:
    if not isinstance(data, dict):
        return {}
    cf = data.get("confirmationFields")
    if not isinstance(cf, dict):
        return {}
    roles = cf.get("roles")
    if not isinstance(roles, list) or len(roles) <= index:
        return {}
    r = roles[index]
    return r if isinstance(r, dict) else {}


def _dot_get(source: Any, path: str) -> Any:
    """Akses nested dict/list via 'a.b.0.c' style path."""
    current = source
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _extract_nickname(data: Any, paths: list[str]) -> str | None:
    for p in paths:
        v = _dot_get(data, p)
        if isinstance(v, str) and v:
            return v
    return None


def _coda_ok(data: Any) -> bool:
    """Return True if Codashop response indicates success."""
    if not isinstance(data, dict):
        return False
    return data.get("errorCode") in ("", None) and not data.get("errorMsg")


# ═════════════════════════════════════════════════════════════
# Router game — EXISTING
# ═════════════════════════════════════════════════════════════

async def aov(c, id, server=None):
    body = (f"user.userId={id}&voucherPricePoint.id=7946"
            "&voucherPricePoint.price=10000&shopLang=id_ID&voucherTypeName=AOV")
    data = await hit_coda(c, body)
    role = _get_role(data)
    return {"success": True, "game": "Garena: AOV (Arena Of Valor)",
            "id": id, "name": role.get("role"), "server": role.get("server")}


async def codm(c, id, server=None):
    body = (f"user.userId={id}&voucherPricePoint.id=46129"
            "&voucherPricePoint.price=10000&shopLang=id_ID&voucherTypeName=CALL_OF_DUTY")
    data = await hit_coda(c, body)
    role = _get_role(data)
    return {"success": True, "game": "Call Of Duty Mobile",
            "id": id, "name": role.get("role"), "server": role.get("server")}


async def ff(c, id, server=None):
    r = await c.get(f"https://gopay.co.id/games/v1/order/prepare/FREEFIRE?userId={id}")
    return {"success": True, "game": "Garena Free Fire", "id": id,
            "name": r.json().get("data")}


async def gi(c, id, server=None):
    first = id[0] if id else ""
    if id.startswith("18") or first == "8":
        sn, sv = "Asia", "os_asia"
    elif first == "6":
        sn, sv = "America", "os_usa"
    elif first == "7":
        sn, sv = "Europe", "os_euro"
    elif first == "9":
        sn, sv = "SAR (Taiwan, Hong Kong, Macao)", "os_cht"
    else:
        return {"success": False, "message": "Not found"}
    body = ("voucherPricePoint.id=116054&voucherPricePoint.price=16500"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={sv}"
            "&voucherTypeName=GENSHIN_IMPACT&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Genshin Impact",
                "id": id, "server": sn, "name": name}
    return {"success": False, "message": "Not found"}


async def hi(c, id, server=None):
    body = ("voucherPricePoint.id=48250&voucherPricePoint.price=16500"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId="
            "&voucherTypeName=HONKAI_IMPACT&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Honkai Impact 3rd", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def hsr(c, id, server=None):
    first = id[0] if id else ""
    m = {"6": ("America", "prod_official_usa"),
         "7": ("Europe", "prod_official_eur"),
         "8": ("Asia", "prod_official_asia"),
         "9": ("SAR (Taiwan, Hong Kong, Macao)", "prod_official_cht")}
    if first not in m:
        return {"success": False, "message": "Not found"}
    sn, sv = m[first]
    body = ("voucherPricePoint.id=855316&voucherPricePoint.price=16000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={sv}"
            "&voucherTypeName=HONKAI_STAR_RAIL&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Honkai: Star Rail",
                "id": id, "server": sn, "name": name}
    return {"success": False, "message": "Not found"}


_LA_ZONES = [
    ("miskatown", "MiskaTown", 500001), ("sandcastle", "SandCastle", 500002),
    ("mouthswamp", "MouthSwamp", 500003), ("redwoodtown", "RedwoodTown", 500004),
    ("obelisk", "Obelisk", 500005), ("newland", "NewLand", 500006),
    ("chaosoutpost", "ChaosOutpost", 500007), ("ironstride", "IronStride", 500008),
    ("crystalthornsea", "CrystalthornSea", 500009), ("fallforest", "FallForest", 510001),
    ("mountsnow", "MountSnow", 510002), ("nancycity", "NancyCity", 520001),
    ("charlestown", "CharlesTown", 520002), ("snowhighlands", "SnowHighlands", 520003),
    ("santopany", "Santopany", 520004), ("levincity", "LevinCity", 520005),
    ("milestone", "MileStone", 520006), ("chaoscity", "ChaosCity", 520007),
    ("twinislands", "TwinIslands", 520008), ("hopewall", "HopeWall", 520009),
    ("labyrinthsea", "LabyrinthSea", 520010),
]


async def la(c, id, server=None):
    if not server:
        return {"success": False, "message": "Bad request"}
    zlc = server.lower()
    sn = sv = None
    for key, n, code in _LA_ZONES:
        if key in zlc:
            sn, sv = n, code
            break
    if sn is None:
        return {"success": False, "message": "Not found"}
    body = ("voucherPricePoint.id=45713&voucherPricePoint.price=15000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={sv}"
            "&voucherTypeName=NETEASE_LIFEAFTER&shopLang=id_ID")
    data = await hit_coda(c, body)
    return {"success": True, "game": "LifeAfter",
            "id": id, "server": sn, "name": _get_username(data)}


_JWT1 = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkeW5hbWljU2t1SW5mbyI6IntcInNrdUlkXCI6XCIxXzEwMDBcIixcImV2ZW50UGFja2FnZVwiOlwiMFwiLFwiZGVub21JbWFnZVVybFwiOlwiaHR0cHM6Ly9jZG4xLmNvZGFzaG9wLmNvbS9pbWFnZXMvOTE2XzQ0Y2MyNmU3LWU3NDctNDk4NS04MzQ1LWZmODFjMGUwM2QxN19MT1ZFIEFORCBERUVQU1BBQ0VfaW1hZ2UvNjAgQ3J5c3RhbHMucG5nXCIsXCJkZW5vbU5hbWVcIjpcIjYwIENyeXN0YWxzXCIsXCJkZW5vbUNhdGVnb3J5TmFtZVwiOlwiQ3J5c3RhbFwiLFwidGFnc1wiOltdLFwiY291bnRyeTJOYW1lXCI6XCJJRFwiLFwibHZ0SWRcIjoxMTY4NCxcImRlZmF1bHRQcmljZVwiOjE5MDAwLjAsXCJkZWZhdWx0Q3VycmVuY3lcIjpcIklEUlwiLFwiYWRkaXRpb25hbEluZm9cIjp7XCJEeW5hbWljU2t1UHJvbW9EZXRhaWxcIjpcIm51bGxcIixcIkxveWFsdHlDdXJyZW5jeURldGFpbFwiOlwie1xcXCJwcmljaW5nU2NoZW1lXFxcIjpcXFwicGFpZF9jdXJyZW5jeVxcXCIsXFxcImxveWFsdHlFYXJuZWRBbW91bnRcXFwiOjAuMCxcXFwibG95YWx0eUJ1cm5lZEFtb3VudFxcXCI6MC4wfVwifX0ifQ.VsI9fduPyRDA1t_GOQ65cR88HJc_a93ROdy8Fsg8bEw"
_JWT2 = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkeW5hbWljU2t1SW5mbyI6IntcInBjSWRcIjoyMjcsXCJwcmljZVwiOjE5MDAwLjAsXCJjdXJyZW5jeVwiOlwiSURSXCIsXCJhcGlQcmljZVwiOjE5MDAwLjAsXCJhcGlQcmljZUN1cnJlbmN5XCI6XCJJRFJcIixcImRpc2NvdW50UHJpY2VcIjoxOTAwMC4wLFwicHJpY2VCZWZvcmVUYXhcIjoxNzExNy4wLFwidGF4QW1vdW50XCI6MTg4My4wLFwic2t1SWRcIjpcIjFfMTAwMFwiLFwibHZ0SWRcIjoxMTY4NH0ifQ.nAclaCSG5o2xD9ccUuWTn3g8nC8Z7_nIDtj_qbCyQ0M"


async def lad(c, id, server=None):
    body = ("voucherPricePoint.id=3&voucherPricePoint.price=19000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}"
            "&voucherTypeName=INFOLD_GAMES-LOVE_AND_DEEPSPACE&lvtId=11684&shopLang=id_ID"
            f"&dynamicSkuToken={_JWT1}&pricePointDynamicSkuToken={_JWT2}")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Love and Deepspace", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def mcgg(c, id, server=None):
    body = ("voucherPricePoint.id=997117&voucherPricePoint.price=1579"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={server or ''}"
            "&voucherTypeName=106-MAGIC_CHESS&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Magic Chess: Go Go",
                "id": id, "zone": server, "name": name}
    return {"success": False, "message": "Not found"}


async def ml(c, id, server=None):
    r = await c.get(f"https://mlbb-api.isan.eu.org/find?id={id}&zone={server or ''}")
    data = r.json()
    return {"success": True, "game": "Mobile Legends: Bang Bang",
            "id": id, "server": server,
            "name": data.get("name"), "country": data.get("countryName")}


async def pb(c, id, server=None):
    body = ("voucherPricePoint.id=54700&voucherPricePoint.price=11000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId="
            "&voucherTypeName=POINT_BLANK&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if name:
        return {"success": True, "game": "Point Blank", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def pgr(c, id, server=None):
    z = (server or "").lower()
    m = {"ap": ("Asia-Pacific", "5000"),
         "eu": ("Europe", "5001"),
         "na": ("North America", "5002")}
    if z not in m:
        return {"success": False, "message": "Bad request"}
    sn, sv = m[z]
    body = ("voucherPricePoint.id=259947&voucherPricePoint.price=15000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={sv}"
            "&voucherTypeName=PUNISHING_GRAY_RAVEN&shopLang=id_ID")
    data = await hit_coda(c, body)
    return {"success": True, "game": "Punishing: Gray Raven",
            "id": id, "server": sn, "name": _get_username(data)}


async def sm(c, id, server=None):
    body = ("voucherPricePoint.id=256513&voucherPricePoint.price=16000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId=global-release"
            "&voucherTypeName=SAUSAGE_MAN&shopLang=id_ID")
    data = await hit_coda(c, body)
    return {"success": True, "game": "Sausage Man",
            "id": id, "name": _get_username(data)}


async def sus(c, id, server=None):
    body = ("voucherPricePoint.id=266077&voucherPricePoint.price=13000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId="
            "&voucherTypeName=SUPER_SUS&shopLang=id_ID")
    data = await hit_coda(c, body)
    return {"success": True, "game": "Super Sus",
            "id": id, "name": _get_username(data)}


async def valo(c, id, server=None):
    body = ("voucherPricePoint.id=973634&voucherPricePoint.price=56000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}"
            "&voucherTypeName=VALORANT&voucherTypeId=109&gvtId=139&shopLang=id_ID")
    data = await hit_coda(c, body)
    if isinstance(data, dict) and data.get("success") is True:
        return {"success": True, "game": "VALORANT",
                "id": id, "server": "Indonesia", "name": _get_username(data)}
    if isinstance(data, dict) and data.get("errorCode") == -200:
        return {"success": True, "game": "VALORANT", "id": id, "name": id}
    return {"success": False, "message": "Not found"}


async def zzz(c, id, server=None):
    p = id[:2]
    m = {"10": ("America", "prod_gf_us"),
         "13": ("Asia", "prod_gf_jp"),
         "15": ("Europe", "prod_gf_eu"),
         "17": ("SAR (Taiwan, Hong Kong, Macao)", "prod_gf_sg")}
    if p not in m:
        return {"success": False, "message": "Bad request"}
    sn, sv = m[p]
    body = ("voucherPricePoint.id=946399&voucherPricePoint.price=16000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.userId={id}&user.zoneId={sv}"
            "&voucherTypeName=ZENLESS_ZONE_ZERO&shopLang=id_ID")
    data = await hit_coda(c, body)
    return {"success": True, "game": "Zenless Zone Zero",
            "id": id, "server": sn, "name": _get_username(data)}


# ═════════════════════════════════════════════════════════════
# Router game — BARU
# ═════════════════════════════════════════════════════════════

async def eightball(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=272564"
            "&voucherPricePoint.price=14000.0000"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=EIGHT_BALL_POOL&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _extract_nickname(data, [
        "confirmationFields.roles.0.role",
        "confirmationFields.username",
    ])
    if _coda_ok(data) and name:
        return {"success": True, "game": "8 Ball Pool", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def aethergazer(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=2"
            "&voucherPricePoint.price=16650.0"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=547-AETHER_GAZER"
            "&voucherTypeId=524&gvtId=691&lvtId=11840&pcId=906&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _extract_nickname(data, [
        "confirmationFields.username",
        "confirmationFields.roles.0.role",
    ])
    if _coda_ok(data) and name:
        return {"success": True, "game": "Aether Gazer", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def autochess(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=203879"
            "&voucherPricePoint.price=150000.0000"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=AUTO_CHESS&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Auto Chess", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


_AZUR_SERVERS = {
    "avrora": ("Avrora", "1"), "lexington": ("Lexington", "2"),
    "sandy": ("Sandy", "3"), "washington": ("Washington", "4"),
    "amagi": ("Amagi", "5"), "littleenterprise": ("Little Enterprise", "6"),
}


async def azurlane(c, id, server=None):
    if not server:
        return {"success": False, "message": "Bad request"}
    key = re.sub(r"\s+", "", server).lower()
    if key not in _AZUR_SERVERS:
        return {"success": False, "message": "Not found"}
    sn, sv = _AZUR_SERVERS[key]
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=99665"
            "&voucherPricePoint.price=70000.0000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.zoneId={sv}"
            "&voucherTypeName=AZUR_LANE&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Azur Lane",
                "id": id, "server": sn, "name": name}
    return {"success": False, "message": "Not found"}


_BADLANDERS_SERVERS = {"global": ("Global", "11001"), "jf": ("JF", "21004")}


async def badlanders(c, id, server=None):
    if not server:
        return {"success": False, "message": "Bad request"}
    key = re.sub(r"\s+", "", server).lower()
    if key not in _BADLANDERS_SERVERS:
        return {"success": False, "message": "Not found"}
    sn, sv = _BADLANDERS_SERVERS[key]
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=333121"
            "&voucherPricePoint.price=2300.0000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.zoneId={sv}"
            "&voucherTypeName=BAD_LANDERS&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Badlanders",
                "id": id, "server": sn, "name": name}
    return {"success": False, "message": "Not found"}


async def barbarq(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=5145"
            "&voucherPricePoint.price=120000.0000"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=ELECSOUL&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _extract_nickname(data, ["confirmationFields.apiResult",
                                     "confirmationFields.username"])
    if _coda_ok(data) and name:
        return {"success": True, "game": "BarbarQ", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


_BASKETRIO_SERVERS = {
    "buzzerbeater": ("Buzzer Beater", "2"),
    "001": ("001", "3"),
    "002": ("002", "4"),
}


async def basketrio(c, id, server=None):
    if not server:
        return {"success": False, "message": "Bad request"}
    key = re.sub(r"\s+", "", server).lower()
    if key not in _BASKETRIO_SERVERS:
        return {"success": False, "message": "Not found"}
    sn, sv = _BASKETRIO_SERVERS[key]
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=147203"
            "&voucherPricePoint.price=832500.0000"
            "&voucherPricePoint.variablePrice=0"
            f"&user.zoneId={sv}"
            "&voucherTypeName=BASKETRIO&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Basketrio",
                "id": id, "server": sn, "name": name}
    return {"success": False, "message": "Not found"}


async def dragoncity(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=254206"
            "&voucherPricePoint.price=65000.0000"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=DRAGON_CITY&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Dragon City", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def hago(c, id, server=None):
    body = ("user.userId=" + id +
            "&voucherPricePoint.id=272113"
            "&voucherPricePoint.price=29700.0000"
            "&voucherPricePoint.variablePrice=0"
            "&user.zoneId="
            "&voucherTypeName=HAGO&shopLang=id_ID")
    data = await hit_coda(c, body)
    name = _get_username(data)
    if _coda_ok(data) and name:
        return {"success": True, "game": "Hago", "id": id, "name": name}
    return {"success": False, "message": "Not found"}


async def pubg(c, id, server=None):
    """PUBG Mobile via GoPay Games (server opsional)."""
    try:
        r = await c.post(
            "https://gopay.co.id/games/v1/order/user-account",
            json={"code": "PUBG_ID",
                  "data": {"userId": str(id), "zoneId": str(server or "")}},
            headers={"Content-Type": "application/json",
                     "Accept": "application/json"},
        )
        data = r.json()
    except Exception:
        return {"success": False, "message": "Not found"}
    nick = _extract_nickname(data, [
        "data.username", "data.userAccount", "data.nickname",
        "data.name", "username", "userAccount",
    ])
    if nick:
        return {"success": True, "game": "PUBG Mobile",
                "id": id, "server": server, "name": nick}
    return {"success": False, "message": "Not found"}


async def hok(c, id, server=None):
    return {"success": False,
            "message": "Honor of Kings belum didukung endpoint ini."}


async def fcmobile(c, id, server=None):
    return {"success": False,
            "message": "FC Mobile belum didukung endpoint ini."}


# ═════════════════════════════════════════════════════════════
# Registry
# ═════════════════════════════════════════════════════════════

GameFn = Callable[[httpx.AsyncClient, str, str | None], Awaitable[dict]]

GAMES: dict[str, dict[str, Any]] = {
    "aov":  {"name": "Arena of Valor",        "fn": aov,  "need": "id"},
    "codm": {"name": "Call of Duty Mobile",   "fn": codm, "need": "id"},
    "ff":   {"name": "Free Fire",             "fn": ff,   "need": "id"},
    "gi":   {"name": "Genshin Impact",        "fn": gi,   "need": "id"},
    "hi":   {"name": "Honkai Impact 3rd",     "fn": hi,   "need": "id"},
    "hsr":  {"name": "Honkai: Star Rail",     "fn": hsr,  "need": "id"},
    "la":   {"name": "LifeAfter",             "fn": la,   "need": "id_server",
             "hint_server": "zone (miskatown, sandcastle, ...)"},
    "lad":  {"name": "Love and Deepspace",    "fn": lad,  "need": "id"},
    "mcgg": {"name": "Magic Chess: Go Go",    "fn": mcgg, "need": "id_server",
             "hint_server": "zone (angka)"},
    "ml":   {"name": "Mobile Legends",        "fn": ml,   "need": "id_server",
             "hint_server": "zone (angka, mis. 2001)"},
    "pb":   {"name": "Point Blank",           "fn": pb,   "need": "id"},
    "pgr":  {"name": "Punishing: Gray Raven", "fn": pgr,  "need": "id_server",
             "hint_server": "ap / eu / na"},
    "sm":   {"name": "Sausage Man",           "fn": sm,   "need": "id"},
    "sus":  {"name": "Super Sus",             "fn": sus,  "need": "id"},
    "valo": {"name": "VALORANT",              "fn": valo, "need": "id"},
    "zzz":  {"name": "Zenless Zone Zero",     "fn": zzz,  "need": "id"},
    "8ball":        {"name": "8 Ball Pool",       "fn": eightball,     "need": "id"},
    "aethergazer":  {"name": "Aether Gazer",      "fn": aethergazer,   "need": "id"},
    "autochess":    {"name": "Auto Chess",        "fn": autochess,     "need": "id"},
    "azurlane":     {"name": "Azur Lane",         "fn": azurlane,      "need": "id_server",
                     "hint_server": "avrora/lexington/sandy/washington/amagi/littleenterprise"},
    "badlanders":   {"name": "Badlanders",        "fn": badlanders,    "need": "id_server",
                     "hint_server": "global / jf"},
    "barbarq":      {"name": "BarbarQ",           "fn": barbarq,       "need": "id"},
    "basketrio":    {"name": "Basketrio",         "fn": basketrio,     "need": "id_server",
                     "hint_server": "buzzerbeater/001/002"},
    "dragoncity":   {"name": "Dragon City",       "fn": dragoncity,    "need": "id"},
    "hago":         {"name": "Hago",              "fn": hago,          "need": "id"},
    "pubg":         {"name": "PUBG Mobile",       "fn": pubg,          "need": "id"},
    "hok":          {"name": "Honor of Kings",    "fn": hok,           "need": "id"},
    "fcmobile":     {"name": "FC Mobile",         "fn": fcmobile,      "need": "id"},
}


# ═════════════════════════════════════════════════════════════
# Runner (sync wrapper untuk Flask)
# ═════════════════════════════════════════════════════════════

async def _run_once(game_key: str, id_: str, server: str | None) -> dict:
    cfg = GAMES[game_key]
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            return await cfg["fn"](client, id_, server)
        except Exception as e:
            return {"success": False, "message": f"Error: {type(e).__name__}: {e}"}


def run_check(game_key: str, id_: str, server: str | None) -> dict:
    return asyncio.run(_run_once(game_key, id_, server))


# ═════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    return "?"


@app.route("/accang", methods=["GET"])
def accang():
    return jsonify({
        "success": True,
        "count": len(GAMES),
        "games": list(GAMES.keys()),
    })


def _parse_inputs() -> tuple[str | None, str | None, str | None, str | None]:
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        game = body.get("game") or request.args.get("game")
        id_ = body.get("id") or request.args.get("id")
        server = body.get("server") or request.args.get("server")
    else:
        game = request.args.get("game")
        id_ = request.args.get("id")
        server = request.args.get("server")
    return game, id_, server, None


@app.route("/check", methods=["GET", "POST"])
def check():
    game, id_, server, _ = _parse_inputs()
    if not game or not id_:
        return jsonify({
            "success": False,
            "message": "Parameter 'game' dan 'id' wajib diisi.",
        }), 400
    game = game.lower()
    if game not in GAMES:
        return jsonify({
            "success": False,
            "message": f"Game '{game}' tidak dikenal.",
        }), 404
    cfg = GAMES[game]
    if cfg["need"] == "id_server" and not server:
        return jsonify({
            "success": False,
            "message": f"Game '{game}' butuh parameter 'server'.",
            "hint_server": cfg.get("hint_server"),
        }), 400
    result = run_check(game, str(id_), server)
    return jsonify(result)


@app.route("/check/<game>", methods=["GET", "POST"])
def check_by_path(game: str):
    game = game.lower()
    if game not in GAMES:
        return jsonify({
            "success": False,
            "message": f"Game '{game}' tidak dikenal.",
        }), 404
    _, id_, server, _ = _parse_inputs()
    if not id_:
        return jsonify({
            "success": False,
            "message": "Parameter 'id' wajib diisi.",
        }), 400
    cfg = GAMES[game]
    if cfg["need"] == "id_server" and not server:
        return jsonify({
            "success": False,
            "message": f"Game '{game}' butuh parameter 'server'.",
            "hint_server": cfg.get("hint_server"),
        }), 400
    result = run_check(game, str(id_), server)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=False)
