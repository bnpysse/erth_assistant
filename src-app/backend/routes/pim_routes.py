# [ANCHOR: CH-10]
# 生产级非阻塞拉取逻辑与多维看板状态漫游 (OOB)
import os
from robyn import SubRouter, Request, Response
from services.pim import fetch_weather_async, fetch_flight_async
from db import add_todo, toggle_todo_status

# 初始化 PIM 模块的独立子路由器，挂载至 /api/v1/pim
pim_router = SubRouter(__name__, prefix="/api/v1/pim")

# 抽取 Tab 按钮模板，以便后端返回 HTML 碎片时利用 OOB (Out-of-Band) 机制同步更新 Tab 状态
def get_tabs_html(active_tab: str) -> str:
    def tab_style(is_active: bool) -> str:
        base_style = "cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; transition: all 0.25s ease;"
        if is_active:
            return base_style + " color: var(--text-primary); background-color: rgba(59, 130, 246, 0.15); border: 1px solid var(--accent-color); box-shadow: 0 0 12px rgba(59, 130, 246, 0.1);"
        else:
            return base_style + " color: var(--text-secondary); background: none; border: 1px solid transparent;"
    
    return f"""
    <div id="tab-weather" class="flex {'active' if active_tab == 'weather' else ''}" hx-get="/api/v1/pim/weather" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="{tab_style(active_tab == 'weather')}">
        ⛅ 天气状况
    </div>
    <div id="tab-flight" class="flex {'active' if active_tab == 'flight' else ''}" hx-get="/api/v1/pim/flight" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="{tab_style(active_tab == 'flight')}">
        ✈️ 航班动态
    </div>
    <div id="tab-schedule" class="flex {'active' if active_tab == 'schedule' else ''}" hx-get="/api/v1/pim/schedule" hx-target="#pim-panel" hx-swap="innerHTML" hx-swap-oob="outerHTML" style="{tab_style(active_tab == 'schedule')}">
        📅 待办日程
    </div>
    """

@pim_router.get("/panel")
async def get_pim_panel(request: Request):
    """
    读取并返回 PIM 面板 HTML 骨架，用作超媒体初始容器。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    component_path = os.path.join(base_dir, "..", "frontend", "src", "components", "pim_dashboard.html")
    
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
            description=f"<div style='color: #ef4444; padding: 20px;'>无法加载 PIM 看板组件: {e}</div>"
        )

@pim_router.get("/weather")
async def get_pim_weather(request: Request):
    """
    获取天气数据并返回 HTML 碎片，同时利用 OOB 更新 Tab 状态。
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
    {get_tabs_html('weather')}
    """
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)

@pim_router.get("/flight")
async def get_pim_flight(request: Request):
    """
    获取航班数据并返回 HTML 碎片，同时利用 OOB 更新 Tab 状态。
    """
    data = await fetch_flight_async()
    flight_no = data.get("flight_no", "N/A")
    status = data.get("status", "N/A")
    eta = data.get("eta", "N/A")
    gate = data.get("gate", "N/A")
    
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
    {get_tabs_html('flight')}
    """
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)

@pim_router.get("/schedule")
async def get_pim_schedule(request: Request):
    """
    获取日程安排面板，模拟返回带有状态红点的待办事项，同时利用 OOB 更新 Tab 状态。
    """
    html = f"""
    <!-- 日程安排卡片 -->
    <div id="schedule-item-1" style="width: 100%; display: flex; flex-direction: column; gap: 16px; animation: fadeIn 0.3s ease;">
        <div style="background: rgba(18, 22, 32, 0.5); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s ease;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="width: 12px; height: 12px; background: #ef4444; border-radius: 50%; box-shadow: 0 0 8px #ef4444;"></div>
                <div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary);">与统帅的战略级汇报会议</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">14:00 - 15:30 | 核心指挥室</div>
                </div>
            </div>
            <!-- 高维杀招触发器：hx-post 到完成端点 -->
            <button hx-post="/api/v1/pim/schedule/complete/1" 
                    hx-target="#schedule-item-1" 
                    hx-swap="outerHTML"
                    style="background: transparent; border: 1px solid var(--accent-color); color: var(--accent-color); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.2s ease;">
                标记完成
            </button>
        </div>
    </div>
    {get_tabs_html('schedule')}
    """
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)

@pim_router.post("/schedule/complete/:id")
async def complete_pim_schedule(request: Request):
    """
    完成日程项触发后：
    1. 局部重绘当前日程项为“已完成”状态（灰色、划线）。
    2. 利用 OOB 级联漫游，跨越 DOM 树精确消除左侧边栏的“活动小红点”。
    """
    item_id = request.path_params.get("id")
    
    # 物理数据防线：将日程强制写入数据库的待办中心并标记为已完成
    try:
        todo = await add_todo("与统帅的战略级汇报会议")
        await toggle_todo_status(todo["id"])
    except Exception as e:
        print(f"[PIM] 同步待办中心失败: {e}")
    
    # 局部更新日程项状态
    html = f"""
    <div id="schedule-item-{item_id}" style="width: 100%; display: flex; flex-direction: column; gap: 16px; animation: fadeIn 0.3s ease;">
        <div style="background: rgba(18, 22, 32, 0.2); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; display: flex; justify-content: space-between; align-items: center; opacity: 0.6;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="width: 12px; height: 12px; background: #10b981; border-radius: 50%;"></div>
                <div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-secondary); text-decoration: line-through;">与统帅的战略级汇报会议</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">14:00 - 15:30 | 已结束</div>
                </div>
            </div>
            <div style="color: #10b981; font-weight: 600; font-size: 0.95rem;">
                ✓ 任务归档
            </div>
        </div>
    </div>
    
    <!-- 高维杀招 (OOB)：跨树消灭左侧边栏的小红点 -->
    <span id="pim-sidebar-badge" hx-swap-oob="true" style="display: none;"></span>
    """
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)
# [ANCHOR_END: CH-10]
