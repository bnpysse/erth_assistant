# [ANCHOR: CH-04]
# Description: Robyn 后端边车服务入口，引入基于 Opaque Token 的鉴权拦截中间件与 CORS 许可白名单，锁死物理通信权限。
# Status: Verified

import os
from robyn import Robyn, Request, Response, ALLOW_CORS
from robyn.types import PathParams
from db import (
    init_db, engine, Todo, get_active_todos, add_todo, toggle_todo_status, soft_delete_todo,
    Journal, get_latest_journal, get_journal_history, get_specific_journal, create_journal, soft_delete_journal
)
from sqlmodel import Session, select
import json
import markdown
from services.clipboard_washer import start_clipboard_monitor

app = Robyn(__file__)

# 在系统启动的破晓时刻，读取前端主进程静默注入的密钥
AGENT_SECRET_TOKEN = os.environ.get("AGENT_SECRET_TOKEN")

@app.before_request()
def auth_middleware(request: Request):
    # 跨域预检放行：如果是 OPTIONS 请求，必须直接放行给底层的路由器，规避管线锁死
    if request.method == "OPTIONS":
        return request
        
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    expected_token = f"Bearer {AGENT_SECRET_TOKEN}"
    
    # 针对 SSE 长连接（EventSource 原生不支持携带自定义 Header），支持在 Query 中携带 Token
    query_token = request.query_params.get("token", "")
    if not query_token:
        query_token = ""
    
    # 强制比对身份令牌，拦截非法流量并响应 403
    if auth_header == expected_token or query_token == AGENT_SECRET_TOKEN:
        return request
        
    return Response(
        status_code=403,
        headers={"Content-Type": "application/json"},
        description='{"error": "Forbidden: Invalid or Missing Opaque Token"}'
    )

# 启用官方 CORS，并显式放行授权及 HTMX 的全套特征 Headers
ALLOW_CORS(app, origins=["*"], headers=[
    "Authorization", "Content-Type", 
    "hx-target", "hx-current-url", "hx-request", "hx-trigger", "hx-trigger-name"
])

@app.startup_handler
async def startup():
    """后端点火时自动初始化本地 libSQL 数据基盘"""
    try:
        await init_db()
        print("[Robyn Backend] Local-First db基盘筑底成功！")
        start_clipboard_monitor()
    except Exception as e:
        print(f"[ERROR] 数据库基盘初始化失败: {e}")

@app.get("/api/v1/health")
async def health_check(request: Request):
    """
    心跳健康检查
    -----------
    不仅返回服务状态，更深入数据层执行连通性测试，向主进程上报真实状态
    """
    try:
        with Session(engine) as session:
            statement = select(Todo).where(Todo.is_deleted == 0).limit(1)
            result = session.exec(statement).first()
            if result:
                status = "success"
                db_msg = f"Connected. Active sentinel title: {result.title}"
            else:
                status = "warning"
                db_msg = "Connected, but no active tasks found."
                
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps({
                    "status": status,
                    "data": {
                        "service": "robyn-sidecar",
                        "database": "sqlmodel",
                        "message": db_msg
                    }
                })
            )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({
                "status": "error",
                "message": f"Database unavailable: {str(e)}"
            })
        )

@app.get("/ping")
def ping(request: Request):
    """Watchdog 看门狗专属心跳探测端点，极低开销"""
    return Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        description=json.dumps({"status": "pong"})
    )

import urllib.parse

def get_request_body_params(request: Request) -> dict:
    """智能解析请求体，兼容 application/json 与 application/x-www-form-urlencoded"""
    # 应对不同版本/内核对 Header 大小写敏感的问题
    content_type = request.headers.get("Content-Type") or request.headers.get("content-type") or request.headers.get("Content-type") or ""
    body_str = ""
    if isinstance(request.body, (bytes, bytearray)):
        body_str = request.body.decode("utf-8")
    elif isinstance(request.body, str):
        body_str = request.body

    if "application/x-www-form-urlencoded" in content_type:
        parsed = urllib.parse.parse_qs(body_str)
        return {k: v[0] for k, v in parsed.items()}
    else:
        try:
            return json.loads(body_str) if body_str else {}
        except Exception:
            # 极限兜底：如果 JSON 解析失败（通常因为 WebKit 发送了奇怪的 Header 导致 Content-Type 没被捕获），
            # 且 body 实际上是 urlencoded，则强行使用 parse_qs 解析
            parsed = urllib.parse.parse_qs(body_str)
