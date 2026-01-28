from langchain_core.tools import tool
import os
import datetime
from typing import Dict, Any, Optional

@tool
def generate_development_doc(analysis_result: Dict[str, Any], 
                           output_dir: Optional[str] = None,
                           template_type: str = "standard") -> Dict[str, Any]:
    """
    生成开发文档
    
    Args:
        analysis_result: 代码分析结果
        output_dir: 输出目录
        template_type: 模板类型：standard, detailed, simple
        
    Returns:
        包含生成结果的字典
    """
    try:
        if not analysis_result.get("success"):
            return {"success": False, "error": "分析结果无效"}
        
        # 确定输出目录
        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), "docs")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if "directory_path" in analysis_result:
            dir_name = os.path.basename(analysis_result["directory_path"])
            filename = f"开发文档_{dir_name}_{timestamp}.md"
        else:
            filename = f"开发文档_{timestamp}.md"
        
        output_path = os.path.join(output_dir, filename)
        
        # 根据模板类型生成内容
        if template_type == "detailed":
            content = _generate_detailed_doc(analysis_result)
        elif template_type == "simple":
            content = _generate_simple_doc(analysis_result)
        else:  # standard
            content = _generate_standard_doc(analysis_result)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "output_path": output_path,
            "filename": filename,
            "file_size": os.path.getsize(output_path),
            "generated_at": timestamp
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def _generate_standard_doc(analysis_result: Dict[str, Any]) -> str:
    """生成标准开发文档"""
    content = []
    
    # 标题
    content.append(f"# 开发文档")
    content.append("")
    
    # 基本信息
    content.append("## 基本信息")
    content.append("")
    content.append(f"- **生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if "directory_path" in analysis_result:
        content.append(f"- **分析目录**: {analysis_result['directory_path']}")
    
    if "total_files_found" in analysis_result:
        content.append(f"- **文件总数**: {analysis_result['total_files_found']}")
        content.append(f"- **分析文件数**: {analysis_result['total_files_analyzed']}")
    
    content.append("")
    
    # 文件类型统计
    if "file_types" in analysis_result and analysis_result["file_types"]:
        content.append("## 文件类型统计")
        content.append("")
        content.append("| 文件类型 | 数量 |")
        content.append("|----------|------|")
        for file_type, count in analysis_result["file_types"].items():
            content.append(f"| {file_type} | {count} |")
        content.append("")
    
    # API端点
    if "api_endpoints" in analysis_result and analysis_result["api_endpoints"]:
        content.append("## API接口端点")
        content.append("")
        content.append("共发现以下API端点：")
        content.append("")
        for i, endpoint in enumerate(analysis_result["api_endpoints"], 1):
            content.append(f"{i}. `{endpoint}`")
        content.append("")
        
        # 特别标注目标方法
        target_method = "RelDishOrTypeToDeptAccountingCenter"
        if any(target_method in ep for ep in analysis_result["api_endpoints"]):
            content.append(f"**特别注意**: 包含目标方法 `{target_method}`")
            content.append("")
    
    # 类和方法统计
    if "classes" in analysis_result and analysis_result["classes"]:
        content.append("## 类定义")
        content.append("")
        content.append(f"共发现 {len(analysis_result['classes'])} 个类：")
        content.append("")
        for i, class_name in enumerate(analysis_result["classes"][:20], 1):  # 只显示前20个
            content.append(f"{i}. `{class_name}`")
        
        if len(analysis_result["classes"]) > 20:
            content.append(f"... 还有 {len(analysis_result['classes']) - 20} 个类")
        content.append("")
    
    if "methods" in analysis_result and analysis_result["methods"]:
        content.append("## 方法定义")
        content.append("")
        content.append(f"共发现 {len(analysis_result['methods'])} 个方法（显示前30个）：")
        content.append("")
        for i, method_name in enumerate(analysis_result["methods"][:30], 1):
            content.append(f"{i}. `{method_name}`")
        
        if len(analysis_result["methods"]) > 30:
            content.append(f"... 还有 {len(analysis_result['methods']) - 30} 个方法")
        content.append("")
    
    # 按文件类型详细分析
    if "files_by_type" in analysis_result and analysis_result["files_by_type"]:
        content.append("## 文件详细分析")
        content.append("")
        
        for file_type, files in analysis_result["files_by_type"].items():
            content.append(f"### {file_type.upper()} 文件")
            content.append("")
            content.append(f"共 {len(files)} 个文件：")
            content.append("")
            
            for file_info in files:
                content.append(f"- **{file_info['file_name']}**")
                if file_info.get('summary'):
                    content.append(f"  - 摘要: {file_info['summary']}")
                content.append(f"  - 路径: `{file_info['file_path']}`")
                content.append("")
    
    # 开发建议
    content.append("## 开发建议")
    content.append("")
    content.append("1. **API接口规范**：建议统一API接口命名规范")
    content.append("2. **错误处理**：确保所有API都有适当的错误处理机制")
    content.append("3. **代码注释**：建议为关键方法添加XML注释")
    content.append("4. **模块划分**：根据功能模块合理组织代码结构")
    content.append("5. **安全性**：验证所有API调用的安全性")
    content.append("")
    
    # 后续步骤
    content.append("## 后续步骤")
    content.append("")
    content.append("1. 根据API端点编写接口文档")
    content.append("2. 为关键类和方法添加详细注释")
    content.append("3. 创建单元测试覆盖主要功能")
    content.append("4. 优化代码结构和性能")
    content.append("")
    
    return "\n".join(content)

def _generate_detailed_doc(analysis_result: Dict[str, Any]) -> str:
    """生成详细开发文档"""
    content = _generate_standard_doc(analysis_result)
    
    # 在标准文档基础上添加更多细节
    detailed_parts = []
    
    # 如果有详细分析结果，添加更多信息
    if "detailed_analyses" in analysis_result:
        detailed_parts.append("## 文件详细分析报告")
        detailed_parts.append("")
        
        for i, file_analysis in enumerate(analysis_result["detailed_analyses"][:10], 1):  # 只显示前10个
            if file_analysis.get("success"):
                detailed_parts.append(f"### {i}. {file_analysis.get('file_name')}")
                detailed_parts.append("")
                detailed_parts.append(f"- **文件类型**: {file_analysis.get('file_type')}")
                detailed_parts.append(f"- **文件大小**: {file_analysis.get('file_size')} 字节")
                
                if file_analysis.get("classes"):
                    detailed_parts.append(f"- **包含类**: {', '.join(file_analysis['classes'][:5])}")
                    if len(file_analysis["classes"]) > 5:
                        detailed_parts.append(f"  ... 还有 {len(file_analysis['classes']) - 5} 个类")
                
                if file_analysis.get("methods"):
                    detailed_parts.append(f"- **包含方法**: {', '.join(file_analysis['methods'][:5])}")
                    if len(file_analysis["methods"]) > 5:
                        detailed_parts.append(f"  ... 还有 {len(file_analysis['methods']) - 5} 个方法")
                
                if file_analysis.get("api_endpoints"):
                    detailed_parts.append(f"- **API端点**: {', '.join(file_analysis['api_endpoints'])}")
                
                detailed_parts.append("")
    
    # 合并内容
    if detailed_parts:
        content += "\n" + "\n".join(detailed_parts)
    
    return content

def _generate_simple_doc(analysis_result: Dict[str, Any]) -> str:
    """生成简单开发文档"""
    content = []
    
    # 标题
    content.append(f"# 开发文档摘要")
    content.append("")
    
    # 基本信息
    content.append("## 基本信息")
    content.append("")
    content.append(f"- 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if "directory_path" in analysis_result:
        content.append(f"- 分析目录: {analysis_result['directory_path']}")
    
    if "total_files_found" in analysis_result:
        content.append(f"- 文件总数: {analysis_result['total_files_found']}")
    
    content.append("")
    
    # 关键统计
    content.append("## 关键统计")
    content.append("")
    
    if "file_types" in analysis_result:
        content.append("**文件类型分布**:")
        for file_type, count in analysis_result["file_types"].items():
            content.append(f"- {file_type}: {count}")
        content.append("")
    
    if "api_endpoints" in analysis_result and analysis_result["api_endpoints"]:
        content.append(f"**API端点**: {len(analysis_result['api_endpoints'])} 个")
        # 显示前5个
        for endpoint in analysis_result["api_endpoints"][:5]:
            content.append(f"  - `{endpoint}`")
        
        if len(analysis_result["api_endpoints"]) > 5:
            content.append(f"  ... 还有 {len(analysis_result['api_endpoints']) - 5} 个")
        content.append("")
    
    # 重点关注
    content.append("## 重点关注")
    content.append("")
    content.append("1. 检查所有API接口的完整性和安全性")
    content.append("2. 验证代码注释的完整性")
    content.append("3. 确保错误处理机制完善")
    content.append("")
    
    return "\n".join(content)