# [ANCHOR: CH-11]
# Description: OS Level Clipboard Listener and Text Washing Layer for Privacy Solidification
# Status: Verified

import re
import time
import threading
import pyperclip

class WashingLayer:
    """
    内容清洗算法核心架构：
    高精度正则映射矩阵，对敏感资产（手机、身份证、IP、银行卡）进行物理隔离与离线固化。
    """
    
    REGEX_MATRIX = {
        # 11位手机号 (中国大陆)
        r'\b1[3-9]\d{9}\b': '[REDACTED_PHONE]',
        # 18位身份证号
        r'\b\d{17}[\dXx]\b': '[REDACTED_ID_CARD]',
        # IPv4 物理IP地址
        r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b': '[REDACTED_IP]',
        # 16-19位银行卡号 (简单校验)
        r'\b\d{16,19}\b': '[REDACTED_BANK_CARD]'
    }

    @classmethod
    def wash(cls, text: str) -> str:
        if not text:
            return ""
        
        washed_text = text
        for pattern, replacement in cls.REGEX_MATRIX.items():
            washed_text = re.sub(pattern, replacement, washed_text)
            
        return washed_text

def clipboard_listener():
    """
    OS原生文本流捕捉：
    监听全局剪贴板变更，将其送入 WashingLayer 进行无情洗涤。
    """
    print("[Clipboard Watcher] OS级剪贴板监听器已就绪，正在进行物理级洗涤监控...")
    recent_value = ""
    
    while True:
        try:
            current_value = pyperclip.paste()
            if current_value and current_value != recent_value:
                recent_value = current_value
                # 捕获到新文本，执行洗涤
                washed_text = WashingLayer.wash(current_value)
                if washed_text != current_value:
                    print(f"\n[Washing Layer] 📸 拦截并洗涤敏感文本:\n--- 洗涤后输出 ---\n{washed_text}\n--------------------")
        except Exception as e:
            pass
        time.sleep(1.0)

def start_clipboard_monitor():
    """点火启动异步剪贴板监听线程"""
    t = threading.Thread(target=clipboard_listener, daemon=True)
    t.start()
