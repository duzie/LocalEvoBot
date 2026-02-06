# Usage

## Scope
当常规 OCR (如 Tesseract) 无法准确识别（例如复杂背景的验证码、手写体、扭曲文字）时，使用此技能。此技能调用云端视觉大模型，准确率高但速度相对较慢且有成本。

## Tools

### recognize_captcha
识别图片中的文字或验证码。

- **Args**:
    - `image_path` (str): 图片文件的绝对路径。
- **Returns**: (str) 识别出的文本内容。

## Examples

### 识别验证码
```python
result = recognize_captcha(image_path="C:\\temp\\captcha.png")
print(f"验证码是: {result}")
```
