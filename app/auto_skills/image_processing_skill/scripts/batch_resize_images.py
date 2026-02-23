from langchain_core.tools import tool
import os
from pathlib import Path
from PIL import Image


@tool
def batch_resize_images(
    input_dir: str,
    output_dir: str,
    width: int,
    height: int,
    keep_aspect_ratio: bool = True,
    quality: int = 95,
    extensions: list = None
) -> dict:
    """
    批量调整图片尺寸
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        width: 目标宽度（像素），0表示保持比例
        height: 目标高度（像素），0表示保持比例
        keep_aspect_ratio: 是否保持宽高比，默认为True
        quality: 输出图片质量（1-100），默认为95
        extensions: 处理的图片扩展名，默认为['jpg','jpeg','png','bmp','gif']
        
    Returns:
        包含批量处理结果的字典
        
    Examples:
        >>> batch_resize_images("input_folder", "output_folder", 800, 600)
    """
    try:
        # 检查输入目录是否存在
        if not os.path.exists(input_dir):
            return {
                "success": False,
                "error": f"输入目录不存在: {input_dir}"
            }
        
        # 设置默认扩展名
        if extensions is None:
            extensions = ['jpg', 'jpeg', 'png', 'bmp', 'gif']
        
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 查找所有图片文件
        image_files = []
        for ext in extensions:
            # 支持大小写
            patterns = [f"*.{ext}", f"*.{ext.upper()}"]
            for pattern in patterns:
                for file_path in Path(input_dir).glob(pattern):
                    if file_path.is_file():
                        image_files.append(str(file_path))
        
        if not image_files:
            return {
                "success": False,
                "error": f"在目录 {input_dir} 中未找到支持的图片文件（扩展名: {', '.join(extensions)}）"
            }
        
        # 处理每个图片文件
        results = []
        success_count = 0
        error_count = 0
        
        for image_path in image_files:
            try:
                # 构建输出路径
                file_name = os.path.basename(image_path)
                output_path = os.path.join(output_dir, file_name)
                
                # 打开图片
                with Image.open(image_path) as img:
                    original_width, original_height = img.size
                    
                    # 计算目标尺寸
                    if width == 0 and height == 0:
                        new_width, new_height = original_width, original_height
                    elif keep_aspect_ratio:
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
                            ratio = min(width_ratio, height_ratio)  # 选择较小的比例
                            new_width = int(original_width * ratio)
                            new_height = int(original_height * ratio)
                    else:
                        # 不保持比例，直接使用指定尺寸
                        new_width = width if width > 0 else original_width
                        new_height = height if height > 0 else original_height
                    
                    # 调整图片尺寸
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
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
                        # 默认保存为原格式
                        resized_img.save(output_path, quality=quality)
                    
                    # 记录结果
                    results.append({
                        "file": file_name,
                        "original_size": f"{original_width}x{original_height}",
                        "new_size": f"{new_width}x{new_height}",
                        "output_path": output_path,
                        "status": "success"
                    })
                    success_count += 1
                    
            except Exception as e:
                results.append({
                    "file": os.path.basename(image_path),
                    "error": str(e),
                    "status": "failed"
                })
                error_count += 1
        
        # 汇总结果
        summary = {
            "total_files": len(image_files),
            "success_count": success_count,
            "error_count": error_count,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "target_size": f"{width}x{height}" if width > 0 and height > 0 else f"宽{width if width > 0 else '自动'}, 高{height if height > 0 else '自动'}",
            "keep_aspect_ratio": keep_aspect_ratio,
            "quality": quality
        }
        
        return {
            "success": True,
            "summary": summary,
            "details": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"批量处理图片时出错: {str(e)}"
        }