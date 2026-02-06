from langchain_core.tools import tool
import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load env from project root if not already loaded
# Assuming the agent runs from project root, but to be safe:
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

@tool
def recognize_captcha(image_path: str) -> str:
    """
    使用视觉模型(Doubao Vision)识别图片中的文字或验证码。
    
    Args:
        image_path: 图片文件的绝对路径
        
    Returns:
        识别出的文本内容
    """
    api_key = os.getenv("ARK_API_KEY")
    model = os.getenv("DOUBAO_VISION_MODEL_NAME")
    
    if not api_key:
        return "Error: ARK_API_KEY not found in environment variables."
    if not model:
        return "Error: DOUBAO_VISION_MODEL_NAME not found in environment variables."
        
    if not os.path.exists(image_path):
        return f"Error: Image file not found at {image_path}"
        
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        
        def encode_image(path):
            with open(path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
                
        base64_image = encode_image(image_path)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify the text or verification code in this image. Only return the text content, no other words."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error recognizing captcha: {str(e)}"
