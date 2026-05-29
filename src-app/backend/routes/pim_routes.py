# [ANCHOR: CH-09: ASYNC_PIM_SERVICE]
# 生产级非阻塞拉取逻辑与错误物理退守
import os
from robyn import SubRouter, Request, Response
from services.pim import fetch_weather_async, fetch_flight_async

# 初始化 PIM 模块的独立子路由器，挂载至 /api/v1/pim
pim_router = SubRouter(__name__, prefix="/api/v1/pim")

@pim_router.get("/panel")
async def get_pim_panel(request: Request):
    """
    读取并返回 PIM 面板 HTML 骨架，用作超媒体初始容器。
    """
    # 基于当前路由文件的物理路径，精确定位前端 components 目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    component_path = os.path.join(base_dir, "..", "frontend", "src", "components", "pim_tabs.html")
    
    try:
        with open(component_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            description=html_content
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "text/html; charset=utf-8"},
            description=f"<div style='color: #ef4444; padding: 20px;'>无法加载 PIM 选项卡面板组件: {e}</div>"
        )

@pim_router.get("/weather")
async def get_pim_weather(request: Request):
    """
    非阻塞获取天气数据，并直接组装为冷峻暗黑主题的 HTML 碎片返回。
    同时使用 HTMX 的 OOB Swaps（hx-swap-oob）机制无痛更新 Tab 按钮状态。
    """
    data = await fetch_weather_async()
    status_data = data.get("data", {})
    location = status_data.get("location", "Unknown")
    condition = status_data.get("condition", "Cloudy")
    temp = status_data.get("temperature", 0.0)
    epoch = status_data.get("updated_epoch", 0)
    
    html = f"""
    <!-- 天气卡片 -->
    <div style="width: 100%; display: flex; flex-direction: column; gap: 16px; animation: fadeIn 0.3s ease;">
        <div style="background: rgba(18, 22, 32, 0.5); border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.05em;">LOCATION</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: var(--text-primary);">{location}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 2.5rem; font-weight: 800; color: var(--accent-color); line-height: 1.1;">{temp}°C</div>
                <div style="font-size: 0.95rem; color: #10b981; font-weight: 600; margin-top: 4px;">{condition}</div>
            </div>
        </div>
        <div style="font-size: 0.8rem; color: var(--text-secondary); text-align: right;">
            数据更新时间戳: {epoch}
        </div>
    </div>

    <!-- 利用 OOB Swaps 进行 Tab 按钮状态的后端级联更新 -->
    <div id="tab-weather" class="flex active" hx-get="/api/v1/pim/weather" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; transition: all 0.25s ease; color: var(--text-primary); background-color: rgba(59, 130, 246, 0.15); border: 1px solid var(--accent-color); box-shadow: 0 0 12px rgba(59, 130, 246, 0.1);">
        ⛅ 天气状况
    </div>
    <div id="tab-flight" class="flex" hx-get="/api/v1/pim/flight" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; transition: all 0.25s ease; color: var(--text-secondary); background: none; border: 1px solid transparent;">
        ✈️ 航班动态
    </div>
    """
    return Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        description=html
    )

@pim_router.get("/flight")
async def get_pim_flight(request: Request):
    """
    非阻塞获取航班数据，返回 HTML 碎片。同样附带 OOB Tab 按钮更新逻辑。
    """
    data = await fetch_flight_async()
    flight_no = data.get("flight_no", "N/A")
    status = data.get("status", "N/A")
    eta = data.get("eta", "N/A")
    gate = data.get("gate", "N/A")
    
    # 状态警告色：延误使用红色，正常使用绿色
    status_color = "#ef4444" if "DELAYED" in status or "延误" in status else "#10b981"
    
    html = f"""
    <!-- 航班动态卡片 -->
    <div style="width: 100%; display: flex; flex-direction: column; gap: 16px; animation: fadeIn 0.3s ease;">
        <div style="background: rgba(18, 22, 32, 0.5); border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.05em;">FLIGHT NO</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: var(--text-primary);">{flight_no}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 2rem; font-weight: 800; color: {status_color}; line-height: 1.1;">{status}</div>
                <div style="font-size: 0.95rem; color: var(--text-secondary); margin-top: 4px;">预计到达: {eta} | 登机口: {gate}</div>
            </div>
        </div>
    </div>

    <!-- 利用 OOB Swaps 进行 Tab 按钮状态的后端级联更新 -->
    <div id="tab-weather" class="flex" hx-get="/api/v1/pim/weather" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; transition: all 0.25s ease; color: var(--text-secondary); background: none; border: 1px solid transparent;">
        ⛅ 天气状况
    </div>
    <div id="tab-flight" class="flex active" hx-get="/api/v1/pim/flight" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; transition: all 0.25s ease; color: var(--text-primary); background-color: rgba(59, 130, 246, 0.15); border: 1px solid var(--accent-color); box-shadow: 0 0 12px rgba(59, 130, 246, 0.1);">
        ✈️ 航班动态
    </div>
    """
    return Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        description=html
    )
# [ANCHOR_END: CH-09: ASYNC_PIM_SERVICE]
