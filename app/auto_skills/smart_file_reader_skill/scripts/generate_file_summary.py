from pathlib import Path
from typing import Dict, List, Optional
import re
import json
from langchain_core.tools import tool

def _semantic_text_summary(file_path: Path, max_length: int) -> str:
    """生成语义文本摘要"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(15000)  # 读取前15KB
        
        # 分析文档类型和内容
        file_name = file_path.name.lower()
        
        # 根据文件名推断
        doc_type = "文档"
        if 'readme' in file_name:
            doc_type = "README文档"
        elif 'changelog' in file_name or 'history' in file_name:
            doc_type = "变更日志"
        elif 'license' in file_name:
            doc_type = "许可证文件"
        elif 'config' in file_name or 'setting' in file_name:
            doc_type = "配置文件说明"
        elif 'api' in file_name or '接口' in file_name:
            doc_type = "API文档"
        
        # 分析内容特征
        lines = content.split('\n')
        
        # 检查是否包含代码块
        code_blocks = re.findall(r'^```', content, re.MULTILINE)
        has_code = len(code_blocks) > 0
        
        # 检查是否包含标题
        headings = re.findall(r'^#{1,6}\s+.+', content, re.MULTILINE)
        has_headings = len(headings) > 0
        
        # 检查是否包含列表
        lists = re.findall(r'^[\-\*\+]\s+.+', content, re.MULTILINE)
        has_lists = len(lists) > 0
        
        # 检查是否包含表格
        tables = re.findall(r'^\|.+\|', content, re.MULTILINE)
        has_tables = len(tables) > 0
        
        # 生成摘要
        summary_parts = []
        
        # 文档类型
        summary_parts.append(f"文档类型: {doc_type}")
        
        # 内容特征
        features = []
        if has_code:
            features.append("包含代码示例")
        if has_headings:
            features.append("结构化标题")
        if has_lists:
            features.append("列表项")
        if has_tables:
            features.append("表格数据")
        
        if features:
            summary_parts.append(f"内容特征: {', '.join(features)}")
        
        # 提取关键内容
        # 1. 提取第一段非空文本作为概述
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if paragraphs:
            first_para = paragraphs[0]
            if len(first_para) > 100:
                first_para = first_para[:100] + "..."
            summary_parts.append(f"概述: {first_para}")
        
        # 2. 提取主要标题
        if headings:
            main_headings = []
            for heading in headings[:5]:  # 只取前5个标题
                # 移除#号和空格
                clean_heading = re.sub(r'^#{1,6}\s+', '', heading).strip()
                if clean_heading:
                    main_headings.append(clean_heading)
            
            if main_headings:
                summary_parts.append(f"主要章节: {', '.join(main_headings[:3])}")
        
        # 3. 如果是代码文件，提取关键信息
        if file_path.suffix.lower() == '.py':
            # 提取导入
            imports = re.findall(r'^(import\s+[\w., ]+|from\s+[\w.]+)', content, re.MULTILINE)
            if imports:
                summary_parts.append(f"导入模块: {', '.join([imp.strip() for imp in imports[:3]])}")
            
            # 提取类定义
            classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
            if classes:
                summary_parts.append(f"定义类: {', '.join(classes[:3])}")
            
            # 提取函数定义
            functions = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
            if functions:
                summary_parts.append(f"定义函数: {', '.join(functions[:3])}")
        
        # 组合摘要
        summary = '\n'.join(summary_parts)
        
        # 限制长度
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary
        
    except Exception as e:
        return f"生成摘要时出错: {str(e)}"

def _technical_document_summary(file_path: Path, max_length: int) -> str:
    """生成技术文档摘要"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(20000)  # 读取前20KB
        
        summary_parts = []
        
        # 分析文件类型
        ext = file_path.suffix.lower()
        
        if ext == '.py':
            summary_parts.append("文件类型: Python源代码")
            
            # 提取关键信息
            lines = content.split('\n')
            
            # 模块文档字符串
            module_doc = ""
            for i, line in enumerate(lines):
                if line.strip().startswith('"""') or line.strip().startswith("'''"):
                    # 找到文档字符串开始
                    doc_lines = []
                    for j in range(i, min(i+10, len(lines))):
                        doc_lines.append(lines[j])
                        if (j > i and 
                            (lines[j].strip().endswith('"""') or 
                             lines[j].strip().endswith("'''"))):
                            break
                    
                    module_doc = '\n'.join(doc_lines)
                    break
            
            if module_doc:
                # 清理文档字符串
                module_doc = re.sub(r'^["\']{3}', '', module_doc)
                module_doc = re.sub(r'["\']{3}$', '', module_doc)
                module_doc = module_doc.strip()
                
                if len(module_doc) > 150:
                    module_doc = module_doc[:150] + "..."
                
                summary_parts.append(f"模块说明: {module_doc}")
            
            # 统计信息
            imports = re.findall(r'^(import\s+[\w., ]+|from\s+[\w.]+)', content, re.MULTILINE)
            classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
            functions = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
            
            stats = []
            if imports:
                stats.append(f"{len(imports)}个导入")
            if classes:
                stats.append(f"{len(classes)}个类")
            if functions:
                stats.append(f"{len(functions)}个函数")
            
            if stats:
                summary_parts.append(f"代码统计: {', '.join(stats)}")
        
        elif ext == '.json':
            summary_parts.append("文件类型: JSON数据")
            
            try:
                data = json.loads(content)
                
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    summary_parts.append(f"主要键: {', '.join(keys)}")
                    
                    # 分析数据结构
                    if 'name' in data:
                        summary_parts.append(f"名称: {data['name']}")
                    if 'version' in data:
                        summary_parts.append(f"版本: {data['version']}")
                    if 'description' in data:
                        desc = data['description']
                        if len(desc) > 100:
                            desc = desc[:100] + "..."
                        summary_parts.append(f"描述: {desc}")
                
                elif isinstance(data, list):
                    summary_parts.append(f"数组长度: {len(data)}")
                    if len(data) > 0:
                        first_item = data[0]
                        if isinstance(first_item, dict):
                            keys = list(first_item.keys())[:3]
                            summary_parts.append(f"项目结构: 包含 {', '.join(keys)} 等字段")
            except:
                summary_parts.append("JSON解析失败，可能是无效格式")
        
        elif ext == '.md':
            summary_parts.append("文件类型: Markdown文档")
            
            # 提取标题
            headings = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
            if headings:
                main_headings = headings[:3]
                summary_parts.append(f"主要标题: {', '.join(main_headings)}")
            
            # 检查是否包含代码
            code_blocks = re.findall(r'^```', content, re.MULTILINE)
            if code_blocks:
                summary_parts.append(f"包含 {len(code_blocks)} 个代码块")
        
        else:
            # 通用文本文件
            summary_parts.append("文件类型: 文本文件")
            
            lines = content.split('\n')
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            
            if non_empty_lines:
                # 提取看起来像标题的行（较短、以冒号结尾、或全大写等）
                potential_titles = []
                for line in non_empty_lines[:10]:
                    line = line.strip()
                    if (len(line) < 100 and 
                        (line.endswith(':') or 
                         line.isupper() or
                         re.match(r'^[A-Z][a-z]+:', line))):
                        potential_titles.append(line)
                
                if potential_titles:
                    summary_parts.append(f"疑似标题: {', '.join(potential_titles[:3])}")
        
        # 组合摘要
        summary = '\n'.join(summary_parts)
        
        # 限制长度
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary
        
    except Exception as e:
        return f"生成技术摘要时出错: {str(e)}"

