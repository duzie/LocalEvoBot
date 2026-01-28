from langchain_core.tools import tool
import os
import datetime
from typing import Dict, Any, Optional
from ..code_analysis_skill.scripts.analyze_code_file import analyze_code_file

@tool
def generate_file_documentation(file_path: Optional[str] = None,
                              output_dir: Optional[str] = None,
                              doc_type: str = "both") -> Dict[str, Any]:
    """
    为单个文件生成文档
    
    Args:
        file_path: 文件路径
        output_dir: 输出目录
        doc_type: 文档类型：dev, req, both
        
    Returns:
        包含生成结果的字典
    """
    try:
        if file_path is None:
            return {"success": False, "error": "文件路径不能为空"}
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        # 分析文件
        analysis_result = analyze_code_file(file_path)
        if not analysis_result.get("success"):
            return {"success": False, "error": f"文件分析失败: {analysis_result.get('error')}"}
        
        # 确定输出目录
        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), "file_docs")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        results = []
        
        # 生成开发文档
        if doc_type in ["dev", "both"]:
            dev_doc_result = _generate_file_dev_doc(analysis_result, output_dir)
            if dev_doc_result.get("success"):
                results.append({
                    "type": "development",
                    "path": dev_doc_result["output_path"],
                    "filename": dev_doc_result["filename"]
                })
        
        # 生成需求文档
        if doc_type in ["req", "both"]:
            req_doc_result = _generate_file_req_doc(analysis_result, output_dir)
            if req_doc_result.get("success"):
                results.append({
                    "type": "requirements",
                    "path": req_doc_result["output_path"],
                    "filename": req_doc_result["filename"]
                })
        
        return {
            "success": True,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_type": analysis_result.get("file_type"),
            "generated_docs": results,
            "analysis_summary": analysis_result.get("summary", "")
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "file_path": file_path}

