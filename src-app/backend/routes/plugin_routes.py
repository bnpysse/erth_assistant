# [ANCHOR: CH-15]
from robyn import SubRouter, Request, Response
from services.plugin_manager import (
    load_plugin, 
    unload_plugin, 
    get_loaded_plugins, 
    get_available_plugins,
    _plugin_registry
)

plugin_router = SubRouter(__name__)

def render_plugin_fragment(plugin_file: str, is_active: bool, logs: list = None) -> str:
    """渲染单个插件状态 HTML 碎片"""
    status_color = "#10b981" if is_active else "#64748b"
    status_text = "运行中" if is_active else "已停用"
    action = "unload" if is_active else "load"
    btn_text = "安全剥离" if is_active else "热插拔启动"
    btn_color = "#ef4444" if is_active else "#3b82f6"
    
    logs_html = ""
    if is_active and logs:
        logs_html = "<div style='margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 6px; font-family: monospace; font-size: 0.8rem; color: #a1a1aa;'>"
        for log in logs[-3:]: # 只展示最新3条
            logs_html += f"<div>{log}</div>"
        logs_html += "</div>"

    return f"""
    <div class="plugin-card" style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 16px; margin-bottom: 12px; transition: all 0.3s; animation: fadeIn 0.4s ease-out;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background-color: {status_color}; box-shadow: 0 0 8px {status_color};"></div>
                <h4 style="margin: 0; color: var(--text-primary); font-size: 1.05rem;">{plugin_file}</h4>
                <span style="font-size: 0.75rem; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; color: {status_color}">{status_text}</span>
            </div>
            <button hx-post="/api/v1/plugins/{action}/{plugin_file}"
                    hx-target="closest .plugin-card"
                    hx-swap="outerHTML"
                    style="background: {btn_color}; border: none; color: white; padding: 6px 12px; border-radius: 6px; font-size: 0.85rem; cursor: pointer; transition: all 0.2s;">
                {btn_text}
            </button>
        </div>
        {logs_html}
    </div>
    """

def render_plugin_dashboard() -> str:
    """渲染全景插件仪表盘 HTML 骨架"""
    available = get_available_plugins()
    loaded = get_loaded_plugins()
    
    cards = ""
    for p in available:
        mod_name = p.replace(".py", "")
        is_active = mod_name in loaded
        logs = _plugin_registry[mod_name]["context"].get_logs() if is_active else []
        cards += render_plugin_fragment(p, is_active, logs)
        
    if not cards:
        cards = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">沙箱内未发现可用插件，请放入 src-app/backend/plugins 目录。</div>'
        
    return f"""
    <div style="width: 100%; max-width: 800px; padding: 24px;">
        <h2 style="color: var(--text-primary); margin-top: 0; display: flex; align-items: center; gap: 8px;">
            🧩 生态热插拔控制台
        </h2>
        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 24px;">
            通过 <code>importlib</code> 动态挂载机制，无需重新编译或重启系统，即刻将功能模块空投至边车运行环境中。所有插件强制纳入隔离沙箱与路径洗涤防线。
        </p>
        <div id="plugin-list-container">
            {cards}
        </div>
    </div>
    """

@plugin_router.get("/api/v1/plugins/panel")
async def get_plugin_panel(request: Request):
    return Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        description=render_plugin_dashboard()
    )

@plugin_router.post("/api/v1/plugins/load/:name")
async def handle_load_plugin(request: Request, name: str = ""):
    # 兼容两种获取 path_params 的方式，防范不同 Robyn 版本的差异
    plugin_name = name or request.path_params.get("name")
    success = load_plugin(plugin_name)
    
    if not success:
        return Response(status_code=500, headers={"Content-Type": "text/html; charset=utf-8"}, description=f"<div style='color: red;'>挂载 {plugin_name} 失败！(涉嫌越权或存在致命语法错误)</div>")
        
    mod_name = plugin_name.replace(".py", "")
    logs = _plugin_registry[mod_name]["context"].get_logs()
    html = render_plugin_fragment(plugin_name, is_active=True, logs=logs)
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)

@plugin_router.post("/api/v1/plugins/unload/:name")
async def handle_unload_plugin(request: Request, name: str = ""):
    plugin_name = name or request.path_params.get("name")
    success = unload_plugin(plugin_name)
    
    if not success:
        return Response(status_code=500, headers={"Content-Type": "text/html; charset=utf-8"}, description=f"<div style='color: red;'>剥离 {plugin_name} 失败！</div>")
        
    html = render_plugin_fragment(plugin_name, is_active=False)
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)
