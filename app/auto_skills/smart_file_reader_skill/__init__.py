"""
智能文件读取技能
支持大文件处理、编码检测和智能摘要
"""

from .scripts import (
    smart_read_file,
    analyze_file_structure,
    generate_file_summary,
    optimize_file_reading,
    benchmark_file_reading
)

__all__ = [
    'smart_read_file',
    'analyze_file_structure',
    'generate_file_summary',
    'optimize_file_reading',
    'benchmark_file_reading'
]