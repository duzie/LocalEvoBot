from langchain_core.tools import tool
from PIL import Image
import os
from datetime import datetime


@tool
def get_image_info(image_path: str) -> dict:
    """
    获取图片信息
    
    Args:
        image_path: 图片路径
        
    Returns:
        包含图片信息的字典
        
    Examples:
        >>> get_image_info("image.jpg")
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"文件不存在: {image_path}"
            }
        
        # 获取文件基本信息
        file_size = os.path.getsize(image_path)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
        file_ctime = datetime.fromtimestamp(os.path.getctime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 打开图片获取详细信息
        with Image.open(image_path) as img:
            width, height = img.size
            mode = img.mode
            format_info = img.format
            format_description = img.format_description
            
            # 尝试获取EXIF信息
            exif_info = {}
            try:
                exif_data = img._getexif()
                if exif_data:
                    # 只提取一些常用的EXIF标签
                    exif_tags = {
                        271: '相机品牌',
                        272: '相机型号',
                        274: '方向',
                        282: 'X分辨率',
                        283: 'Y分辨率',
                        296: '分辨率单位',
                        306: '日期时间',
                        33434: '曝光时间',
                        33437: '光圈值',
                        34855: 'ISO感光度',
                        37378: '闪光灯',
                        37380: '焦距',
                        37383: '测光模式',
                        37385: '闪光灯模式',
                        37500: '制造商备注',
                        37510: '用户注释',
                        40961: '色彩空间',
                        41985: '白平衡',
                        41986: '数字变焦比率',
                        41987: '等效35mm焦距',
                        41988: '场景类型',
                        41989: '自定义渲染',
                        41990: '曝光模式',
                        41991: '白平衡模式',
                        41992: '数字变焦',
                        41993: '对比度',
                        41994: '饱和度',
                        41995: '锐度',
                        41996: '主体距离范围'
                    }
                    
                    for tag_id, value in exif_data.items():
                        tag_name = exif_tags.get(tag_id, f"标签{tag_id}")
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore')
                            except:
                                value = str(value)
                        exif_info[tag_name] = str(value)
            except:
                exif_info = {"error": "无法读取EXIF信息"}
            
            # 获取颜色模式信息
            color_modes = {
                '1': '1位像素，黑白',
                'L': '8位像素，灰度',
                'P': '8位像素，使用调色板映射到任何模式',
                'RGB': '3x8位像素，真彩色',
                'RGBA': '4x8位像素，带透明通道的真彩色',
                'CMYK': '4x8位像素，分色',
                'YCbCr': '3x8位像素，彩色视频格式',
                'LAB': '3x8位像素，L*a*b颜色空间',
                'HSV': '3x8位像素，色相，饱和度，明度颜色空间',
                'I': '32位有符号整数像素',
                'F': '32位浮点像素'
            }
            
            mode_description = color_modes.get(mode, f"未知模式: {mode}")
            
            # 计算文件大小（人类可读格式）
            def human_readable_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"
            
            return {
                "success": True,
                "file_path": image_path,
                "file_name": os.path.basename(image_path),
                "file_size_bytes": file_size,
                "file_size_human": human_readable_size(file_size),
                "last_modified": file_mtime,
                "created_time": file_ctime,
                "image_info": {
                    "dimensions": f"{width}x{height}",
                    "width": width,
                    "height": height,
                    "aspect_ratio": f"{width}:{height}",
                    "mode": mode,
                    "mode_description": mode_description,
                    "format": format_info,
                    "format_description": format_description,
                    "has_alpha": mode in ['RGBA', 'LA', 'PA'],
                    "is_grayscale": mode in ['L', 'LA'],
                    "is_indexed": mode == 'P'
                },
                "exif_info": exif_info if exif_info else "无EXIF信息"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"获取图片信息时出错: {str(e)}"
        }