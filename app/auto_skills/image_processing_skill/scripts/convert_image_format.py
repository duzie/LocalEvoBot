from langchain_core.tools import tool
from PIL import Image
import os
from pathlib import Path


@tool
def convert_image_format(
    image_path: str,
    output_path: str,
    format: str = "JPEG",
    quality: int = 95
) -> dict:
    """
    转换图片格式
    
    Args:
        image_path: 原始图片路径
        output_path: 输出图片路径
        format: 目标格式：JPEG、PNG、BMP、GIF、WEBP等，默认为JPEG
        quality: 输出图片质量（1-100，仅JPEG有效），默认为95
        
    Returns:
        包含操作结果的字典
        
    Examples:
        >>> convert_image_format("input.png", "output.jpg", "JPEG")
        >>> convert_image_format("input.jpg", "output.png", "PNG")
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"输入文件不存在: {image_path}"
            }
        
        # 打开图片
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            original_format = img.format
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 转换格式并保存
            format_upper = format.upper()
            
            # 处理RGBA模式转换为RGB模式（JPEG不支持透明度）
            if format_upper in ['JPEG', 'JPG'] and img.mode in ['RGBA', 'LA']:
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                # 如果图片有透明度，合并到白色背景上
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])  # 使用alpha通道作为mask
                else:
                    background.paste(img, mask=img.split()[1])  # LA模式使用亮度通道作为mask
                img = background
            
            # 保存图片
            save_kwargs = {}
            if format_upper in ['JPEG', 'JPG', 'WEBP']:
                save_kwargs['quality'] = quality
                if format_upper in ['JPEG', 'JPG']:
                    save_kwargs['optimize'] = True
            
            img.save(output_path, format=format_upper, **save_kwargs)
            
            # 获取输出文件大小
            output_size = os.path.getsize(output_path)
            
            return {
                "success": True,
                "original_format": original_format,
                "original_size": f"{original_width}x{original_height}",
                "new_format": format_upper,
                "output_path": output_path,
                "output_size_bytes": output_size,
                "quality": quality if format_upper in ['JPEG', 'JPG', 'WEBP'] else None
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"转换图片格式时出错: {str(e)}"
        }