def _generate_file_dev_doc(analysis_result: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """为单个文件生成开发文档"""
    try:
        file_name = analysis_result.get("file_name", "unknown")
        file_type = analysis_result.get("file_type", "unknown")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成文件名
        base_name = os.path.splitext(file_name)[0]
        filename = f"开发文档_{base_name}_{timestamp}.md"
        output_path = os.path.join(output_dir, filename)
        
        # 生成文档内容
        content = _create_file_dev_content(analysis_result)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "output_path": output_path,
            "filename": filename,
            "file_size": os.path.getsize(output_path)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def _generate_file_req_doc(analysis_result: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """为单个文件生成需求文档"""
    try:
        file_name = analysis_result.get("file_name", "unknown")
        file_type = analysis_result.get("file_type", "unknown")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成文件名
        base_name = os.path.splitext(file_name)[0]
        filename = f"需求文档_{base_name}_{timestamp}.md"
        output_path = os.path.join(output_dir, filename)
        
        # 生成文档内容
        content = _create_file_req_content(analysis_result)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "output_path": output_path,
            "filename": filename,
            "file_size": os.path.getsize(output_path)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def _create_file_dev_content(analysis_result: Dict[str, Any]) -> str:
    """创建文件开发文档内容"""
    content = []
    
    # 标题
    file_name = analysis_result.get("file_name", "未知文件")
    content.append(f"# {file_name} - 开发文档")
    content.append("")
    
    # 文件信息
    content.append("## 文件信息")
    content.append("")
    content.append(f"- **文件名**: {file_name}")
    content.append(f"- **文件类型**: {analysis_result.get('file_type', '未知')}")
    content.append(f"- **文件路径**: `{analysis_result.get('file_path', '未知')}`")
    content.append(f"- **文件大小**: {analysis_result.get('file_size', 0)} 字节")
    content.append(f"- **生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    # 文件摘要
    if analysis_result.get("summary"):
        content.append("## 文件摘要")
        content.append("")
        content.append(analysis_result["summary"])
        content.append("")
    
    # 详细分析
    file_type = analysis_result.get("file_type", "")
    
    if file_type == 'cs':
        content.append("## C#文件分析")
        content.append("")
        
        if analysis_result.get("classes"):
            content.append("### 类定义")
            content.append("")
            for class_name in analysis_result["classes"]:
                content.append(f"- `{class_name}`")
            content.append("")
        
        if analysis_result.get("methods"):
            content.append("### 方法定义")
            content.append("")
            for method_name in analysis_result["methods"]:
                content.append(f"- `{method_name}`")
            content.append("")
        
        if analysis_result.get("imports"):
            content.append("### 引用命名空间")
            content.append("")
            for import_stmt in analysis_result["imports"]:
                content.append(f"- `using {import_stmt};`")
            content.append("")
    
    elif file_type == 'aspx':
        content.append("## ASPX文件分析")
        content.append("")
        
        if analysis_result.get("controls"):
            content.append("### 控件列表")
            content.append("")
            for control in analysis_result["controls"]:
                content.append(f"- {control}")
            content.append("")
        
        if analysis_result.get("code_behind"):
            content.append("### 代码后置文件")
            content.append("")
            content.append(f"`{analysis_result['code_behind']}`")
            content.append("")
        
        if analysis_result.get("script_blocks"):
            content.append("### 脚本块")
            content.append("")
            content.append(f"包含 {len(analysis_result['script_blocks'])} 个脚本块")
            content.append("")
    
    elif file_type == 'ashx':
        content.append("## ASHX文件分析")
        content.append("")
        
        if analysis_result.get("handler_class"):
            content.append("### Handler类")
            content.append("")
            content.append(f"`{analysis_result['handler_class']}`")
            content.append("")
        
        if analysis_result.get("process_request"):
            content.append("### ProcessRequest方法")
            content.append("")
            content.append("包含 `ProcessRequest` 方法，用于处理HTTP请求")
            content.append("")
        
        if analysis_result.get("methods"):
            content.append("### 其他方法")
            content.append("")
            for method_name in analysis_result["methods"]:
                content.append(f"- `{method_name}`")
            content.append("")
    
    elif file_type == 'js':
        content.append("## JavaScript文件分析")
        content.append("")
        
        if analysis_result.get("functions"):
            content.append("### 函数定义")
            content.append("")
            for func_name in analysis_result["functions"]:
                content.append(f"- `{func_name}`")
            content.append("")
        
        if analysis_result.get("ajax_calls"):
            content.append("### AJAX调用")
            content.append("")
            for ajax_call in analysis_result["ajax_calls"][:5]:  # 只显示前5个
                content.append(f"- `{ajax_call[:100]}...`")
            content.append("")
    
    elif file_type == 'html':
        content.append("## HTML文件分析")
        content.append("")
        
        if analysis_result.get("title"):
            content.append("### 页面标题")
            content.append("")
            content.append(analysis_result["title"])
            content.append("")
        
        if analysis_result.get("forms"):
            content.append("### 表单")
            content.append("")
            content.append(f"包含 {len(analysis_result['forms'])} 个表单")
            content.append("")
    
    # API端点
    if analysis_result.get("api_endpoints"):
        content.append("## API接口端点")
        content.append("")
        for endpoint in analysis_result["api_endpoints"]:
            content.append(f"- `{endpoint}`")
        content.append("")
        
        # 特别关注目标方法
        target_method = "RelDishOrTypeToDeptAccountingCenter"
        if any(target_method in ep for ep in analysis_result["api_endpoints"]):
            content.append(f"**重点关注**: 包含目标方法 `{target_method}`")
            content.append("")
    
    # 开发说明
    content.append("## 开发说明")
    content.append("")
    
    if file_type == 'cs':
        content.append("1. **类设计**: 检查类的职责是否单一")
        content.append("2. **方法设计**: 验证方法的参数和返回值类型")
        content.append("3. **异常处理**: 确保关键操作有异常处理")
        content.append("4. **代码注释**: 为公共方法添加XML注释")
    
    elif file_type == 'aspx':
        content.append("1. **控件使用**: 验证控件的ID和属性设置")
        content.append("2. **页面布局**: 检查页面结构是否合理")
        content.append("3. **脚本管理**: 确保脚本位置适当")
        content.append("4. **样式分离**: 建议将样式移到CSS文件")
    
    elif file_type == 'ashx':
        content.append("1. **请求处理**: 验证ProcessRequest方法的实现")
        content.append("2. **参数验证**: 确保输入参数的安全性验证")
        content.append("3. **响应格式**: 统一响应数据格式")
        content.append("4. **错误处理**: 提供友好的错误信息")
    
    elif file_type == 'js':
        content.append("1. **函数封装**: 检查函数的复用性")
        content.append("2. **变量作用域**: 避免全局变量污染")
        content.append("3. **异步处理**: 确保异步操作的正确性")
        content.append("4. **浏览器兼容**: 验证跨浏览器兼容性")
    
    elif file_type == 'html':
        content.append("1. **语义化标签**: 使用合适的HTML5标签")
        content.append("2. **可访问性**: 确保页面可访问性")
        content.append("3. **响应式设计**: 支持不同设备尺寸")
        content.append("4. **性能优化**: 优化图片和资源加载")
    
    content.append("")
    
    # 修改记录
    content.append("## 修改记录")
    content.append("")
    content.append("| 日期 | 版本 | 修改说明 | 修改人 |")
    content.append("|------|------|----------|--------|")
    content.append(f"| {datetime.datetime.now().strftime('%Y-%m-%d')} | 1.0 | 初始文档生成 | 系统 |")
    content.append("")
    
    return "\n".join(content)

def _create_file_req_content(analysis_result: Dict[str, Any]) -> str:
    """创建文件需求文档内容"""
    content = []
    
    # 标题
    file_name = analysis_result.get("file_name", "未知文件")
    content.append(f"# {file_name} - 需求文档")
    content.append("")
    
    # 文件概述
    content.append("## 文件概述")
    content.append("")
    content.append(f"**文件名称**: {file_name}")
    content.append(f"**文件类型**: {analysis_result.get('file_type', '未知')}")
    content.append(f"**功能定位**: {_get_file_function_description(analysis_result)}")
    content.append("")
    
    # 功能需求
    content.append("## 功能需求")
    content.append("")
    
    file_type = analysis_result.get("file_type", "")
    
    if file_type == 'cs':
        content.append("### C#类文件功能需求")
        content.append("")
        
        if analysis_result.get("classes"):
            content.append("**主要类功能**:")
            content.append("")
            for class_name in analysis_result["classes"]:
                class_desc = _get_class_description(class_name)
                content.append(f"- **{class_name}**: {class_desc}")
            content.append("")
        
        if analysis_result.get("methods"):
            content.append("**关键方法功能**:")
            content.append("")
            for method_name in analysis_result["methods"][:10]:  # 只显示前10个
                method_desc = _get_method_description(method_name)
                content.append(f"- `{method_name}`: {method_desc}")
            content.append("")
    
    elif file_type == 'aspx':
        content.append("### ASPX页面功能需求")
        content.append("")
        
        page_name = os.path.splitext(file_name)[0]
        content.append(f"**页面名称**: {page_name}")
        content.append("")
        
        content.append("**页面功能**:")
        content.append("")
        page_func = _get_page_function_description(page_name)
        content.append(page_func)
        content.append("")
        
        if analysis_result.get("controls"):
            content.append("**界面控件需求**:")
            content.append("")
            for control in analysis_result["controls"][:10]:  # 只显示前10个
                control_desc = _get_control_description(control)
                content.append(f"- {control}: {control_desc}")
            content.append("")
    
    elif file_type == 'ashx':
        content.append("### ASHX处理器功能需求")
        content.append("")
        
        content.append("**处理器功能**: HTTP请求处理接口")
        content.append("")
        
        if analysis_result.get("handler_class"):
            content.append(f"**处理类**: {analysis_result['handler_class']}")
            content.append("")
        
        content.append("**处理需求**:")
        content.append("1. 接收HTTP请求参数")
        content.append("2. 验证请求合法性")
        content.append("3. 执行业务逻辑处理")
        content.append("4. 返回处理结果")
        content.append("5. 处理异常情况")
        content.append("")
    
    elif file_type == 'js':
        content.append("### JavaScript脚本功能需求")
        content.append("")
        
        content.append("**脚本功能**: 客户端交互逻辑")
        content.append("")
        
        if analysis_result.get("functions"):
            content.append("**主要函数功能**:")
            content.append("")
            for func_name in analysis_result["functions"][:10]:
                func_desc = _get_function_description(func_name)
                content.append(f"- `{func_name}`: {func_desc}")
            content.append("")
        
        if analysis_result.get("ajax_calls"):
            content.append("**数据交互需求**:")
            content.append("")
            content.append("需要与服务器进行以下数据交互：")
            content.append("")
            for ajax_call in analysis_result["ajax_calls"][:5]:
                content.append(f"- {_get_ajax_description(ajax_call)}")
            content.append("")
    
    elif file_type == 'html':
        content.append("### HTML页面功能需求")
        content.append("")
        
        if analysis_result.get("title"):
            content.append(f"**页面标题**: {analysis_result['title']}")
            content.append("")
        
        content.append("**页面功能需求**:")
        content.append("")
        content.append("1. 提供用户操作界面")
        content.append("2. 展示相关数据信息")
        content.append("3. 支持用户输入和交互")
        content.append("4. 响应式布局适配")
        content.append("")
    
    # API接口需求
    if analysis_result.get("api_endpoints"):
        content.append("## API接口需求")
        content.append("")
        
        for endpoint in analysis_result["api_endpoints"]:
            content.append(f"### 接口: `{endpoint}`")
            content.append("")
            
            # 根据端点生成需求
            api_reqs = _get_api_requirements(endpoint)
            for req in api_reqs:
                content.append(f"- {req}")
            
            content.append("")
    
    # 非功能需求
    content.append("## 非功能需求")
    content.append("")
    
    content.append("### 性能需求")
    content.append("1. 响应时间符合用户期望")
    content.append("2. 资源占用合理")
    content.append("3. 并发处理能力")
    content.append("")
    
    content.append("### 可靠性需求")
    content.append("1. 错误处理机制完善")
    content.append("2. 数据一致性保证")
    content.append("3. 异常恢复能力")
    content.append("")
    
    content.append("### 可维护性需求")
    content.append("1. 代码结构清晰")
    content.append("2. 注释完整准确")
    content.append("3. 配置易于修改")
    content.append("")
    
    # 约束条件