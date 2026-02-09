from langchain_core.tools import tool
import platform
import ctypes
from ctypes import wintypes
from typing import List, Dict, Any
import subprocess
import csv
import io

# --- Ctypes setup for Process Name ---
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

def _get_process_map_tasklist() -> Dict[int, str]:
    """Get all processes as {pid: name} dict using tasklist (robust fallback)."""
    pid_map = {}
    try:
        # /NH: No Header, /FO CSV: CSV format
        cmd = 'tasklist /FO CSV /NH'
        # Use shell=True to find tasklist in path easily, suppress window if possible
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        output = subprocess.check_output(cmd, startupinfo=startupinfo, encoding="gbk", errors="ignore")
        
        f = io.StringIO(output)
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                name = row[0]
                try:
                    pid = int(row[1])
                    pid_map[pid] = name
                except ValueError:
                    pass
    except Exception:
        pass
    return pid_map

def _get_process_name(pid: int, fallback_map: Dict[int, str] = None) -> str:
    """Get process executable name from PID, with fallback."""
    if pid <= 0:
        return ""
        
    # 1. Try Ctypes (Fast)
    try:
        h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if h_process:
            name_buffer = ctypes.create_unicode_buffer(1024)
            size = psapi.GetModuleBaseNameW(h_process, 0, name_buffer, ctypes.sizeof(name_buffer) // 2)
            kernel32.CloseHandle(h_process)
            if size:
                return name_buffer.value
    except Exception:
        pass
        
    # 2. Try Fallback Map
    if fallback_map and pid in fallback_map:
        return fallback_map[pid]
        
    return ""

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

@tool
def uia_list_windows(filter_title: str = None, filter_process: str = None, show_invisible: bool = False) -> str:
    """
    列出当前所有顶级窗口的信息（标题、进程名、PID）。
    当不知道确切的 window_title 时，用此工具查找。
    
    Args:
        filter_title: (可选) 简单的字符串包含匹配，过滤标题。
        filter_process: (可选) 简单的字符串包含匹配，过滤进程名 (如 "notepad")。
        show_invisible: (可选) 是否显示不可见窗口。默认 False (仅显示可见窗口)。
    """
    if platform.system() != "Windows":
        return "错误: 仅支持 Windows"

    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        
        is_agent_admin = _is_admin()
        
        # 预先获取 fallback map (为了性能，仅当 ctypes 失败时可能需要，但为了简化逻辑，可以按需获取)
        # 这里为了稳健，如果用户指定了 process 过滤，我们最好确保能获取到 name
        # 所以先初始化为空，用到再加载
        process_map = None
        
        # 获取所有顶级窗口
        windows = desktop.windows()
        
        results = []
        for w in windows:
            try:
                # 获取基本信息
                # desktop.windows() 返回的是 wrappers
                if hasattr(w, "wrapper_object"):
                    wrapper = w.wrapper_object()
                else:
                    wrapper = w
                    
                title = wrapper.element_info.name
                pid = wrapper.element_info.process_id
                
                # print(f"DEBUG: Window {title} PID {pid}")
                
                # 获取进程名 (带 fallback)
                proc_name = _get_process_name(pid)
                if not proc_name:
                    if process_map is None:
                        process_map = _get_process_map_tasklist()
                    proc_name = _get_process_name(pid, process_map)
                
                # 过滤无标题窗口
                # 如果指定了 filter_process，即使标题为空也应该显示 (可能就是用户要找的窗口)
                # 如果 show_invisible=True，也应该显示空标题窗口
                should_skip_empty_title = (not filter_title and not filter_process and not show_invisible)
                if not title and should_skip_empty_title:
                    continue

                is_visible = wrapper.is_visible()
                if not show_invisible and not is_visible:
                    continue
                
                # 应用过滤器
                if filter_title and filter_title.lower() not in title.lower():
                    continue
                if filter_process and filter_process.lower() not in proc_name.lower():
                    continue
                
                results.append({
                    "title": title,
                    "process": proc_name,
                    "pid": pid,
                    "visible": is_visible,
                    "handle": wrapper.handle
                })
            except Exception:
                continue
                
        # 格式化输出
        if not results:
            # 如果指定了进程过滤但没找到窗口，尝试诊断进程是否存在
            if filter_process:
                if process_map is None:
                    process_map = _get_process_map_tasklist()
                
                found_pids = [str(pid) for pid, name in process_map.items() if filter_process.lower() in name.lower()]
                if found_pids:
                    msg = f"未找到匹配的窗口。\n检测到进程 '{filter_process}' 正在运行 (PID: {', '.join(found_pids)})，但未找到属于它的顶级窗口。\n可能原因：\n1. 窗口被最小化到系统托盘 (Tray)\n2. 它是后台服务或无界面进程"
                    if not is_agent_admin:
                        msg += "\n3. 权限不足 (Agent 为非管理员，目标进程可能是管理员权限，导致无法获取窗口句柄)"
                    return msg

            return "未找到匹配的窗口。"
            
        output = []
        if not is_agent_admin:
            output.append("[提示: 当前 Agent 以普通用户权限运行。若无法找到或操作管理员权限程序的窗口，请以管理员身份重启 Agent/IDE]")
            
        output.append(f"找到 {len(results)} 个窗口:")
        # 按进程名排序，方便查看
        results.sort(key=lambda x: (x['process'], x['title']))
        
        for r in results:
            vis_mark = "" if r['visible'] else "[Hidden] "
            output.append(f"- Process: {r['process']:<20} | PID: {r['pid']:<6} | Title: {vis_mark}{r['title']}")
            
        return "\n".join(output)

    except Exception as e:
        return f"列出窗口失败: {str(e)}"
