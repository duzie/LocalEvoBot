from langchain_core.tools import tool
from pydub import AudioSegment
import os
import json
import hashlib
import hmac
import base64
import datetime
from urllib.parse import urlencode
import websocket
from typing import Optional

@tool
def transcribe_audio(
    audio_path: str,
    file_path: Optional[str] = None,
    language: str = "zh_cn",
    appid: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> dict:
    """
    使用讯飞语音识别 API 将音频文件转录为文字
    
    Args:
        audio_path: 音频文件路径（支持 mp3, wav, m4a, flac 等格式）
        language: 语言，默认 zh_cn（中文）
        appid: 讯飞 APP ID（可选，默认从环境变量 XF_APPID 读取）
        api_key: 讯飞 API Key（可选，默认从环境变量 XFAPI_KEY 读取）
        api_secret: 讯飞 API Secret（可选，默认从环境变量 XFAPI_SECRET 读取）
    
    Returns:
        dict: {
            "success": bool,
            "text": str,  # 识别结果
            "duration": float,  # 音频时长（秒）
            "message": str
        }
    """
    if (not audio_path) and file_path:
        audio_path = file_path
    # 从环境变量读取凭证
    appid = appid or os.getenv("XF_APPID") or os.getenv("XF_APP_ID")
    api_key = api_key or os.getenv("XFAPI_KEY") or os.getenv("XF_API_KEY")
    api_secret = api_secret or os.getenv("XFAPI_SECRET") or os.getenv("XF_API_SECRET")
    
    if not all([appid, api_key, api_secret]):
        return {"success": False, "text": "", "duration": 0, "message": "缺少讯飞 API 凭证，请设置 XF_APPID, XFAPI_KEY, XFAPI_SECRET 环境变量"}
    
    if not os.path.exists(audio_path):
        return {"success": False, "text": "", "duration": 0, "message": f"音频文件不存在：{audio_path}"}
    
    host = "iat-api.xfyun.cn"
    path = "/v2/iat"
    
    # 转换音频为 PCM (16kHz, 16bit, 单声道)
    try:
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio_data = audio.raw_data
        duration_seconds = len(audio) / 1000.0
    except Exception as e:
        return {"success": False, "text": "", "duration": 0, "message": f"音频格式转换失败：{str(e)}"}
    
    # 生成鉴权 URL
    now = datetime.datetime.now()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(api_secret.encode('utf-8'), signature_origin.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')
    authorization = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization_base64 = base64.b64encode(authorization.encode('utf-8')).decode('utf-8')
    query = urlencode({"authorization": authorization_base64, "date": date, "host": host})
    url = f"wss://{host}{path}?{query}"
    
    # 分帧 (1280 字节/帧)
    frame_size = 1280
    chunks = [audio_data[i:i+frame_size] for i in range(0, len(audio_data), frame_size)]
    
    if not chunks:
        return {"success": False, "text": "", "duration": 0, "message": "音频数据为空"}
    
    try:
        # 使用同步 WebSocket 客户端
        ws = websocket.create_connection(url, timeout=30)
        
        text_result = []
        
        # 发送所有帧（第一帧包含完整字段，后续帧只包含 data）
        for idx, chunk in enumerate(chunks):
            status = 0 if idx == 0 else 1
            if idx == len(chunks) - 1:
                status = 2  # 最后一帧
            
            if idx == 0:
                # 第一帧：包含 common, business, data
                payload = {
                    "common": {"app_id": appid},
                    "business": {
                        "language": language,
                        "domain": "iat",
                        "accent": "mandarin",
                        "vad_eos": 3000,
                        "dwa": "wpgs",
                        "ptt": 0
                    },
                    "data": {
                        "status": status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(chunk).decode('utf-8')
                    }
                }
            else:
                # 后续帧：只包含 data
                payload = {
                    "data": {
                        "status": status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(chunk).decode('utf-8')
                    }
                }
            
            ws.send(json.dumps(payload))
        
        # 统一接收所有响应
        while True:
            msg = ws.recv()
            data = json.loads(msg)
            code = data.get("code", 0)
            if code != 0:
                ws.close()
                return {"success": False, "text": "", "duration": 0, "message": f"API 错误：{data.get('message', '未知错误')} (code={code})"}
            
            # 提取文本
            result_text = _extract_text_from_response(data)
            text_result.append(result_text)
            
            # 检查是否结束
            result_data = data.get("data", {})
            resp_status = result_data.get("status")
            if resp_status == 2:
                break
        
        ws.close()
        final_text = "".join(text_result).strip()
        
        if final_text:
            return {"success": True, "text": final_text, "duration": duration_seconds, "message": "转录成功"}
        else:
            return {"success": False, "text": "", "duration": duration_seconds, "message": "未识别到内容"}
        
    except Exception as e:
        return {"success": False, "text": "", "duration": 0, "message": f"WebSocket 错误：{str(e)}"}


def _extract_text_from_response(data: dict) -> str:
    """从讯飞 API 响应中提取文本"""
    text = ""
    if not isinstance(data, dict):
        return text
    
    # 尝试从 data.result.ws 提取
    result_data = data.get("data", {})
    if isinstance(result_data, dict):
        result = result_data.get("result", {})
        if isinstance(result, dict):
            ws_list = result.get("ws", [])
            if isinstance(ws_list, list):
                for ws_item in ws_list:
                    if isinstance(ws_item, dict):
                        cw_list = ws_item.get("cw", [])
                        if isinstance(cw_list, list):
                            for cw_item in cw_list:
                                if isinstance(cw_item, dict):
                                    text += cw_item.get("w", "")
    
    # 尝试从 payload.result.text 提取（base64 编码）
    if not text and data.get("payload"):
        payload = data.get("payload", {})
        if isinstance(payload, dict):
            result = payload.get("result", {})
            if isinstance(result, dict):
                encoded = result.get("text", "")
                if encoded:
                    try:
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        inner = json.loads(decoded)
                        ws_list = inner.get("ws", [])
                        if isinstance(ws_list, list):
                            for ws_item in ws_list:
                                if isinstance(ws_item, dict):
                                    cw_list = ws_item.get("cw", [])
                                    if isinstance(cw_list, list):
                                        for cw_item in cw_list:
                                            if isinstance(cw_item, dict):
                                                text += cw_item.get("w", "")
                    except Exception:
                        pass
    
    return text