# [ANCHOR: CH-07]

def render_task_fragment(todo: dict) -> str:
    """将单个待办事项渲染为超媒体 HTML 碎片"""
    todo_id = todo["id"]
    title = todo["title"]
    is_completed = todo["is_completed"]
    
    completed_class = "completed" if is_completed == 1 else ""
    checkmark = "✓" if is_completed == 1 else ""
    text_completed_class = "completed" if is_completed == 1 else ""
    
    return f"""
    <li class="todo-item">
        <div class="todo-item-left">
            <button hx-put="/api/v1/todos/{todo_id}/toggle" 
                    hx-target="closest li" 
                    hx-swap="outerHTML" 
                    class="todo-toggle-btn {completed_class}">
                {checkmark}
            </button>
            <span class="todo-text {text_completed_class}">{title}</span>
        </div>
        <button hx-delete="/api/v1/todos/{todo_id}" 
                hx-target="closest li" 
                hx-swap="outerHTML" 
                class="todo-btn-delete">
            ✕
        </button>
    </li>
    """

def render_todo_center(todos: list) -> str:
    """渲染完整的待办中心面板 HTML 碎片"""
    list_items = "".join(render_task_fragment(todo) for todo in todos)
    return f"""
    <div class="todo-card">
        <h2>
            <span>📅 待办中心</span>
            <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-secondary);">共 {len(todos)} 项任务</span>
        </h2>
        
        <!-- 零 JS 超媒体新增表单 -->
        <form hx-post="/api/v1/todos" 
              hx-target="#todo-list" 
              hx-swap="afterbegin" 
              class="todo-form"
              hx-on="htmx:afterRequest: this.reset()">
            <input type="text" 
                   name="title" 
                   placeholder="记录你的下一个伟大构想..." 
                   class="todo-input" 
                   required 
                   autocomplete="off" />
            <button type="submit" class="todo-btn-add">添加</button>
        </form>

        <!-- 滚动任务列表 -->
        <ul id="todo-list" class="todo-list">
            {list_items}
        </ul>
    </div>
    """

# [ANCHOR: CH-06]

@app.get("/api/v1/todos")
async def get_todos(request: Request):
    try:
        todos = await get_active_todos()
        is_htmx = request.headers.get("hx-request") == "true"
        
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_todo_center(todos)
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todos)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 16px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

async def handle_create_todo(request: Request):
    try:
        body = get_request_body_params(request)
        title = body.get("title")
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not title:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing field: title</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing field: title"})
                )
                
        todo = await add_todo(title)
        print(f"[Database] 数据已沉淀入库: {todo['id'][:8]} - {title}")
        
        if is_htmx:
            return Response(
                status_code=201,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_task_fragment(todo)
            )
        else:
            return Response(
                status_code=201,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todo)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.post("/api/v1/todos")
async def create_todo_v1(request: Request):
    return await handle_create_todo(request)

@app.post("/api/v1/tasks")
async def create_task_v1(request: Request):
    return await handle_create_todo(request)

async def handle_toggle_todo(request: Request, id: str):
    try:
        todo_id = id
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not todo_id:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing parameter: id</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing parameter: id"})
                )
                
        todo = await toggle_todo_status(todo_id)
        if todo is None:
            if is_htmx:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Todo not found</div>'
                )
            else:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Todo not found or already deleted"})
                )
                
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_task_fragment(todo)
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todo)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.put("/api/v1/todos/:id/toggle")
async def toggle_todo_v1(request: Request, id: str):
    return await handle_toggle_todo(request, id)

@app.put("/api/v1/tasks/:id/toggle")
async def toggle_task_v1(request: Request, id: str):
    return await handle_toggle_todo(request, id)

