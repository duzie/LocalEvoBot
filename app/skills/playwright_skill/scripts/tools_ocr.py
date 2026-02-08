from langchain_core.tools import tool

from . import _playwright_core as core


@tool
def playwright_click_by_ocr(text: str, index: int = 0, offset_x: int = 0, offset_y: int = 0, exact_match: bool = False, double_click: bool = False):
    """
    通过 OCR 识别屏幕文字并点击指定位置。
    当无法通过 CSS 选择器定位元素时，可使用此方法。
    
    Args:
        text: 要查找的文字
        index: 如果有多个匹配，点击第几个 (默认 0)
        offset_x: 点击位置相对于文字中心的 X 轴偏移量
        offset_y: 点击位置相对于文字中心的 Y 轴偏移量
        exact_match: 是否完全匹配文字 (默认 False，使用包含匹配)
        double_click: 是否双击 (默认 False)
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"

    pytesseract, err = core._setup_tesseract(language="chi_sim")
    if err:
        return err

    try:
        from PIL import Image
        from pytesseract import Output
        import io

        screenshot_bytes = core._page.screenshot()
        image = Image.open(io.BytesIO(screenshot_bytes))

        data = pytesseract.image_to_data(image, lang="chi_sim+eng", output_type=Output.DICT)

        matches = []
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            content = data["text"][i].strip()
            if not content:
                continue

            match = False
            if exact_match:
                if content == text:
                    match = True
            else:
                if text in content:
                    match = True

            if match:
                matches.append(
                    {
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                        "text": content,
                    }
                )

        if not matches:
            return f"未找到包含 '{text}' 的文字"

        if index >= len(matches):
            return f"找到 {len(matches)} 个匹配，但索引 {index} 超出范围"

        target = matches[index]

        center_x = target["x"] + target["w"] / 2
        center_y = target["y"] + target["h"] / 2

        final_x = center_x + offset_x
        final_y = center_y + offset_y

        if double_click:
            core._page.mouse.dblclick(final_x, final_y)
        else:
            core._page.mouse.click(final_x, final_y)

        return f"已点击文字 '{target['text']}' 位置 ({final_x}, {final_y})"

    except Exception as e:
        return f"OCR 点击失败: {e}"


@tool
def playwright_type_current(text: str, delay: int = 50):
    """
    在当前焦点元素输入文本。
    通常配合 playwright_click_by_ocr 使用 (先点击输入框或标签，再输入)。
    
    Args:
        text: 要输入的文本
        delay: 按键间隔 (毫秒)，默认 50
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        core._page.keyboard.type(text, delay=delay)
        return f"已输入: {text}"
    except Exception as e:
        return f"输入失败: {e}"

