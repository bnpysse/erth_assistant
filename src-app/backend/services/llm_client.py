import os
import json
import httpx
import uuid

# 使用 Qwen 3.5 9b 作为后备模型。统帅可随时通过 OLLAMA_MODEL="codeqwen:7b" 覆写
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")

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

    async def pre_consume(self):
        """预读判决：拦截并解析大模型的动作意图"""
        async for line in self.response.aiter_lines():
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
                        self.buffer.append(delta["content"])
                        if not self.is_tool_call:
                            # 是纯文本流，放弃劫持，直接中断预读
                            break
                except Exception as e:
                    pass
                    
        if self.is_tool_call:
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
        """向上层交付纯文本流"""
        # 吐出预读时截获的文本碎块
        for text in self.buffer:
            self.final_text += text
            yield text
            
        # 继续排干剩余的流
        if not self.is_tool_call:
            async for line in self.response.aiter_lines():
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
                        if "content" in delta and delta.get("content") is not None:
                            content = delta["content"]
                            self.final_text += content
                            yield content
                    except Exception:
                        pass
            await self.close()

    async def close(self):
        await self.response.aclose()
        await self.client.aclose()


async def async_llm_chat_stream(messages: list, tools: list = None) -> StreamParser:
    """
    点燃大模型推理火花
    构建物理请求报文，发起带有系统工具集限制的异步请求。
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True
    }
    if tools:
        payload["tools"] = tools

    print(f"[LLM] ⚡ Ignition: model={OLLAMA_MODEL}")
    client = httpx.AsyncClient(timeout=120.0)
    req = client.build_request("POST", f"{OLLAMA_BASE_URL}/chat/completions", json=payload)
    resp = await client.send(req, stream=True)
    
    parser = StreamParser(client, resp)
    await parser.pre_consume()
    return parser
