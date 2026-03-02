from langchain_core.tools import tool
"""
检查测试覆盖率并生成报告。

Args:
    source_dir: 源代码目录
    coverage_file: 覆盖率数据文件路径（默认 .coverage）
    report_format: 报告格式：text/html/json（默认 text）
    min_coverage: 最低覆盖率要求（默认 80）

Returns:
    包含覆盖率报告的字典
"""
import os
import subprocess
import json
from pathlib import Path


@tool
def check_coverage(
    source_dir: str,
    coverage_file: str = '.coverage',
    report_format: str = 'text',
    min_coverage: int = 80
) -> dict:
    """
    检查测试覆盖率并生成报告
    
    Args:
        source_dir: 源代码目录
        coverage_file: 覆盖率数据文件路径
        report_format: 报告格式：text/html/json
        min_coverage: 最低覆盖率要求
    
    Returns:
        包含覆盖率报告的字典
    """
    try:
        # 验证目录存在
        if not os.path.exists(source_dir):
            return {
                'ok': False,
                'error': f'源代码目录不存在：{source_dir}'
            }
        
        # 检查是否已有覆盖率数据
        has_coverage_data = os.path.exists(coverage_file)
        
        if not has_coverage_data:
            # 尝试运行测试生成覆盖率数据
            print(f'未找到覆盖率数据文件，尝试运行测试...')
            test_result = subprocess.run(
                ['pytest', '--cov', source_dir, '--cov-report', 'term-missing', '-q'],
                capture_output=True,
                text=True,
                timeout=300
            )
            if test_result.returncode != 0 and not os.path.exists(coverage_file):
                return {
                    'ok': False,
                    'error': '无法生成覆盖率数据，请先运行测试',
                    'pytest_output': test_result.stdout + test_result.stderr
                }
        
        # 生成指定格式的报告
        report_output = ''
        
        if report_format == 'text':
            result = subprocess.run(
                ['coverage', 'report', '--show-missing'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(coverage_file) or '.'
            )
            report_output = result.stdout
            
            # 提取覆盖率百分比
            lines = report_output.split('\n')
            coverage_percent = None
            for line in lines:
                if 'TOTAL' in line or 'total' in line.lower():
                    parts = line.split()
                    for part in parts:
                        if '%' in part:
                            try:
                                coverage_percent = float(part.replace('%', ''))
                            except:
                                pass
        
        elif report_format == 'html':
            html_dir = 'htmlcov'
            result = subprocess.run(
                ['coverage', 'html', '-d', html_dir],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(coverage_file) or '.'
            )
            report_output = f'HTML 报告已生成：{os.path.abspath(html_dir)}/index.html'
            
            # 同时获取文本摘要
            text_result = subprocess.run(
                ['coverage', 'report'],
                capture_output=True,
                text=True
            )
            lines = text_result.stdout.split('\n')
            coverage_percent = None
            for line in lines:
                if 'TOTAL' in line or 'total' in line.lower():
                    parts = line.split()
                    for part in parts:
                        if '%' in part:
                            try:
                                coverage_percent = float(part.replace('%', ''))
                            except:
                                pass
        
        elif report_format == 'json':
            json_file = 'coverage.json'
            result = subprocess.run(
                ['coverage', 'json', '-o', json_file],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(coverage_file) or '.'
            )
            
            # 读取 JSON 报告
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    coverage_data = json.load(f)
                    report_output = json.dumps(coverage_data, indent=2, ensure_ascii=False)
                    coverage_percent = coverage_data.get('totals', {}).get('percent_covered', 0)
            else:
                return {
                    'ok': False,
                    'error': '无法生成 JSON 覆盖率报告'
                }
        
        else:
            return {
                'ok': False,
                'error': f'不支持的报告格式：{report_format}，支持：text/html/json'
            }
        
        # 检查是否达到最低覆盖率要求
        meets_requirement = coverage_percent is not None and coverage_percent >= min_coverage
        
        return {
            'ok': meets_requirement,
            'coverage_percent': coverage_percent,
            'min_coverage': min_coverage,
            'meets_requirement': meets_requirement,
            'report_format': report_format,
            'report': report_output,
            'summary': f'覆盖率：{coverage_percent:.1f}% (要求：{min_coverage}%) - {"✓ 达标" if meets_requirement else "✗ 未达标"}',
            'recommendations': [] if meets_requirement else [
                '为未覆盖的函数添加测试用例',
                '测试边界情况和异常处理',
                '运行 pytest --cov 查看具体未覆盖的行'
            ]
        }
    
    except subprocess.TimeoutExpired:
        return {
            'ok': False,
            'error': '覆盖率检查超时（>5 分钟）'
        }
    
    except FileNotFoundError as e:
        return {
            'ok': False,
            'error': f'未找到命令：{e.filename}，请先安装 coverage 工具',
            'solution': 'pip install coverage pytest-cov'
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
        result = check_coverage(sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))