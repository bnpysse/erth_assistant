import os
import json
import httpx
import uuid
from pathlib import Path

# 尝试手动加载 .env 文件，防止 Bun 未注入环境变量
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key and val:
                    os.environ[key] = val

# 核心配置：通过环境变量实现云端与本地的无缝切换
LLM_MODE = os.environ.get("LLM_MODE", "cloud") # 默认切换到云端模式（本地算力测试完毕，开启云端体验）

# Local Ollama 配置
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")

# Cloud API 配置 (完全兼容 OpenAI 规范的任意云端，如 DeepSeek, 通义千问, GPT-4)
CLOUD_API_BASE = os.environ.get("CLOUD_API_BASE", "https://api.deepseek.com/v1")
CLOUD_API_KEY = os.environ.get("CLOUD_API_KEY", "YOUR_API_KEY")
CLOUD_MODEL = os.environ.get("CLOUD_MODEL", "deepseek-chat")

class StreamParser:
    """
    极简异步流解析器
    原生物理解析 OpenAI 兼容的 SSE 数据流。
    如果检测到 Function Calling 意图，原地穷尽截获；
    如果检测到纯文本内容，则交还控制权给上层进行流式直出。
    """
    def __init__(self, client: httpx.AsyncClient, response: httpx.Response):
        self.client = client
        self.response = response
        self.is_tool_call = False
        self.tool_name = None
        self.tool_args = {}
        self.tool_id = None
        self.final_text = ""
        self._raw_args_str = ""
        self.buffer = []
        self._line_iter = self.response.aiter_lines()

    async def pre_consume(self):
        """预读判决：拦截并解析大模型的动作意图"""
        async for line in self._line_iter:
            line = line.strip()
            if not line or line.startswith(":"): 
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]": 
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    if "tool_calls" in delta and delta["tool_calls"]:
                        self.is_tool_call = True
                        tc = delta["tool_calls"][0]
                        if "id" in tc and tc["id"]: 
                            self.tool_id = tc["id"]
                        if "function" in tc:
                            if "name" in tc["function"] and tc["function"]["name"]:
                                self.tool_name = tc["function"]["name"]
                            if "arguments" in tc["function"]:
                                self._raw_args_str += tc["function"]["arguments"]
                    elif "content" in delta and delta.get("content") is not None:
                        content_val = delta["content"]
                        self.buffer.append(content_val)
                        if content_val and not self.is_tool_call:
                            # 只有当出现了实质性的纯文本流（非空），才判定为放弃劫持
                            break
                except Exception as e:
                    pass
                    
        if self.is_tool_call:
            # 如果是动作意图，继续吃掉整个流以收集完整的 JSON 参数
            async for line in self._line_iter:
                line = line.strip()
                if not line or line.startswith(":"): 
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]": 
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        if "tool_calls" in delta and delta["tool_calls"]:
                            tc = delta["tool_calls"][0]
                            if "function" in tc and "arguments" in tc["function"]:
                                self._raw_args_str += tc["function"]["arguments"]
                    except Exception as e:
                        pass
            
            if not self.tool_id: 
                self.tool_id = f"call_{uuid.uuid4().hex[:8]}"
            try:
                self.tool_args = json.loads(self._raw_args_str) if self._raw_args_str else {}
            except Exception as e:
                print(f"[LLM] 格式幻觉警告 - 工具参数解析失败: {e}")
                self.tool_args = {}
            # 动作参数截获完毕，关闭底层 Socket
            await self.close()

    async def text_stream(self):
        """向上层交付纯文本流，同时兼顾后发制人的 tool_calls"""
        # 吐出预读时截获的文本碎块
        for text in self.buffer:
            self.final_text += text
            yield text
            
        async for line in self._line_iter:
            line = line.strip()
            if not line or line.startswith(":"): 
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]": 
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    
                    if "tool_calls" in delta and delta["tool_calls"]:
                        self.is_tool_call = True
                        tc = delta["tool_calls"][0]
                        if "id" in tc and tc["id"]: 
                            self.tool_id = tc["id"]
                        if "function" in tc:
                            if "name" in tc["function"] and tc["function"]["name"]:
                                self.tool_name = tc["function"]["name"]
                            if "arguments" in tc["function"]:
                                self._raw_args_str += tc["function"]["arguments"]

                    if "content" in delta and delta.get("content") is not None:
                        content = delta["content"]
                        self.final_text += content
                        yield content
                except Exception:
                    pass
        await self.close()
        
        # 结束后统一解析参数
        if self.is_tool_call:
            if not self.tool_id: 
                self.tool_id = f"call_{uuid.uuid4().hex[:8]}"
            try:
                self.tool_args = json.loads(self._raw_args_str) if self._raw_args_str else {}
            except Exception as e:
                print(f"[LLM] 格式幻觉警告 - 工具参数解析失败: {e}")
                self.tool_args = {}

    async def close(self):
        await self.response.aclose()
        await self.client.aclose()


async def async_llm_chat_stream(messages: list, tools: list = None) -> StreamParser:
    """
    点燃大模型推理火花
    构建物理请求报文，发起带有系统工具集限制的异步请求。
    """
    is_cloud = (LLM_MODE.lower() == "cloud")
    
    api_base = CLOUD_API_BASE if is_cloud else OLLAMA_BASE_URL
    model_name = CLOUD_MODEL if is_cloud else OLLAMA_MODEL
    api_key = CLOUD_API_KEY if is_cloud else "ollama"

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True
    }
    if tools:
        payload["tools"] = tools

    print(f"[LLM] ⚡ Ignition: mode={LLM_MODE}, model={model_name}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    client = httpx.AsyncClient(timeout=None)
    req = client.build_request("POST", f"{api_base}/chat/completions", headers=headers, json=payload)
    resp = await client.send(req, stream=True)
    
    parser = StreamParser(client, resp)
    # 不再预读拦截，全部交由 text_stream 边读边解
    return parser
