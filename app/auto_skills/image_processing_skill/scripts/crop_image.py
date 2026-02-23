from langchain_core.tools import tool
from PIL import Image
import os
from pathlib import Path


@tool
def crop_image(
    image_path: str,
    output_path: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    quality: int = 95
) -> dict:
    """
    裁剪图片
    
    Args:
        image_path: 原始图片路径
        output_path: 输出图片路径
        left: 裁剪区域左上角X坐标
        top: 裁剪区域左上角Y坐标
        right: 裁剪区域右下角X坐标
        bottom: 裁剪区域右下角Y坐标
        quality: 输出图片质量（1-100），默认为95
        
    Returns:
        包含操作结果的字典
        
    Examples:
        >>> crop_image("input.jpg", "output.jpg", 100, 100, 500, 400)  # 裁剪从(100,100)到(500,400)的区域
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
            
            # 验证裁剪区域
            if left < 0 or top < 0 or right <= left or bottom <= top:
                return {
                    "success": False,
                    "error": f"无效的裁剪区域: left={left}, top={top}, right={right}, bottom={bottom}"
                }
            
            if right > original_width or bottom > original_height:
                return {
                    "success": False,
                    "error": f"裁剪区域超出图片范围: 图片尺寸={original_width}x{original_height}, 裁剪区域={left},{top},{right},{bottom}"
                }
            
            # 计算裁剪区域尺寸
            crop_width = right - left
            crop_height = bottom - top
            
            # 裁剪图片
            cropped_img = img.crop((left, top, right, bottom))
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 保存图片
            # 根据文件扩展名确定格式
            ext = Path(output_path).suffix.lower()
            if ext in ['.jpg', '.jpeg']:
                cropped_img.save(output_path, 'JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                cropped_img.save(output_path, 'PNG', optimize=True)
            elif ext == '.webp':
                cropped_img.save(output_path, 'WEBP', quality=quality)
            else:
                # 默认保存为JPEG
                cropped_img.save(output_path, quality=quality)
            
            return {
                "success": True,
                "original_size": f"{original_width}x{original_height}",
                "crop_region": f"({left},{top})-({right},{bottom})",
                "crop_size": f"{crop_width}x{crop_height}",
                "output_path": output_path,
                "quality": quality
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"裁剪图片时出错: {str(e)}"
        }