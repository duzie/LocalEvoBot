from langchain_core.tools import tool
from PIL import Image
import os
from pathlib import Path


@tool
def resize_image(
    image_path: str,
    output_path: str,
    width: int,
    height: int,
    keep_aspect_ratio: bool = True,
    quality: int = 95
) -> dict:
    """
    调整图片尺寸（缩放）
    
    Args:
        image_path: 原始图片路径
        output_path: 输出图片路径
        width: 目标宽度（像素），0表示保持比例
        height: 目标高度（像素），0表示保持比例
        keep_aspect_ratio: 是否保持宽高比，默认为True
        quality: 输出图片质量（1-100），默认为95
        
    Returns:
        包含操作结果的字典
        
    Examples:
        >>> resize_image("input.jpg", "output.jpg", 800, 600)
        >>> resize_image("input.jpg", "output.jpg", 800, 0, keep_aspect_ratio=True)  # 按宽度缩放，高度自动计算
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
            
            # 计算目标尺寸
            if width == 0 and height == 0:
                return {
                    "success": False,
                    "error": "宽度和高度不能同时为0"
                }
            
            if keep_aspect_ratio:
                if width == 0:
                    # 按高度缩放，宽度自动计算
                    ratio = height / original_height
                    new_width = int(original_width * ratio)
                    new_height = height
                elif height == 0:
                    # 按宽度缩放，高度自动计算
                    ratio = width / original_width
                    new_width = width
                    new_height = int(original_height * ratio)
                else:
                    # 同时指定宽高，但保持比例
                    width_ratio = width / original_width
                    height_ratio = height / original_height
                    ratio = min(width_ratio, height_ratio)  # 选择较小的比例，确保图片完全在目标区域内
                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
            else:
                # 不保持比例，直接使用指定尺寸
                new_width = width if width > 0 else original_width
                new_height = height if height > 0 else original_height
            
            # 调整图片尺寸
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 保存图片
            # 根据文件扩展名确定格式
            ext = Path(output_path).suffix.lower()
            if ext in ['.jpg', '.jpeg']:
                resized_img.save(output_path, 'JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                resized_img.save(output_path, 'PNG', optimize=True)
            elif ext == '.webp':
                resized_img.save(output_path, 'WEBP', quality=quality)
            else:
                # 默认保存为JPEG
                resized_img.save(output_path, quality=quality)
            
            return {
                "success": True,
                "original_size": f"{original_width}x{original_height}",
                "new_size": f"{new_width}x{new_height}",
                "output_path": output_path,
                "quality": quality,
                "aspect_ratio_preserved": keep_aspect_ratio
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"调整图片尺寸时出错: {str(e)}"
        }