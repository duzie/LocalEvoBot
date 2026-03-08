"""
Proactive Checks - 主动性检查工具

定期检查系统状态，主动提醒用户需要注意的事项。
"""

import os
import subprocess
from datetime import datetime
from typing import Dict, List
from langchain_core.tools import tool


def check_git_status() -> Dict:
    """检查 Git 状态"""
    try:
        # 检查是否有未提交的修改
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        )
        
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            return {
                "status": "warning",
                "message": f"有 {len(lines)} 个未提交的修改",
                "details": lines[:5]  # 只显示前 5 个
            }
        
        return {
            "status": "ok",
            "message": "Git 干净，没有未提交的修改"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Git 检查失败：{e}"
        }


def check_test_coverage() -> Dict:
    """检查测试覆盖率（如果有的话）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    try:
        # 尝试运行 pytest-cov
        result = subprocess.run(
            ["pytest", "--cov=app", "--cov-report=term-missing", "--co"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=base_dir
        )
        
        # 如果没有测试，pytest 会返回 0 但没有覆盖率信息
        if "no tests ran" in result.stdout.lower():
            return {
                "status": "info",
                "message": "未检测到测试文件"
            }
        
        # 解析覆盖率（简化版，实际需要运行完整测试）
        return {
            "status": "info",
            "message": "测试覆盖率检查需要运行完整测试（耗时较长，建议手动执行）"
        }
    except FileNotFoundError:
        return {
            "status": "info",
            "message": "未安装 pytest-cov，跳过覆盖率检查"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"覆盖率检查失败：{e}"
        }


def check_linter_warnings() -> Dict:
    """检查 linter 警告"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    app_dir = os.path.join(base_dir, "app")
    
    try:
        result = subprocess.run(
            ["flake8", app_dir, "--count", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # 最后一行是警告数
        output_lines = result.stderr.strip().split("\n")
        if output_lines:
            try:
                warning_count = int(output_lines[-1])
                if warning_count > 5:
                    return {
                        "status": "warning",
                        "message": f"有 {warning_count} 个 linter 警告",
                        "suggestion": "建议运行 flake8 app 查看详细警告"
                    }
                elif warning_count > 0:
                    return {
                        "status": "info",
                        "message": f"有 {warning_count} 个 linter 警告（<5 个，可接受）"
                    }
            except ValueError:
                pass
        
        return {
            "status": "ok",
            "message": "代码质量良好，无明显 linter 警告"
        }
    except FileNotFoundError:
        return {
            "status": "info",
            "message": "未安装 flake8，跳过 linter 检查"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Linter 检查失败：{e}"
        }


def check_dependency_updates() -> Dict:
    """检查依赖更新"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    requirements_path = os.path.join(base_dir, "requirements.txt")
    
    if not os.path.exists(requirements_path):
        return {
            "status": "info",
            "message": "未找到 requirements.txt"
        }
    
    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout.strip():
            import json
            outdated = json.loads(result.stdout)
            if outdated:
                packages = [pkg["name"] for pkg in outdated[:5]]
                return {
                    "status": "warning",
                    "message": f"有 {len(outdated)} 个依赖包可更新",
                    "details": packages,
                    "suggestion": "运行 pip list --outdated 查看详情"
                }
        
        return {
            "status": "ok",
            "message": "所有依赖包都是最新版本"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"依赖检查失败：{e}"
        }


def check_disk_usage() -> Dict:
    """检查磁盘使用（特别是数据目录）"""
    try:
        import shutil
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.join(base_dir, "app", "data")
        
        if os.path.exists(data_dir):
            total, used, free = shutil.disk_usage(data_dir)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            
            usage_percent = (used / total) * 100
            
            if usage_percent > 90:
                return {
                    "status": "warning",
                    "message": f"数据目录磁盘使用率 {usage_percent:.1f}%",
                    "details": f"已用 {used_gb:.1f}GB / 剩余 {free_gb:.1f}GB",
                    "suggestion": "建议清理旧的记忆归档和日志文件"
                }
            elif usage_percent > 75:
                return {
                    "status": "info",
                    "message": f"数据目录磁盘使用率 {usage_percent:.1f}%",
                    "details": f"已用 {used_gb:.1f}GB / 剩余 {free_gb:.1f}GB"
                }
        
        return {
            "status": "ok",
            "message": "磁盘使用正常"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"磁盘检查失败：{e}"
        }


@tool
def proactive_check(check_type: str = "all") -> str:
    """
    执行主动性检查
    
    Args:
        check_type: 检查类型 (git/coverage/linter/deps/disk/all)
    
    Returns:
        检查报告
    """
    results = []
    warnings = []
    
    checks = {
        "git": check_git_status,
        "coverage": check_test_coverage,
        "linter": check_linter_warnings,
        "deps": check_dependency_updates,
        "disk": check_disk_usage,
    }
    
    if check_type == "all":
        checks_to_run = checks.values()
    else:
        checks_to_run = [checks.get(check_type, checks["git"])]
    
    for check_fn in checks_to_run:
        result = check_fn()
        status_icon = {"ok": "[OK]", "warning": "[WARN]", "error": "[ERR]", "info": "[INFO]"}.get(result["status"], "•")
        results.append(f"{status_icon} {result['message']}")
        
        if result["status"] == "warning":
            warnings.append(result["message"])
    
    # 添加总结
    if warnings:
        results.append(f"\n[WARN] 发现 {len(warnings)} 个需要注意的问题")
    
    return "\n".join(results)


@tool
def get_system_status() -> Dict:
    """
    获取系统整体状态
    
    Returns:
        状态报告
    """
    import psutil
    
    # CPU 和内存
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    # 进程数
    python_processes = len([p for p in psutil.process_iter() if "python" in p.name().lower()])
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_usage": f"{cpu_percent}%",
        "memory_usage": f"{memory.percent}%",
        "memory_available": f"{memory.available / (1024**2):.0f}MB",
        "python_processes": python_processes,
        "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning"
    }
