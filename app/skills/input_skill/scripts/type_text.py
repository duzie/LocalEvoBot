from langchain_core.tools import tool
import pyautogui
import time
import pyperclip

@tool
def type_text(text: str, mode: str = "type", press_enter: bool = False, clear_before_input: bool = False):
    """
    输入文本。
    
    Args:
        text: 要输入的文本内容。
        mode: 输入模式。
            - "type": 模拟按键逐字输入 (默认)。
            - "paste": 使用剪贴板粘贴 (推荐，避开输入法)。
        press_enter: 是否在输入完成后按下回车键。
        clear_before_input: 是否在输入前先全选 (Ctrl+A)，常用于覆盖输入框原有内容。
    """
    try:
        time.sleep(0.5)
        
        # 自动处理 {ENTER} 后缀
        if text.endswith("{ENTER}"):
            text = text[:-7]
            press_enter = True
            
        if clear_before_input:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            
        if mode == "paste":
            # 备份剪贴板
            try:
                original = pyperclip.paste()
            except:
                original = ""
            
            pyperclip.copy(text)
            # Ctrl+V
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
        else:
            pyautogui.write(text, interval=0.05)
            
        msg = f"已输入文本: {text} (模式: {mode})"
        
        if press_enter:
            time.sleep(0.1)
            pyautogui.press('enter')
            msg += " 并按下了回车"
            
        return msg
    except Exception as e:
        return f"输入失败: {e}"
