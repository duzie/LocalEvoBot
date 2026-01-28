from langchain_core.tools import tool
import os
import datetime
from typing import Dict, Any, Optional

@tool
def generate_requirements_doc(analysis_result: Dict[str, Any], 
                            output_dir: Optional[str] = None,
                            template_type: str = "standard") -> Dict[str, Any]:
    """
    生成需求文档
    
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
            filename = f"需求文档_{dir_name}_{timestamp}.md"
        else:
            filename = f"需求文档_{timestamp}.md"
        
        output_path = os.path.join(output_dir, filename)
        
        # 根据模板类型生成内容
        if template_type == "detailed":
            content = _generate_detailed_req_doc(analysis_result)
        elif template_type == "simple":
            content = _generate_simple_req_doc(analysis_result)
        else:  # standard
            content = _generate_standard_req_doc(analysis_result)
        
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

def _generate_standard_req_doc(analysis_result: Dict[str, Any]) -> str:
    """生成标准需求文档"""
    content = []
    
    # 标题
    content.append(f"# 需求文档")
    content.append("")
    
    # 文档信息
    content.append("## 文档信息")
    content.append("")
    content.append(f"- **文档版本**: 1.0")
    content.append(f"- **生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if "directory_path" in analysis_result:
        content.append(f"- **系统模块**: {os.path.basename(analysis_result['directory_path'])}")
    
    content.append(f"- **文档类型**: 基于代码分析的需求文档")
    content.append("")
    
    # 系统概述
    content.append("## 系统概述")
    content.append("")
    content.append("### 1.1 系统背景")
    content.append("本系统是基于现有代码分析得出的需求文档，主要针对SCM（供应链管理）系统的BasicSet模块。")
    content.append("")
    
    content.append("### 1.2 系统目标")
    content.append("1. 提供基础数据设置功能")
    content.append("2. 实现部门与会计中心的关联管理")
    content.append("3. 支持菜品或类型与部门的关联配置")
    content.append("4. 提供统一的错误处理机制")
    content.append("")
    
    # 功能需求
    content.append("## 功能需求")
    content.append("")
    
    # 基于API端点推断功能
    if "api_endpoints" in analysis_result and analysis_result["api_endpoints"]:
        content.append("### 2.1 API接口功能")
        content.append("")
        
        # 对API端点进行分类和描述
        api_categories = {
            "数据关联": [],
            "配置管理": [],
            "错误处理": [],
            "其他功能": []
        }
        
        for endpoint in analysis_result["api_endpoints"]:
            endpoint_lower = endpoint.lower()
            
            if any(keyword in endpoint_lower for keyword in ['rel', 'link', 'associate', 'connect']):
                api_categories["数据关联"].append(endpoint)
            elif any(keyword in endpoint_lower for keyword in ['config', 'set', 'update', 'save']):
                api_categories["配置管理"].append(endpoint)
            elif any(keyword in endpoint_lower for keyword in ['error', 'handler', 'exception']):
                api_categories["错误处理"].append(endpoint)
            else:
                api_categories["其他功能"].append(endpoint)
        
        # 输出每个类别的功能描述
        for category, endpoints in api_categories.items():
            if endpoints:
                content.append(f"#### {category}")
                content.append("")
                
                for endpoint in endpoints:
                    # 根据端点名称生成功能描述
                    description = _generate_api_description(endpoint)
                    content.append(f"- **{endpoint}**")
                    content.append(f"  - 功能描述: {description}")
                    
                    # 特别关注目标方法
                    if "RelDishOrTypeToDeptAccountingCenter" in endpoint:
                        content.append("  - **核心功能**: 菜品/类型与部门会计中心的关联管理")
                        content.append("  - **业务价值**: 实现成本核算和部门绩效评估的基础数据关联")
                    
                    content.append("")
    
    # 基于文件类型推断功能
    if "files_by_type" in analysis_result:
        content.append("### 2.2 页面功能")
        content.append("")
        
        for file_type, files in analysis_result["files_by_type"].items():
            if file_type in ['aspx', 'html']:
                content.append(f"#### {file_type.upper()} 页面功能")
                content.append("")
                
                for file_info in files[:5]:  # 只显示前5个
                    page_name = os.path.splitext(file_info['file_name'])[0]
                    content.append(f"- **{page_name}** 页面")
                    content.append(f"  - 文件: {file_info['file_name']}")
                    
                    # 根据文件名推断功能
                    func_desc = _infer_function_from_filename(page_name)
                    if func_desc:
                        content.append(f"  - 主要功能: {func_desc}")
                    
                    content.append("")
    
    # 非功能需求
    content.append("## 非功能需求")
    content.append("")
    
    content.append("### 3.1 性能需求")
    content.append("1. API响应时间应在3秒以内")
    content.append("2. 页面加载时间应在5秒以内")
    content.append("3. 支持并发用户数: 50+")
    content.append("")
    
    content.append("### 3.2 可靠性需求")
    content.append("1. 系统可用性达到99.5%")
    content.append("2. 数据一致性保证")
    content.append("3. 错误恢复机制")
    content.append("")
    
    content.append("### 3.3 安全性需求")
    content.append("1. 用户身份验证")
    content.append("2. 数据访问权限控制")
    content.append("3. 输入数据验证")
    content.append("4. SQL注入防护")
    content.append("")
    
    content.append("### 3.4 可维护性需求")
    content.append("1. 代码注释率不低于30%")
    content.append("2. 模块化设计")
    content.append("3. 配置外部化")
    content.append("")
    
    # 数据需求
    content.append("## 数据需求")
    content.append("")
    
    content.append("### 4.1 数据实体")
    content.append("基于代码分析，系统可能涉及以下数据实体：")
    content.append("")
    
    # 从类名推断数据实体
    if "classes" in analysis_result and analysis_result["classes"]:
        entity_candidates = []
        for class_name in analysis_result["classes"]:
            if any(keyword in class_name.lower() for keyword in ['model', 'entity', 'dto', 'vo', 'info']):
                entity_candidates.append(class_name)
        
        if entity_candidates:
            for entity in entity_candidates[:10]:  # 只显示前10个
                content.append(f"- **{entity}**: 数据实体类")
        else:
            content.append("- 部门信息实体")
            content.append("- 会计中心实体")
            content.append("- 菜品/类型实体")
            content.append("- 关联关系实体")
    
    content.append("")
    
    content.append("### 4.2 数据关系")
    content.append("1. 部门与会计中心的多对一关系")
    content.append("2. 菜品/类型与部门的多对多关系")
    content.append("3. 关联关系的时间有效性")
    content.append("")
    
    # 接口需求
    content.append("## 接口需求")
    content.append("")
    
    content.append("### 5.1 内部接口")
    content.append("1. ErrorCodeHandler.ashx: 统一错误处理接口")
    content.append("2. 数据访问接口")
    content.append("3. 业务逻辑接口")
    content.append("")
    
    content.append("### 5.2 外部接口")
    content.append("1. 财务系统接口（如需要）")
    content.append("2. 人力资源系统接口（如需要）")
    content.append("3. 供应链系统接口")
    content.append("")
    
    # 约束条件
    content.append("## 约束条件")
    content.append("")
    
    content.append("### 6.1 技术约束")
    content.append("1. 基于ASP.NET技术栈")
    content.append("2. 使用C#编程语言")
    content.append("3. 支持IE11及以上浏览器")
    content.append("")
    
    content.append("### 6.2 业务约束")
    content.append("1. 符合公司财务制度")
    content.append("2. 遵循供应链管理规范")
    content.append("3. 满足审计要求")
    content.append("")
    
    # 假设和依赖
    content.append("## 假设和依赖")
    content.append("")
    
    content.append("### 7.1 假设条件")
    content.append("1. 用户具备基本的计算机操作能力")
    content.append("2. 网络环境稳定")
    content.append("3. 数据库服务可用")
    content.append("")
    
    content.append("### 7.2 外部依赖")
    content.append("1. .NET Framework运行环境")
    content.append("2. SQL Server数据库")
    content.append("3. IIS Web服务器")
    content.append("")
    
    return "\n".join(content)

def _generate_api_description(endpoint: str) -> str:
    """根据API端点名称生成功能描述"""
    endpoint_lower = endpoint.lower()
    
    if 'reldishortypetodeptaccountingcenter' in endpoint_lower.replace(' ', '').replace('_', ''):
        return "关联菜品或类型到部门会计中心，用于成本核算和绩效评估"
    
    elif 'dish' in endpoint_lower:
        if 'type' in endpoint_lower:
            return "菜品类型管理功能"
        else:
            return "菜品管理功能"
    
    elif 'dept' in endpoint_lower or 'department' in endpoint_lower:
        if 'accounting' in endpoint_lower or 'center' in endpoint_lower:
            return "部门会计中心管理"
        else:
            return "部门管理功能"
    
    elif 'error' in endpoint_lower:
        return "错误处理功能"
    
    elif 'get' in endpoint_lower:
        return "数据查询功能"
    
    elif 'save' in endpoint_lower or 'update' in endpoint_lower:
        return "数据保存或更新功能"
    
    elif 'delete' in endpoint_lower or 'remove' in endpoint_lower:
        return "数据删除功能"
    
    elif 'list' in endpoint_lower:
        return "数据列表查询功能"
    
    elif 'config' in endpoint_lower:
        return "系统配置功能"
    
    else:
        return "系统功能接口"

def _infer_function_from_filename(filename: str) -> str:
    """根据文件名推断功能"""
    filename_lower = filename.lower()
    
    if 'dept' in filename_lower or 'department' in filename_lower:
        return "部门管理"
    
    elif 'dish' in filename_lower:
        return "菜品管理"
    
    elif 'type' in filename_lower:
        return "类型管理"
    
    elif 'accounting' in filename_lower:
        return "会计中心管理"
    
    elif 'config' in filename_lower or 'set' in filename_lower:
        return "系统配置"
    
    elif 'list' in filename_lower:
        return "数据列表"
    
    elif 'edit' in filename_lower:
        return "数据编辑"
    
    elif 'add' in filename_lower or 'new' in filename_lower:
        return "数据新增"
    
    elif 'view' in filename_lower:
        return "数据查看"
    
    elif 'report' in filename_lower:
        return "报表功能"
    
    else:
        return "系统功能页面"

def _generate_detailed_req_doc(analysis_result: Dict[str, Any]) -> str:
    """生成详细需求文档"""
    content = _generate_standard_req_doc(analysis_result)
    
    # 添加更多详细内容
    detailed_parts = []
    
    # 添加用例分析
    detailed_parts.append("## 用例分析")
    detailed_parts.append("")
    
    # 基于API端点创建用例
    if "api_endpoints" in analysis_result and analysis_result["api_endpoints"]:
        detailed_parts.append("### 主要业务用例")
        detailed_parts.append("")
        
        for i, endpoint in enumerate(analysis_result["api_endpoints"][:10], 1):  # 只显示前10个
            detailed_parts.append(f"#### 用例{i}: {endpoint}")
            detailed_parts.append("")
            detailed_parts.append("**主要参与者**: 系统管理员/业务用户")
            detailed_parts.append("")
            detailed_parts.append("**前置条件**:")
            detailed_parts.append("1. 用户已登录系统")
            detailed_parts.append("2. 用户具有相应操作权限")
            detailed_parts.append("")
            
            detailed_parts.append("**基本流程**:")
            detailed_parts.append("1. 用户访问相关功能页面")
            detailed_parts.append("2. 系统显示操作界面")
            detailed_parts.append("3. 用户输入必要数据")
            detailed_parts.append("4. 系统调用API接口处理请求")
            detailed_parts.append("5. 系统返回处理结果")
            detailed_parts.append("")
            
            detailed_parts.append("**后置条件**:")
            detailed_parts.append("1. 数据被正确保存或更新")
            detailed_parts.append("2. 系统状态保持一致")
            detailed_parts.append("")
            
            detailed_parts.append("**异常流程**:")
            detailed_parts.append("1. 数据验证失败")
            detailed_parts.append("2. 权限不足")
            detailed_parts.append("3. 系统异常")
            detailed_parts.append("")
    
    # 合并内容
    if detailed_parts:
        content += "\n" + "\n".join(detailed_parts)
    
    return content

def _generate_simple_req_doc(analysis_result: Dict[str, Any]) -> str:
    """生成简单需求文档"""
    content = []
    
    # 标题
    content.append(f"# 需求文档摘要")
    content.append("")
    
    # 基本信息
    content.append("## 基本信息")
    content.append("")
    content.append(f"- 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if "directory_path" in analysis_result:
        content.append(f"- 系统模块: {os.path.basename(analysis_result['directory_path'])}")
    
    content.append("")
    
    # 核心功能
    content.append("## 核心功能需求")
    content.append("")
    
    # 基于API端点
    if "api_endpoints" in analysis_result and analysis_result["api_endpoints"]:
        content.append("**主要API功能**:")
        for endpoint in analysis_result["api_endpoints"][:8]:  # 只显示前8个
            desc = _generate_api_description(endpoint)
            content.append(f"- {endpoint}: {desc}")
        content.append("")
    
    # 关键需求
    content.append("## 关键需求")
    content.append("")
    content.append("1. **数据关联管理**: 支持菜品/类型与部门会计中心的关联")
    content.append("2. **错误处理**: 统一的错误处理机制")
    content.append("3. **权限控制**: 基于角色的访问控制")
    content.append("4. **数据验证**: 输入数据的有效性验证")
    content.append("")
    
    # 约束条件
    content.append("## 主要约束")
    content.append("")
    content.append("- 技术栈: ASP.NET + C#")
    content.append("- 数据库: SQL Server")
    content.append("- 浏览器兼容性: IE11+")
    content.append("")
    
    return "\n".join(content)