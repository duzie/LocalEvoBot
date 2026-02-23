# Image Processing Skill

图片处理技能，提供裁剪、缩放、格式转换等图像处理功能，与现有的图片下载功能互补。

## 工具列表

### 1. resize_image - 调整图片尺寸（缩放）
调整图片尺寸，支持保持宽高比。

**参数:**
- `image_path`: 原始图片路径
- `output_path`: 输出图片路径
- `width`: 目标宽度（像素），0表示保持比例
- `height`: 目标高度（像素），0表示保持比例
- `keep_aspect_ratio`: 是否保持宽高比，默认为True
- `quality`: 输出图片质量（1-100），默认为95

**示例:**
```python
# 将图片缩放到800x600，保持宽高比
resize_image("input.jpg", "output.jpg", 800, 600)

# 按宽度800像素缩放，高度自动计算
resize_image("input.jpg", "output.jpg", 800, 0)

# 按高度600像素缩放，宽度自动计算
resize_image("input.jpg", "output.jpg", 0, 600)

# 强制缩放到指定尺寸，不保持宽高比
resize_image("input.jpg", "output.jpg", 800, 600, keep_aspect_ratio=False)
```

### 2. crop_image - 裁剪图片
裁剪图片的指定区域。

**参数:**
- `image_path`: 原始图片路径
- `output_path`: 输出图片路径
- `left`: 裁剪区域左上角X坐标
- `top`: 裁剪区域左上角Y坐标
- `right`: 裁剪区域右下角X坐标
- `bottom`: 裁剪区域右下角Y坐标
- `quality`: 输出图片质量（1-100），默认为95

**示例:**
```python
# 裁剪从(100,100)到(500,400)的区域
crop_image("input.jpg", "output.jpg", 100, 100, 500, 400)

# 裁剪图片中心区域
crop_image("input.jpg", "output.jpg", 200, 150, 600, 450)
```

### 3. convert_image_format - 转换图片格式
转换图片到不同的格式。

**参数:**
- `image_path`: 原始图片路径
- `output_path`: 输出图片路径
- `format`: 目标格式：JPEG、PNG、BMP、GIF、WEBP等，默认为JPEG
- `quality`: 输出图片质量（1-100，仅JPEG有效），默认为95

**示例:**
```python
# PNG转JPEG
convert_image_format("input.png", "output.jpg", "JPEG")

# JPEG转PNG
convert_image_format("input.jpg", "output.png", "PNG")

# 转换为WebP格式
convert_image_format("input.jpg", "output.webp", "WEBP")
```

### 4. get_image_info - 获取图片信息
获取图片的详细信息，包括尺寸、格式、EXIF数据等。

**参数:**
- `image_path`: 图片路径

**示例:**
```python
# 获取图片信息
get_image_info("image.jpg")
```

### 5. batch_resize_images - 批量调整图片尺寸
批量处理目录中的所有图片。

**参数:**
- `input_dir`: 输入目录
- `output_dir`: 输出目录
- `width`: 目标宽度（像素），0表示保持比例
- `height`: 目标高度（像素），0表示保持比例
- `keep_aspect_ratio`: 是否保持宽高比，默认为True
- `quality`: 输出图片质量（1-100），默认为95
- `extensions`: 处理的图片扩展名，默认为['jpg','jpeg','png','bmp','gif']

**示例:**
```python
# 批量将目录中的所有图片缩放到800x600
batch_resize_images("input_folder", "output_folder", 800, 600)

# 批量按宽度800像素缩放
batch_resize_images("input_folder", "output_folder", 800, 0)
```

## 使用场景

1. **网页图片优化**: 下载的图片可能尺寸过大，需要缩放以适应网页显示
2. **社交媒体图片**: 不同平台对图片尺寸有不同要求，需要裁剪或缩放
3. **批量处理**: 处理大量图片，如产品图库、照片集等
4. **格式转换**: 将图片转换为更适合的格式，如PNG转JPEG以减少文件大小
5. **图片信息分析**: 查看图片的EXIF信息、尺寸等

## 与现有功能的互补性

- **下载图片** (`download_image`, `download_multiple_images`): 从网络获取图片
- **验证图片URL** (`validate_image_url`): 检查图片链接是否有效
- **图片处理** (本技能): 对下载的图片进行后续处理

**典型工作流程:**
1. 使用 `download_image` 下载图片
2. 使用 `get_image_info` 查看图片信息
3. 使用 `resize_image` 或 `crop_image` 调整图片
4. 使用 `convert_image_format` 转换格式（如果需要）
5. 使用处理后的图片

## 依赖

- Pillow (PIL): Python图像处理库
- 支持格式: JPEG, PNG, BMP, GIF, WebP, TIFF等

## 注意事项

1. 处理大图片时可能需要较多内存
2. 保持宽高比时，实际输出尺寸可能与指定尺寸不完全相同
3. 转换格式时，透明背景的PNG转JPEG会自动添加白色背景
4. 批量处理时建议先在小样本上测试

## 错误处理

所有工具都返回包含 `success` 字段的字典，操作失败时会包含 `error` 字段描述错误原因。