async def handle_delete_todo(request: Request, id: str):
    try:
        todo_id = id
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not todo_id:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing parameter: id</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing parameter: id"})
                )
                
        success = await soft_delete_todo(todo_id)
        if not success:
            if is_htmx:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Todo not found or already deleted</div>'
                )
            else:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Todo not found or already deleted"})
                )
                
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=""
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"status": "success", "message": f"Todo {todo_id} soft deleted"})
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.delete("/api/v1/todos/:id")
async def delete_todo_v1(request: Request, id: str):
    return await handle_delete_todo(request, id)

@app.delete("/api/v1/tasks/:id")
async def delete_task_v1(request: Request, id: str):
    return await handle_delete_todo(request, id)

# [ANCHOR: CH-08]
# ==================== Journal / Notebook Handlers ====================

def render_journal_history_fragment(journal: dict) -> str:
    return f"""
    <div class="group flex items-center justify-between" style="padding: 12px; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; justify-content: space-between;">
        <button hx-get="/api/v1/journals/{journal['id']}" hx-swap="none" style="background: none; border: none; color: var(--text-primary); cursor: pointer; text-align: left; flex: 1; padding: 0; margin: 0; outline: none;">
            📝 {journal['title']}
        </button>
        <button 
            hx-delete="/api/v1/journals/{journal['id']}" 
            hx-target="closest div.group" 
            hx-swap="outerHTML"
            style="background: none; border: none; cursor: pointer; opacity: 0; padding: 4px; font-size: 1.1rem;"
            onmouseover="this.style.opacity=1"
            onmouseout="this.style.opacity=0"
            title="删除此纪要"
        >
            🗑️
        </button>
    </div>
    """

def render_notebook_center(journals: list) -> str:
    """渲染全景日志 HTML 骨架"""
    history_html = "".join(render_journal_history_fragment(j) for j in journals)
    return f"""
    <div style="display: flex; gap: 24px; width: 100%; max-width: 1400px; height: calc(100vh - 80px); animation: fadeIn 0.4s ease-out;">
        <!-- 左侧：历史纪要 -->
        <div style="flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; display: flex; flex-direction: column; overflow: hidden; min-width: 260px;">
            <h3 style="color: var(--accent-color); margin-top: 0;">📚 历史纪要</h3>
            <div id="journal-history" hx-get="/api/v1/journals/history" hx-trigger="load, journalSaved from:body" hx-on::response-error="this.innerHTML = '<div style=\\'color: #ef4444;\\'>加载失败</div>'" style="overflow-y: auto; flex: 1;">
                {history_html}
            </div>
        </div>

        <!-- 中间：编辑器 -->
        <div style="flex: 2; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; display: flex; flex-direction: column; min-width: 350px;">
            <div hx-get="/api/v1/journals/latest" hx-trigger="load" class="hidden" style="display: none;"></div>
            <form hx-post="/api/v1/journals" hx-swap="none" style="display: flex; flex-direction: column; height: 100%; gap: 16px;">
                <input id="journal-title" type="text" name="title" placeholder="输入纪要标题..." required style="background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; color: var(--text-primary); font-size: 1.1rem; outline: none; transition: border-color 0.3s;" onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'" />
                <textarea id="journal-editor" name="content" placeholder="使用 Markdown 记录..." required 
                    hx-post="/api/v1/markdown/preview" 
                    hx-trigger="keyup changed delay:500ms, load" 
                    hx-target="#markdown-preview"
                    style="flex: 1; background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; color: var(--text-primary); font-size: 0.95rem; outline: none; resize: none; font-family: monospace; transition: border-color 0.3s;"
                    onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'"
                ></textarea>
                <button type="submit" style="background: var(--accent-color); color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2); transition: all 0.3s;">沉淀入库 (Save)</button>
            </form>
        </div>

        <!-- 右侧：Markdown 预览 -->
        <div style="flex: 2; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; display: flex; flex-direction: column; overflow-y: auto; min-width: 400px;">
            <h3 style="color: var(--accent-color); margin-top: 0; margin-bottom: 16px;">👁️ 实时预览</h3>
            <div id="markdown-preview" style="color: var(--text-primary); line-height: 1.6; padding-right: 12px; word-wrap: break-word;">
                <p style="color: var(--text-secondary);">等待编译 HTML 碎片...</p>
            </div>
        </div>
    </div>
    """

