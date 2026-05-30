from robyn import Router, Request, Response
import json
from services.action_registry import ActionRegistry

agent_router = Router()

@agent_router.get("/api/v1/agent/schemas")
async def get_action_schemas(request: Request):
    """
    语义意图捕获管线：
    向大模型暴露当前已挂载的所有原子化 Action Schemas
    """
    schemas = ActionRegistry.get_all_schemas()
    return Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        description=json.dumps({"schemas": schemas})
    )

@agent_router.post("/api/v1/agent/execute")
async def execute_action(request: Request):
    """
    语义意图到物理执行的转换：
    接收大模型 Function Calling 回传的 JSON，执行物理方法并返回结果。
    """
    try:
        body_str = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else request.body
        payload = json.loads(body_str) if body_str else {}
        
        action_name = payload.get("action")
        arguments = payload.get("arguments", {})
        
        if not action_name:
            return Response(status_code=400, headers={"Content-Type": "application/json"}, description='{"error": "Missing action name"}')
            
        print(f"[Agent Runtime] ⚡ 意图触发: {action_name} | Params: {arguments}")
        
        # 物理执行
        result = await ActionRegistry.execute(action_name, arguments)
        
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"action": action_name, "result": result})
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )

# [ANCHOR: CH-13] 手写 AI 工具闭环循环与 HTMX SSE 流式打字机落地
import asyncio
from services.llm_client import async_llm_chat_stream
import uuid
import urllib.parse
import html

# 本地轻量化会话轮询队列（FIFO）
_chat_sessions = {}

def render_chat_message(role, content):
    if role == "user":
        return f"<div class='chat-msg user' style='text-align: right; margin: 10px 0;'><span style='background: var(--bg-card); padding: 8px 12px; border-radius: 12px; display: inline-block; border: 1px solid var(--border-color);'>{html.escape(content)}</span></div>"
    return ""

def render_chat_ui():
    """AI 控制台的基础框架"""
    return """
    <div style="display: flex; flex-direction: column; height: calc(100vh - 80px); width: 100%; max-width: 900px; background: rgba(27, 33, 47, 0.7); border: 1px solid var(--border-color); border-radius: 16px; padding: 24px; box-sizing: border-box; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);">
        <h2 style="margin-top: 0; color: var(--accent-color); border-bottom: 1px solid var(--border-color); padding-bottom: 12px; display: flex; justify-content: space-between;">
            <span>🤖 AI 控制台</span>
            <span style="font-size: 0.8rem; color: var(--text-secondary); font-weight: normal; margin-top: 8px;">(Local OLLAMA ReAct)</span>
        </h2>
        
        <div id="chat-history" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding: 12px 0;">
            <div style="text-align: center; color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem;">会话初始化完成。等待物理指令...</div>
        </div>

        <form hx-post="/api/v1/agent/send" 
              hx-target="#chat-history" 
              hx-swap="beforeend" 
              hx-on="htmx:afterRequest: this.reset()"
              style="display: flex; gap: 12px; margin-top: 16px;">
            <input type="text" name="msg" placeholder="输入指令，例如：当前的绝对物理时间是多少？" required 
                   style="flex: 1; background: #0b0e14; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 16px; color: var(--text-primary); outline: none; transition: border-color 0.3s;" onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'">
            <button type="submit" style="background: var(--accent-color); color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='var(--accent-hover)'" onmouseout="this.style.background='var(--accent-color)'">发送指令</button>
        </form>
    </div>
    """

@agent_router.get("/api/v1/agent/chat_ui")
def get_chat_ui(request: Request):
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=render_chat_ui())

@agent_router.post("/api/v1/agent/send")
def handle_send_message(request: Request):
    body_str = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else request.body
    parsed = urllib.parse.parse_qs(body_str)
    user_msg = parsed.get("msg", [""])[0]
    
    if not user_msg:
        return Response(status_code=400, headers={"Content-Type": "text/html"}, description="")

    msg_id = uuid.uuid4().hex[:8]
    encoded_msg = urllib.parse.quote(user_msg)
    
    # 注入用户气泡，并隐式挂载 SSE 触发器
    response_html = f"""
    {render_chat_message("user", user_msg)}
    <div id="sse-wrapper-{msg_id}">
        <div hx-ext="sse" sse-connect="/api/v1/agent/chat_sse?msg={encoded_msg}&msg_id={msg_id}" sse-swap="message" hx-swap="beforeend">
        </div>
    </div>
    """
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=response_html)

