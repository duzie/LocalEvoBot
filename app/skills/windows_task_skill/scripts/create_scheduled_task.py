from langchain_core.tools import tool
import json
import subprocess
from typing import Optional, Dict, Any


def _run_powershell(ps_script: str) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@tool
def create_windows_scheduled_task(
    task_name: str,
    command: str,
    schedule: str = "daily",
    time_hhmm: str = "09:00",
    description: Optional[str] = None,
    overwrite: bool = False,
    task_path: str = "\\",
) -> Dict[str, Any]:
    """
    创建 Windows 计划任务（无需管理员权限）。

    说明:
    - 使用当前用户（交互式登录）注册，因此不需要管理员权限与密码
    - 任务仅在当前用户登录时可运行

    Args:
        task_name: 任务名称（不含路径）
        command: 要执行的命令行（通过 cmd.exe /c 执行）
        schedule: 触发类型：daily | once
        time_hhmm: 触发时间，格式 HH:mm
        description: 任务描述
        overwrite: 若任务已存在，是否覆盖
        task_path: 任务路径，例如 "\\" 或 "\\MyFolder\\"
    """
    schedule_norm = (schedule or "").strip().lower()
    if schedule_norm not in {"daily", "once"}:
        return {"success": False, "message": "schedule 仅支持 daily 或 once"}

    if not task_path or not task_path.startswith("\\"):
        return {"success": False, "message": "task_path 必须以 \\\\ 开头，例如 \\\\ 或 \\\\MyFolder\\\\"}
    if not task_path.endswith("\\"):
        task_path = task_path + "\\"

    def _ps_quote(text: str) -> str:
        return "'" + (text or "").replace("'", "''") + "'"

    safe_name = _ps_quote(task_name)
    safe_path = _ps_quote(task_path)
    safe_time = _ps_quote(time_hhmm)
    safe_desc = _ps_quote(description or "")
    safe_cmd = _ps_quote(command)
    safe_overwrite = "$true" if overwrite else "$false"
    safe_schedule = _ps_quote(schedule_norm)

    ps = f"""
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding
$taskName = {safe_name}
$taskPath = {safe_path}
$timeText = {safe_time}
$desc = {safe_desc}
$cmdLine = {safe_cmd}
$overwrite = {safe_overwrite}
$schedule = {safe_schedule}

try {{ [void][TimeSpan]::ParseExact($timeText, 'hh\\:mm', $null) }} catch {{ throw "time_hhmm 格式错误，应为 HH:mm，例如 09:00" }}

$now = Get-Date
$at = $now.Date.Add([TimeSpan]::Parse($timeText))
if ($at -lt $now) {{ $at = $at.AddDays(1) }}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ' + $cmdLine)
if ($schedule -eq 'daily') {{
  $trigger = New-ScheduledTaskTrigger -Daily -At $at
}} else {{
  $trigger = New-ScheduledTaskTrigger -Once -At $at
}}

$existing = $null
try {{ $existing = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop }} catch {{ $existing = $null }}
if ($existing -ne $null) {{
  if (-not $overwrite) {{ throw "任务已存在：$taskPath$taskName" }}
  Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false | Out-Null
}}

$userId = $env:USERDOMAIN + '\\' + $env:USERNAME
Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Action $action -Trigger $trigger -Description $desc -User $userId -RunLevel Limited -Force | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath
$out = [ordered]@{{
  success = $true
  task = ($taskPath + $taskName)
  next_run_time = $info.NextRunTime
  last_run_time = $info.LastRunTime
  last_task_result = $info.LastTaskResult
}}
$out | ConvertTo-Json -Depth 4
"""

    result = _run_powershell(ps)
    if not result.get("ok"):
        return {"success": False, "message": "创建任务失败", "error": result.get("stderr") or result.get("error") or result}

    stdout = (result.get("stdout") or "").strip()
    try:
        data = json.loads(stdout) if stdout else {}
        if isinstance(data, dict) and data.get("success") is True:
            return data
    except Exception:
        pass

    return {"success": True, "task": f"{task_path}{task_name}", "raw": stdout}