@app.get("/api/v1/notebook")
async def get_notebook(request: Request):
    """全景日志主视图"""
    is_htmx = request.headers.get("hx-request") == "true"
    journals = await get_journal_history()
    
    if is_htmx:
        return Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            description=render_notebook_center(journals)
        )
    else:
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"message": "Notebook structure"})
        )

@app.post("/api/v1/markdown/preview")
async def markdown_preview(request: Request):
    """编译 Markdown 并返回 HTML"""
    body = get_request_body_params(request)
    content = body.get("content", "")
    html = markdown.markdown(content, extensions=['fenced_code', 'tables'])
    
    return Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        description=html
    )

def render_oob_editor(title: str, content: str) -> str:
    # 提取了可复用部分，防止前端样式断开
    return f"""
    <input id="journal-title" type="text" name="title" value="{title}" placeholder="输入纪要标题..." required style="background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; color: var(--text-primary); font-size: 1.1rem; outline: none; transition: border-color 0.3s;" onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'" hx-swap-oob="outerHTML">
    <textarea id="journal-editor" name="content" placeholder="使用 Markdown 记录..." required 
        hx-post="/api/v1/markdown/preview" 
        hx-trigger="keyup changed delay:500ms, load" 
        hx-target="#markdown-preview"
        hx-swap="innerHTML"
        style="flex: 1; background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; color: var(--text-primary); font-size: 0.95rem; outline: none; resize: none; font-family: monospace; transition: border-color 0.3s;"
        onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'"
        hx-swap-oob="outerHTML"
    >{content}</textarea>
    """

@app.get("/api/v1/journals/latest")
async def fetch_latest_journal_route(request: Request):
    latest = await get_latest_journal()
    title = latest["title"] if latest else ""
    content = latest["content"] if latest else ""
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=render_oob_editor(title, content))

@app.get("/api/v1/journals/:id")
async def fetch_specific_journal_route(request: Request, id: str):
    journal_id = id
    journal = await get_specific_journal(journal_id)
    title = journal["title"] if journal else ""
    content = journal["content"] if journal else ""
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=render_oob_editor(title, content))

@app.get("/api/v1/journals/history")
async def fetch_journal_history_route(request: Request):
    journals = await get_journal_history()
    html = "".join(render_journal_history_fragment(j) for j in journals)
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=html)

@app.post("/api/v1/journals")
async def handle_create_journal_route(request: Request):
    body = get_request_body_params(request)
    title = body.get("title", "")
    content = body.get("content", "")
    await create_journal(title, content)
    return Response(
        status_code=200, 
        headers={
            "Content-Type": "text/html; charset=utf-8", 
            "HX-Trigger": "journalSaved", 
            "Access-Control-Expose-Headers": "HX-Trigger"
        }, 
        description="保存成功"
    )

@app.delete("/api/v1/journals/:id")
async def delete_journal_route(request: Request, id: str):
    journal_id = id
    await soft_delete_journal(journal_id)
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description="")


# [ANCHOR: CH-09]
# 生产级非阻塞拉取逻辑与错误物理退守
from routes.pim_routes import pim_router
app.include_router(pim_router)
# [ANCHOR_END: CH-09]

# [ANCHOR: CH-12]
from routes.agent_routes import agent_router
app.include_router(agent_router)
# [ANCHOR_END: CH-12]

# [ANCHOR: CH-15]
from routes.plugin_routes import plugin_router
app.include_router(plugin_router)
# [ANCHOR_END: CH-15]


if __name__ == "__main__":
    # 使用 Port 0 启动，操作系统分配空闲随机端口，杜绝冲突硬编码
    # 真实运行端口会打印到 stdout 供前端捕获
    app.start(host="127.0.0.1", port=0)