def _executive_summary(file_path: Path, max_length: int) -> str:
    """生成执行摘要（给管理者的简短摘要）"""
    try:
        # 先获取技术摘要
        tech_summary = _technical_document_summary(file_path, 500)
        
        # 简化为执行摘要格式
        lines = tech_summary.split('\n')
        
        # 提取关键信息
        key_points = []
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 只保留最重要的信息
                if key in ['文件类型', '模块说明', '主要键', '主要标题', '名称', '版本']:
                    key_points.append(f"{key}: {value}")
        
        # 如果没有提取到关键点，使用第一行
        if not key_points and lines:
            key_points.append(lines[0])
        
        # 添加文件基本信息
        file_size = file_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        
        if size_mb > 1:
            size_str = f"{size_mb:.1f} MB"
        else:
            size_kb = file_size / 1024
            size_str = f"{size_kb:.1f} KB"
        
        key_points.insert(0, f"文件: {file_path.name} ({size_str})")
        
        # 组合
        summary = '\n'.join(key_points)
        
        # 限制长度
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary
        
    except Exception as e:
        return f"生成执行摘要时出错: {str(e)}"

@tool
def generate_file_summary(
    file_path: str, 
    summary_type: str = "semantic",
    max_length: int = 500
) -> Dict:
    """生成文件摘要
    
    Args:
        file_path: 文件路径
        summary_type: 摘要类型，可选值: 
            - "semantic": 语义摘要（默认）
            - "technical": 技术摘要
            - "executive": 执行摘要
        max_length: 最大长度（字符数）
        
    Returns:
        包含摘要信息的字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    
    if not path.is_file():
        return {"error": f"不是文件: {file_path}"}
    
    # 根据类型选择摘要生成器
    if summary_type == "technical":
        summary = _technical_document_summary(path, max_length)
    elif summary_type == "executive":
        summary = _executive_summary(path, max_length)
    else:  # 默认语义摘要
        summary = _semantic_text_summary(path, max_length)
    
    # 获取文件信息
    file_size = path.stat().st_size
    modified_time = path.stat().st_mtime
    
    from datetime import datetime
    modified_str = datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        "file_info": {
            "path": str(path),
            "name": path.name,
            "size_bytes": file_size,
            "size_human": _format_file_size(file_size),
            "modified": modified_str,
            "extension": path.suffix.lower()
        },
        "summary": {
            "type": summary_type,
            "content": summary,
            "length": len(summary),
            "max_length": max_length
        },
        "success": True
    }

def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
