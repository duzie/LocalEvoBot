"""
Safe File Editing Tools - 安全文件编辑工具

提供文件编辑的备份、验证、回滚功能。
基于 quick_edit 增强，添加完整的代码质量保障。
"""

import os
import shutil
import json
import ast
from datetime import datetime
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


# ============================================================================
# 备份管理器
# ============================================================================

class BackupManager:
    """备份管理器"""
    
    def __init__(self, backup_dir: str = None):
        if backup_dir:
            self.backup_dir = backup_dir
        else:
            # 默认备份目录：app/data/backups
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self.backup_dir = os.path.join(base_dir, "app", "data", "backups")
        
        os.makedirs(self.backup_dir, exist_ok=True)
        self._ensure_history_file()
    
    def _ensure_history_file(self):
        """确保备份历史文件存在"""
        info_file = os.path.join(self.backup_dir, "backup_history.json")
        if not os.path.exists(info_file):
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump({"backups": []}, f, ensure_ascii=False, indent=2)
    
    def create_backup(self, file_path: str, reason: str = "") -> Dict[str, Any]:
        """
        创建文件备份
        
        Args:
            file_path: 文件路径
            reason: 备份原因
            
        Returns:
            备份结果
        """
        try:
            if not os.path.exists(file_path):
                return {"ok": False, "error": f"文件不存在：{file_path}"}
            
            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.basename(file_path)
            backup_name = f"{base_name}.{timestamp}.backup"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # 复制文件
            shutil.copy2(file_path, backup_path)
            
            # 保存备份信息
            self._save_backup_info(file_path, backup_path, timestamp, reason)
            
            return {
                "ok": True,
                "message": "备份成功",
                "backup_path": backup_path,
                "timestamp": timestamp
            }
            
        except Exception as e:
            return {"ok": False, "error": f"备份失败：{e}"}
    
    def rollback(self, backup_path: str) -> Dict[str, Any]:
        """
        回滚到备份
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            回滚结果
        """
        try:
            if not os.path.exists(backup_path):
                return {"ok": False, "error": f"备份文件不存在：{backup_path}"}
            
            # 读取备份信息
            info = self._load_backup_info(backup_path)
            if info:
                original_path = info["original_path"]
            else:
                # 尝试从文件名解析
                original_path = self._parse_original_path(backup_path)
            
            if not original_path:
                return {"ok": False, "error": "无法确定原始文件路径"}
            
            # 恢复文件
            shutil.copy2(backup_path, original_path)
            
            return {
                "ok": True,
                "message": "回滚成功",
                "original_path": original_path,
                "backup_path": backup_path
            }
            
        except Exception as e:
            return {"ok": False, "error": f"回滚失败：{e}"}
    
    def list_backups(self, file_path: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        列出备份历史
        
        Args:
            file_path: 文件路径（可选，过滤特定文件的备份）
            limit: 最多返回数量
            
        Returns:
            备份列表
        """
        try:
            info_file = os.path.join(self.backup_dir, "backup_history.json")
            if not os.path.exists(info_file):
                return {"ok": True, "count": 0, "backups": []}
            
            with open(info_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                backups = history.get("backups", [])
            
            # 过滤特定文件的备份
            if file_path:
                abs_path = os.path.abspath(file_path)
                backups = [b for b in backups if b.get("original_path") == abs_path]
            
            # 按时间排序（最新的在前）
            backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # 限制数量
            return {
                "ok": True,
                "count": len(backups),
                "backups": backups[:limit]
            }
            
        except Exception as e:
            return {"ok": False, "error": f"列出备份失败：{e}"}
    
    def cleanup_old_backups(self, file_path: str = None, keep: int = 5) -> Dict[str, Any]:
        """
        清理旧备份
        
        Args:
            file_path: 文件路径（可选，清理特定文件的备份）
            keep: 保留最近 N 个备份
            
        Returns:
            清理结果
        """
        try:
            result = self.list_backups(file_path, limit=100)
            if not result["ok"]:
                return result
            
            backups = result["backups"]
            deleted = 0
            
            # 删除旧备份
            for backup in backups[keep:]:
                backup_path = backup.get("backup_path")
                if backup_path and os.path.exists(backup_path):
                    os.remove(backup_path)
                    deleted += 1
            
            # 更新备份历史
            if file_path:
                self._update_backup_history(file_path, backups[:keep])
            
            return {
                "ok": True,
                "message": f"清理完成，删除 {deleted} 个旧备份",
                "deleted_count": deleted
            }
            
        except Exception as e:
            return {"ok": False, "error": f"清理失败：{e}"}
    
    def _save_backup_info(self, original_path: str, backup_path: str, timestamp: str, reason: str):
        """保存备份信息"""
        info_file = os.path.join(self.backup_dir, "backup_history.json")
        
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = {"backups": []}
        
        history["backups"].append({
            "original_path": os.path.abspath(original_path),
            "backup_path": backup_path,
            "timestamp": timestamp,
            "reason": reason
        })
        
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def _load_backup_info(self, backup_path: str) -> Optional[Dict]:
        """加载备份信息"""
        info_file = os.path.join(self.backup_dir, "backup_history.json")
        if not os.path.exists(info_file):
            return None
        
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for backup in history.get("backups", []):
                    if backup.get("backup_path") == backup_path:
                        return backup
        except:
            pass
        
        return None
    
    def _parse_original_path(self, backup_path: str) -> str:
        """从备份文件名解析原始路径"""
        base_name = os.path.basename(backup_path)
        parts = base_name.split('.')
        
        if len(parts) >= 4 and parts[-1] == 'backup':
            original_name = '.'.join(parts[:-2])
            return os.path.join(os.path.dirname(backup_path), original_name)
        
        return ""
    
    def _update_backup_history(self, file_path: str, backups: List[Dict]):
        """更新备份历史"""
        info_file = os.path.join(self.backup_dir, "backup_history.json")
        
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = {"backups": []}
        
        # 更新特定文件的备份
        abs_path = os.path.abspath(file_path)
        history["backups"] = [b for b in history["backups"] if b.get("original_path") != abs_path]
        history["backups"].extend(backups)
        
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


# ============================================================================
# 代码验证器
# ============================================================================

class CodeVerifier:
    """代码验证器"""
    
    def verify_syntax(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        验证语法
        
        Args:
            file_path: 文件路径
            content: 代码内容
            
        Returns:
            验证结果
        """
        if file_path.endswith('.py'):
            try:
                compile(content, file_path, 'exec')
                return {"ok": True, "message": "语法正确"}
            except SyntaxError as e:
                return {
                    "ok": False,
                    "error": f"语法错误 (行{e.lineno}): {e.msg}"
                }
        
        # 其他语言暂时跳过语法验证
        return {"ok": True, "message": "已跳过语法验证（非 Python 文件）"}
    
    def check_imports(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """
        检查新增的导入
        
        Args:
            old_content: 旧内容
            new_content: 新内容
            
        Returns:
            检查结果
        """
        old_imports = set(self._extract_imports(old_content))
        new_imports = set(self._extract_imports(new_content))
        
        added_imports = list(new_imports - old_imports)
        removed_imports = list(old_imports - new_imports)
        
        return {
            "ok": True,
            "added_imports": added_imports,
            "removed_imports": removed_imports,
            "has_new_imports": len(added_imports) > 0
        }
    
    def _extract_imports(self, code: str) -> List[str]:
        """提取导入语句"""
        imports = []
        for line in code.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
        return imports


# ============================================================================
# 工具函数
# ============================================================================

@tool
def create_backup(file_path: str, reason: str = "") -> Dict[str, Any]:
    """
    创建文件备份
    
    Args:
        file_path: 文件路径
        reason: 备份原因
        
    Returns:
        备份结果
    """
    manager = BackupManager()
    return manager.create_backup(file_path, reason)


@tool
def safe_edit_file(file_path: str, old_text: str, new_text: str, 
                   create_backup: bool = True, verify: bool = True) -> Dict[str, Any]:
    """
    安全编辑文件
    
    Args:
        file_path: 文件路径
        old_text: 要替换的文本
        new_text: 新文本
        create_backup: 是否创建备份（默认 True）
        verify: 是否验证语法（默认 True）
        
    Returns:
        编辑结果
    """
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {"ok": False, "error": f"文件不存在：{file_path}"}
        
        # 2. 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    old_content = f.read()
            except Exception as e:
                return {"ok": False, "error": f"无法读取文件：{e}"}
        
        # 3. 检查匹配
        if old_text not in old_content:
            return {
                "ok": False,
                "error": "找不到要替换的文本",
                "suggestion": "请检查 old_text 是否完全匹配（包括空格和换行）"
            }
        
        # 4. 创建备份
        backup_path = None
        if create_backup:
            manager = BackupManager()
            backup_result = manager.create_backup(file_path, "编辑前备份")
            if backup_result["ok"]:
                backup_path = backup_result["backup_path"]
        
        # 5. 替换
        new_content = old_content.replace(old_text, new_text)
        
        # 6. 验证语法
        if verify and file_path.endswith('.py'):
            verifier = CodeVerifier()
            syntax_result = verifier.verify_syntax(file_path, new_content)
            if not syntax_result["ok"]:
                # 语法验证失败，回滚
                if backup_path:
                    manager.rollback(backup_path)
                return {
                    "ok": False,
                    "error": f"语法验证失败：{syntax_result['error']}",
                    "backed_up": True,
                    "backup_path": backup_path,
                    "action": "已自动回滚"
                }
        
        # 7. 写回
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return {"ok": False, "error": f"写入失败：{e}"}
        
        # 8. 检查导入变化
        import_changes = {"added": [], "removed": []}
        if verify:
            verifier = CodeVerifier()
            import_result = verifier.check_imports(old_content, new_content)
            import_changes = {
                "added": import_result.get("added_imports", []),
                "removed": import_result.get("removed_imports", [])
            }
        
        # 9. 返回结果
        return {
            "ok": True,
            "message": "编辑成功",
            "backup_path": backup_path,
            "replaced_count": old_content.count(old_text),
            "import_changes": import_changes,
            "changes": {
                "old_lines": len(old_content.split('\n')),
                "new_lines": len(new_content.split('\n')),
                "diff": len(new_content.split('\n')) - len(old_content.split('\n'))
            }
        }
        
    except Exception as e:
        return {"ok": False, "error": f"编辑失败：{e}"}


@tool
def rollback_edit(backup_path: str) -> Dict[str, Any]:
    """
    回滚文件编辑
    
    Args:
        backup_path: 备份文件路径
        
    Returns:
        回滚结果
    """
    manager = BackupManager()
    return manager.rollback(backup_path)


@tool
def verify_edit(file_path: str, new_content: str) -> Dict[str, Any]:
    """
    验证文件编辑
    
    Args:
        file_path: 文件路径
        new_content: 新内容
        
    Returns:
        验证结果
    """
    verifier = CodeVerifier()
    
    # 语法验证
    syntax_result = verifier.verify_syntax(file_path, new_content)
    
    # 读取旧内容
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
        
        # 检查导入变化
        import_result = verifier.check_imports(old_content, new_content)
    except:
        import_result = {"added_imports": [], "removed_imports": [], "has_new_imports": False}
    
    return {
        "ok": syntax_result["ok"],
        "syntax_valid": syntax_result["ok"],
        "import_changes": import_result,
        "warnings": [] if syntax_result["ok"] else [syntax_result.get("error", "")],
        "suggestions": [
            "建议运行测试验证功能",
            "建议调用 review_code 审查代码质量"
        ] if syntax_result["ok"] else ["修复语法错误后再保存"]
    }


@tool
def list_backups(file_path: str = None, limit: int = 10) -> Dict[str, Any]:
    """
    列出备份历史
    
    Args:
        file_path: 文件路径（可选）
        limit: 最多返回数量
        
    Returns:
        备份列表
    """
    manager = BackupManager()
    return manager.list_backups(file_path, limit)


@tool
def cleanup_old_backups(file_path: str = None, keep: int = 5) -> Dict[str, Any]:
    """
    清理旧备份
    
    Args:
        file_path: 文件路径（可选）
        keep: 保留最近 N 个备份
        
    Returns:
        清理结果
    """
    manager = BackupManager()
    return manager.cleanup_old_backups(file_path, keep)


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 测试备份
    print("测试备份功能...")
    result = create_backup.invoke({
        "file_path": "test.py",
        "reason": "测试备份"
    })
    print(f"备份结果：{result}")
    
    # 测试列出备份
    print("\n测试列出备份...")
    result = list_backups.invoke({})
    print(f"备份列表：{result}")
