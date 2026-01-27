from langchain_core.tools import tool
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import html

class PurchaseDocumentationGenerator:
@tool
    def __init__(self, aspx_file_path: str, app_code_path: str, output_dir: str):
        self.aspx_file_path = Path(aspx_file_path)
        self.app_code_path = Path(app_code_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 存储分析结果
        self.api_calls = []
        self.handlers = {}
        self.common_classes = {}
        self.entity_classes = {}
        
    def read_file_content(self, file_path: Path) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            return ""
    
    def analyze_aspx_file(self) -> List[Dict]:
        """分析ASPX文件中的API调用"""
        content = self.read_file_content(self.aspx_file_path)
        if not content:
            return []
        
        api_calls = []
        
        # 查找JavaScript中的API调用
        js_patterns = [
            r'\.ajax\s*\(\s*\{[^}]*url\s*:\s*[\'"]([^\'"]+)[\'"]',
            r'\.post\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'\.get\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'fetch\s*\(\s*[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in js_patterns:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                if 'ErrorCodeHandler.ashx' in url:
                    # 提取methodName参数
                    method_match = re.search(r'methodName\s*[:=]\s*[\'"]([^\'"]+)[\'"]', 
                                           content[match.start():match.start()+500])
                    method_name = method_match.group(1) if method_match else "unknown"
                    
                    api_calls.append({
                        'type': 'ajax',
                        'url': url,
                        'method': method_name,
                        'context': content[max(0, match.start()-200):match.end()+200]
                    })
        
        # 查找服务器端代码中的API调用
        server_patterns = [
            r'LanguageTool\.GetLanguage\(\)',
            r'SystemTool\.GetWdatePickerLangStringOld\(\)',
            r'console\.log\([^)]+\)',
        ]
        
        for pattern in server_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                api_calls.append({
                    'type': 'server',
                    'method': match.group(0),
                    'context': content[max(0, match.start()-100):match.end()+100]
                })
        
        return api_calls
    
    def find_handler_implementation(self, method_name: str) -> Dict:
        """在App_Code中查找处理器实现"""
        handler_file = None
        
        # 首先在Handlers/SCM目录中查找
        scm_handlers_dir = self.app_code_path / "Handlers" / "SCM"
        if scm_handlers_dir.exists():
            for file in scm_handlers_dir.glob("*.cs"):
                content = self.read_file_content(file)
                if f'class.*{method_name}' in content or f'class.*{method_name.capitalize()}' in content:
                    handler_file = file
                    break
        
        # 如果没有找到，在Common目录中查找
        if not handler_file:
            common_dir = self.app_code_path / "Common"
            if common_dir.exists():
                for file in common_dir.glob("*.cs"):
                    content = self.read_file_content(file)
                    if method_name in content:
                        handler_file = file
                        break
        
        if handler_file:
            return {
                'file_path': str(handler_file),
                'file_name': handler_file.name,
                'content_preview': self.read_file_content(handler_file)[:2000]
            }
        
        return None
    
    def analyze_common_classes(self):
        """分析Common目录中的通用类"""
        common_dir = self.app_code_path / "Common"
        if not common_dir.exists():
            return
        
        for file in common_dir.glob("*.cs"):
            content = self.read_file_content(file)
            class_match = re.search(r'class\s+(\w+)', content)
            if class_match:
                class_name = class_match.group(1)
                self.common_classes[class_name] = {
                    'file_path': str(file),
                    'file_name': file.name,
                    'methods': self.extract_methods(content),
                    'size': file.stat().st_size
                }
    
    def extract_methods(self, content: str) -> List[str]:
        """从C#代码中提取方法"""
        methods = []
        pattern = r'(public|private|protected|internal)\s+(static\s+)?(\w+\s+)?(\w+)\s*\([^)]*\)\s*{'
        matches = re.finditer(pattern, content)
        for match in matches:
            methods.append(match.group(4))
        return methods[:20]  # 只返回前20个方法
    
    def generate_documentation(self) -> str:
        """生成完整的开发文档"""
        print("开始分析ASPX文件...")
        self.api_calls = self.analyze_aspx_file()
        
        print("分析Common类...")
        self.analyze_common_classes()
        
        print("查找处理器实现...")
        for api_call in self.api_calls:
            if api_call['type'] == 'ajax' and 'method' in api_call:
                handler_info = self.find_handler_implementation(api_call['method'])
                if handler_info:
                    self.handlers[api_call['method']] = handler_info
        
        # 生成Markdown文档
        doc_content = self._create_markdown_document()
        
        # 保存文档
        output_file = self.output_dir / f"{self.aspx_file_path.stem}_原始开发文档.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        print(f"文档已生成: {output_file}")
        return str(output_file)
    
    def _create_markdown_document(self) -> str:
        """创建Markdown格式的文档"""
        doc = []
        
        # 标题
        doc.append(f"# {self.aspx_file_path.name} 原始开发文档\n")
        doc.append(f"**生成时间**: {self._get_current_time()}\n")
        doc.append(f"**文件路径**: `{self.aspx_file_path}`\n")
        doc.append(f"**文件大小**: {self.aspx_file_path.stat().st_size / 1024:.2f} KB\n")
        doc.append(f"**最后修改**: {self._get_file_time(self.aspx_file_path)}\n")
        
        # 概述
        doc.append("\n## 1. 概述")
        doc.append(f"这是一个采购入库单管理页面，位于供应链管理(SCM)模块中。")
        doc.append(f"页面包含 {len(self.api_calls)} 个API调用。\n")
        
        # API调用分析
        doc.append("\n## 2. API调用分析")
        
        # AJAX API调用
        ajax_calls = [call for call in self.api_calls if call['type'] == 'ajax']
        if ajax_calls:
            doc.append("\n### 2.1 AJAX API调用")
            doc.append("| 序号 | 方法名 | URL | 处理器文件 |")
            doc.append("|------|--------|-----|------------|")
            for i, call in enumerate(ajax_calls, 1):
                handler_info = self.handlers.get(call['method'], {})
                handler_file = handler_info.get('file_name', '未找到')
                doc.append(f"| {i} | `{call['method']}` | `{call['url']}` | `{handler_file}` |")
        
        # 服务器端API调用
        server_calls = [call for call in self.api_calls if call['type'] == 'server']
        if server_calls:
            doc.append("\n### 2.2 服务器端API调用")
            for call in server_calls:
                doc.append(f"- **{call['method']}**")
                doc.append(f"  ```csharp\n  {call['context'].strip()}\n  ```")
        
        # 处理器实现
        doc.append("\n## 3. 处理器实现 (App_Code)")
        if self.handlers:
            for method_name, handler_info in self.handlers.items():
                doc.append(f"\n### 3.{list(self.handlers.keys()).index(method_name)+1} {method_name}")
                doc.append(f"**文件**: `{handler_info['file_path']}`")
                doc.append(f"**大小**: {handler_info.get('size', '未知')} 字节")
                doc.append("\n**代码预览**:")
                doc.append("```csharp")
                doc.append(handler_info['content_preview'])
                doc.append("```")
        else:
            doc.append("\n未找到对应的处理器实现。")
        
        # Common类分析
        doc.append("\n## 4. 通用类库 (Common)")
        if self.common_classes:
            doc.append("\n| 类名 | 文件 | 方法数量 | 大小 |")
            doc.append("|------|------|----------|------|")
            for class_name, class_info in self.common_classes.items():
                methods_count = len(class_info.get('methods', []))
                size_kb = class_info.get('size', 0) / 1024
                doc.append(f"| `{class_name}` | `{class_info['file_name']}` | {methods_count} | {size_kb:.1f} KB |")
            
            # 详细分析关键类
            key_classes = ['LanguageTool', 'SystemTool', 'Security', 'DBOperator']
            for class_name in key_classes:
                if class_name in self.common_classes:
                    doc.append(f"\n### 4.{key_classes.index(class_name)+1} {class_name}")
                    class_info = self.common_classes[class_name]
                    doc.append(f"**文件**: `{class_info['file_path']}`")
                    doc.append(f"**主要方法**:")
                    for method in class_info.get('methods', [])[:10]:
                        doc.append(f"- `{method}`")
        else:
            doc.append("\n未找到Common目录。")
        
        # 文件结构
        doc.append("\n## 5. 文件结构")
        doc.append("\n### 5.1 App_Code目录结构")
        doc.append("```")
        self._append_directory_structure(doc, self.app_code_path, 0)
        doc.append("```")
        
        # 使用说明
        doc.append("\n## 6. 使用说明")
        doc.append("""
### 6.1 主要功能
1. **采购入库单管理**: 创建、编辑、删除采购入库单
2. **物料管理**: 物料选择、数量、单价、总价计算
3. **多语言支持**: 使用LanguageTool进行国际化
4. **数据验证**: 业务规则验证（数量、价格、日期等）
5. **打印功能**: 支持采购单打印

### 6.2 技术特点
- **前端框架**: EasyUI + Bootstrap
- **多语言**: 完整的国际化支持
- **AJAX交互**: 通过ErrorCodeHandler.ashx进行数据交互
- **表格编辑**: 支持行内编辑和批量操作

### 6.3 开发注意事项
1. 所有业务逻辑都在App_Code/Handlers/SCM目录中
2. 多语言处理使用LanguageTool类
3. 数据库操作使用DBOperator类
4. 权限验证使用Security类
""")
        
        # 附录
        doc.append("\n## 附录")
        doc.append("\n### A. 相关文件")
        doc.append(f"- **主页面**: `{self.aspx_file_path.name}`")
        doc.append(f"- **处理器目录**: `App_Code/Handlers/SCM/`")
        doc.append(f"- **通用类库**: `App_Code/Common/`")
        
        doc.append("\n### B. 修改记录")
        doc.append("| 日期 | 修改内容 | 修改人 |")
        doc.append("|------|----------|--------|")
        doc.append(f"| {self._get_file_time(self.aspx_file_path)} | 初始创建 | 系统 |")
        
        return "\n".join(doc)
    
    def _get_current_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_file_time(self, file_path: Path) -> str:
        """获取文件时间"""
        try:
            mtime = file_path.stat().st_mtime
            from datetime import datetime
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return "未知"
    
    def _append_directory_structure(self, doc: List[str], path: Path, level: int):
        """追加目录结构"""
        indent = "  " * level
        
        if path.is_dir():
            doc.append(f"{indent}{path.name}/")
            try:
                items = list(path.iterdir())
                # 先显示目录，再显示文件
                dirs = [item for item in items if item.is_dir()]
                files = [item for item in items if item.is_file()]
                
                for dir_item in sorted(dirs, key=lambda x: x.name):
                    self._append_directory_structure(doc, dir_item, level + 1)
                
                for file_item in sorted(files, key=lambda x: x.name):
                    size = file_item.stat().st_size
                    size_str = f" ({size/1024:.1f} KB)" if size > 1024 else f" ({size} B)"
                    doc.append(f"{indent}  {file_item.name}{size_str}")
            except PermissionError:
                doc.append(f"{indent}  [权限不足]")
        else:
            size = path.stat().st_size
            size_str = f" ({size/1024:.1f} KB)" if size > 1024 else f" ({size} B)"
            doc.append(f"{indent}{path.name}{size_str}")

def generate_purchase_documentation(aspx_file_path: str, app_code_path: str, output_dir: str) -> Dict[str, Any]:
    """
    生成采购入库页面的原始开发文档
    
    Args:
        aspx_file_path: ASPX文件路径
        app_code_path: App_Code目录路径
        output_dir: 输出目录
        
    Returns:
        包含生成结果的字典
    """
    try:
        generator = PurchaseDocumentationGenerator(aspx_file_path, app_code_path, output_dir)
        output_file = generator.generate_documentation()
        
        return {
            "success": True,
            "output_file": output_file,
            "api_calls_count": len(generator.api_calls),
            "handlers_found": len(generator.handlers),
            "common_classes": len(generator.common_classes),
            "message": f"文档已成功生成到: {output_file}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"生成文档失败: {e}"
        }