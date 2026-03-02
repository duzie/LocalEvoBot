from langchain_core.tools import tool
"""
执行 pytest 测试并返回结果。

Args:
    test_path: 测试文件或目录路径
    verbose: 是否显示详细输出（默认 True）
    stop_on_failure: 遇到失败是否停止（默认 False）
    coverage: 是否生成覆盖率报告（默认 True）

Returns:
    包含测试结果的字典
"""
import os
import subprocess
import json
import tempfile
from pathlib import Path


@tool
def run_pytest(
    test_path: str,
    verbose: bool = True,
    stop_on_failure: bool = False,
    coverage: bool = True
) -> dict:
    """
    执行 pytest 测试并返回结果
    
    Args:
        test_path: 测试文件或目录路径
        verbose: 是否显示详细输出
        stop_on_failure: 遇到失败是否停止
        coverage: 是否生成覆盖率报告
    
    Returns:
        包含测试结果的字典
    """
    try:
        # 验证路径存在
        if not os.path.exists(test_path):
            return {
                'ok': False,
                'error': f'测试路径不存在：{test_path}'
            }
        
        # 构建 pytest 命令
        cmd = ['pytest']
        
        if verbose:
            cmd.append('-v')
        
        if stop_on_failure:
            cmd.append('-x')
        
        # 添加覆盖率选项
        if coverage:
            cmd.extend(['--cov', os.path.dirname(test_path) or '.'])
            cmd.extend(['--cov-report', 'term-missing'])
            cmd.extend(['--cov-report', 'json'])
        
        # 添加 JSON 输出
        json_report_file = os.path.join(tempfile.gettempdir(), 'pytest_report.json')
        cmd.extend(['--json-report', '--json-report-file', json_report_file])
        cmd.append(test_path)
        
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 分钟超时
        )
        
        # 解析结果
        test_output = result.stdout + result.stderr
        
        # 尝试读取 JSON 报告
        coverage_data = None
        test_details = []
        
        if os.path.exists(json_report_file):
            try:
                with open(json_report_file, 'r', encoding='utf-8') as f:
                    json_report = json.load(f)
                    test_details = json_report.get('tests', [])
            except:
                pass
        
        # 尝试读取覆盖率 JSON
        cov_json_path = 'coverage.json'
        if os.path.exists(cov_json_path):
            try:
                with open(cov_json_path, 'r', encoding='utf-8') as f:
                    coverage_data = json.load(f)
            except:
                pass
        
        # 统计结果
        passed = test_output.count(' PASSED')
        failed = test_output.count(' FAILED')
        skipped = test_output.count(' SKIPPED')
        errors = test_output.count(' ERROR')
        
        # 提取失败详情
        failures = []
        if failed > 0:
            # 简单的失败提取逻辑
            lines = test_output.split('\n')
            current_failure = None
            for line in lines:
                if 'FAILED' in line and '::' in line:
                    if current_failure:
                        failures.append(current_failure)
                    current_failure = {'test': line.strip(), 'details': []}
                elif current_failure and line.strip() and not line.startswith('='):
                    current_failure['details'].append(line)
            if current_failure:
                failures.append(current_failure)
        
        # 提取覆盖率
        coverage_percent = None
        if coverage_data and 'totals' in coverage_data:
            coverage_percent = coverage_data['totals'].get('percent_covered', 0)
        
        return {
            'ok': result.returncode == 0,
            'returncode': result.returncode,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'errors': errors,
            'total': passed + failed + skipped + errors,
            'coverage_percent': coverage_percent,
            'output': test_output,
            'failures': failures,
            'test_details': test_details,
            'coverage_data': coverage_data,
            'summary': f'通过：{passed}, 失败：{failed}, 跳过：{skipped}, 错误：{errors}' + 
                      (f', 覆盖率：{coverage_percent:.1f}%' if coverage_percent else '')
        }
    
    except subprocess.TimeoutExpired:
        return {
            'ok': False,
            'error': '测试执行超时（>5 分钟）',
            'summary': '测试执行超时'
        }
    
    except FileNotFoundError:
        return {
            'ok': False,
            'error': '未找到 pytest 命令，请先安装：pip install pytest pytest-cov pytest-json-report',
            'solution': 'pip install pytest pytest-cov pytest-json-report'
        }
    
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
            'traceback': __import__('traceback').format_exc()
        }


if __name__ == '__main__':
    # 测试示例
    import sys
    if len(sys.argv) > 1:
        result = run_pytest(sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))