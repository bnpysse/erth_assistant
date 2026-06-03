# [ANCHOR: CH-09]
# 生产级非阻塞拉取逻辑与错误物理退守
import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_weather_async() -> dict:
    """
    异步非阻塞拉取天气微服务数据，配置 500ms 超时。
    如果网络不可达或发生超时，采用物理影子降级退守机制，充填默认字典载荷。
    """
    # 模拟外部微服务 API 地址
    url = "http://127.0.0.1:9999/api/mock/weather"
    default_weather = {
        "status": "success",
        "data": {
            "location": "北京 (Beijing)",
            "condition": "晴 (Sunny)",
            "temperature": 26.5,
            "updated_epoch": 1716883200
        }
    }
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            response = await client.get(url)
            if response.status_code == 200:
                payload = response.json()
                # 校验以防格式不匹配
                if isinstance(payload, dict) and "data" in payload:
                    return payload
            return default_weather
    except Exception as e:
        logger.warning(f"天气 API 拉取超时或不可达，执行物理影子降级退守。异常信息: {e}")
        return default_weather

async def fetch_flight_async() -> dict:
    """
    异步非阻塞拉取航班动态数据，配置 500ms 超时。
    若遭遇外部断网或响应假死，拉取本地默认载荷以规避主进程阻塞。
    """
    # 模拟外部航班动态 API 地址
    url = "http://127.0.0.1:9999/api/mock/flight"
    default_flight = {
        "flight_no": "CA1501",
        "status": "已起飞 (DEPARTED)",
        "eta": "10:30",
        "gate": "T3-C08"
    }
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            response = await client.get(url)
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict) and "flight_no" in payload:
                    return payload
            return default_flight
    except Exception as e:
        logger.warning(f"航班 API 拉取超时或不可达，执行物理影子降级退守。异常信息: {e}")
        return default_flight
# [ANCHOR_END: CH-09]