@agent_router.get("/api/v1/agent/chat_sse")
async def chat_sse_endpoint(request: Request):
    session_id = request.queries.get("session_id", ["default"])[0]
    user_msg = request.queries.get("msg", [""])[0]
    msg_id = request.queries.get("msg_id", [""])[0]
    
    user_msg = urllib.parse.unquote(user_msg)
    
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = [
            {"role": "system", "content": "你是 ERTH Assistant，一台冷酷、精准、极简的超级 AI 架构机。当前工作在绝对零 JS 的物理环境中。如果用户索要工具信息或请求动作，你必须严格使用提供的 tools 架构去执行！回答需冷酷简短，具备赛博朋克极客风格。"}
        ]
        
    session_hist = _chat_sessions[session_id]
    session_hist.append({"role": "user", "content": user_msg})
    
    # 防止上下文爆炸
    if len(session_hist) > 21:
        _chat_sessions[session_id] = [session_hist[0]] + session_hist[-20:]

    async def sse_generator():
        yield f"data: <div class='chat-msg ai' style='margin: 10px 0;'><div style='border-left: 2px solid var(--accent-color); padding-left: 10px; background: rgba(59, 130, 246, 0.05); padding: 12px; border-radius: 0 8px 8px 0; white-space: pre-wrap; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; line-height: 1.5;'>\n\n"
        
        while True:
            # 获取全量可用动作雷达
            tools = [{"type": "function", "function": schema} for schema in ActionRegistry.get_all_schemas()]
            
            response = await async_llm_chat_stream(
                messages=session_hist,
                tools=tools if tools else None
            )
            
            if response.is_tool_call:
                # 触发物理劫持
                tool_name = response.tool_name
                tool_args = response.tool_args
                
                log_msg = f"&gt; [System] 物理动作调用截获: {tool_name}"
                if tool_args:
                    log_msg += f" | Payload: {html.escape(str(tool_args))}"
                    
                yield f"data: <div style='color: var(--accent-color); font-family: monospace; font-size: 0.85rem; margin-bottom: 8px; border-bottom: 1px dashed var(--accent-color); padding-bottom: 4px;'>{log_msg}</div>\n\n"
                
                try:
                    result = await ActionRegistry.execute(tool_name, tool_args)
                    result_str = str(result)
                    # 也输出执行结果的 log
                    yield f"data: <div style='color: #10b981; font-family: monospace; font-size: 0.85rem; margin-bottom: 12px; opacity: 0.8;'>&gt; [System] 动作返回: {html.escape(result_str)[:200]}...</div>\n\n"
                except Exception as e:
                    result_str = f"Error: {str(e)}"
                    yield f"data: <div style='color: #ef4444; font-family: monospace; font-size: 0.85rem; margin-bottom: 12px;'>&gt; [System] 执行崩溃: {html.escape(result_str)}</div>\n\n"
                
                # 结果回充给大模型
                session_hist.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": response.tool_id, "type": "function", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}]
                })
                session_hist.append({
                    "role": "tool",
                    "tool_call_id": response.tool_id,
                    "name": tool_name,
                    "content": result_str
                })
                continue
            
            else:
                # 文本决议流式渲染
                async for chunk in response.text_stream():
                    yield f"data: {html.escape(chunk)}\n\n"
                
                yield "data: </div></div>\n\n"
                session_hist.append({"role": "assistant", "content": response.final_text})
                
                # 动态 OOB 销毁 SSE 连接器，关闭流
                yield f"data: <div id='sse-wrapper-{msg_id}' hx-swap-oob='true'></div>\n\n"
                break

    return Response(
        status_code=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        },
        description=sse_generator()
    )
