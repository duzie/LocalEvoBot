from pathlib import Path
from typing import Dict, List, Any
import time
import psutil
import os
from langchain_core.tools import tool

def _generate_performance_report(results: Dict, analysis: Dict, file_size: int) -> Dict:
    """生成性能报告"""
    report = {
        "executive_summary": "",
        "key_findings": [],
        "performance_metrics": {},
        "comparison_table": []
    }
    
    # 执行摘要
    best_method = analysis.get("best_method", {})
    improvement = analysis.get("improvement_over_baseline", 0)
    
    if best_method:
        report["executive_summary"] = (
            f"基准测试完成。最佳方法是 '{best_method.get('description', 'unknown')}'，"
            f"相比基线方法综合性能提升 {improvement}%。"
        )
    else:
        report["executive_summary"] = "基准测试完成，但未能确定最佳方法。"
    
    # 关键发现
    fastest = analysis.get("fastest_method", {})
    most_mem_efficient = analysis.get("most_memory_efficient", {})
    
    if fastest:
        report["key_findings"].append(
            f"最快方法: {fastest.get('description', 'unknown')} "
            f"({fastest.get('time_mean', 0):.4f} 秒)"
        )
    
    if most_mem_efficient:
        report["key_findings"].append(
            f"最省内存方法: {most_mem_efficient.get('description', 'unknown')} "
            f"({most_mem_efficient.get('memory_mean', 0):.2f} MB)"
        )
    
    # 性能指标
    report["performance_metrics"] = {
        "file_size_mb": file_size / (1024 * 1024),
        "total_methods_tested": len(results),
        "overall_improvement": improvement
    }
    
    # 比较表
    for method_name, method_results in results.items():
        report["comparison_table"].append({
            "method": method_name,
            "description": method_results.get("description", ""),
            "time_mean": method_results.get("time_mean", 0),
            "time_std": method_results.get("time_std", 0),
            "memory_mean": method_results.get("memory_mean", 0),
            "memory_std": method_results.get("memory_std", 0),
            "score": method_results.get("score", 0)
        })
    
    return report

def _analyze_benchmark_results(results: Dict) -> Dict:
    """分析基准测试结果"""
    analysis = {
        "fastest_method": {},
        "most_memory_efficient": {},
        "best_method": {},
        "improvement_over_baseline": 0
    }
    
    if not results:
        return analysis
    
    # 找到最快的方法
    fastest_time = float('inf')
    fastest_method = None
    
    # 找到最省内存的方法
    lowest_memory = float('inf')
    most_mem_method = None
    
    # 找到综合评分最高的方法
    highest_score = -float('inf')
    best_method = None
    
    for method_name, method_data in results.items():
        time_mean = method_data.get("time_mean", float('inf'))
        memory_mean = method_data.get("memory_mean", float('inf'))
        score = method_data.get("score", -float('inf'))
        
        if time_mean < fastest_time:
            fastest_time = time_mean
            fastest_method = method_name
        
        if memory_mean < lowest_memory:
            lowest_memory = memory_mean
            most_mem_method = method_name
        
        if score > highest_score:
            highest_score = score
            best_method = method_name
    
    if fastest_method:
        analysis["fastest_method"] = {
            "name": fastest_method,
            **results[fastest_method]
        }
    
    if most_mem_method:
        analysis["most_memory_efficient"] = {
            "name": most_mem_method,
            **results[most_mem_method]
        }
    
    if best_method:
        analysis["best_method"] = {
            "name": best_method,
            **results[best_method]
        }
    
    # 计算相对于基线方法的改进
    if "baseline" in results and best_method in results:
        baseline_score = results["baseline"].get("score", 0)
        best_score = results[best_method].get("score", 0)
        
        if baseline_score > 0:
            improvement = ((best_score - baseline_score) / baseline_score) * 100
            analysis["improvement_over_baseline"] = round(improvement, 2)
    
    return analysis

@tool
def benchmark_file_reading(file_path: str, iterations: int = 3) -> Dict:
    """基准测试文件读取方法
    
    Args:
        file_path: 要测试的文件路径
        iterations: 每个方法的测试迭代次数
        
    Returns:
        包含基准测试结果的字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    
    file_size = path.stat().st_size
    
    # 定义要测试的方法
    methods = {
        "baseline": {
            "description": "标准文件读取",
            "function": _baseline_read
        },
        "chunked": {
            "description": "分块读取",
            "function": _chunked_read
        },
        "memory_mapped": {
            "description": "内存映射读取",
            "function": _memory_mapped_read
        },
        "buffered": {
            "description": "缓冲读取",
            "function": _buffered_read
        }
    }
    
    results = {}
    
    for method_name, method_info in methods.items():
        print(f"测试方法: {method_name} ({method_info['description']})")
        
        time_results = []
        memory_results = []
        
        for i in range(iterations):
            # 测量时间
            start_time = time.time()
            
            # 测量内存
            process = psutil.Process(os.getpid())
            start_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            # 执行读取
            try:
                content = method_info["function"](path)
                success = True
            except Exception as e:
                print(f"方法 {method_name} 第 {i+1} 次迭代失败: {e}")
                success = False
                content = ""
            
            end_time = time.time()
            end_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            if success:
                time_results.append(end_time - start_time)
                memory_results.append(end_memory - start_memory)
        
        if time_results:
            # 计算统计信息
            import statistics
            time_mean = statistics.mean(time_results)
            time_std = statistics.stdev(time_results) if len(time_results) > 1 else 0
            
            memory_mean = statistics.mean(memory_results)
            memory_std = statistics.stdev(memory_results) if len(memory_results) > 1 else 0
            
            # 计算综合评分（越低越好）
            # 权重：时间 60%，内存 40%
            time_score = time_mean * 1000  # 转换为毫秒
            memory_score = memory_mean
            
            # 归一化评分
            score = (0.6 * time_score) + (0.4 * memory_score)
            
            results[method_name] = {
                "description": method_info["description"],
                "time_mean": round(time_mean, 4),
                "time_std": round(time_std, 4),
                "memory_mean": round(memory_mean, 2),
                "memory_std": round(memory_std, 2),
                "score": round(score, 2),
                "iterations": iterations,
                "success_rate": len(time_results) / iterations
            }
        else:
            results[method_name] = {
                "description": method_info["description"],
                "error": "所有迭代都失败",
                "success_rate": 0
            }
    
    # 分析结果
    analysis = _analyze_benchmark_results(results)
    
    # 生成报告
    report = _generate_performance_report(results, analysis, file_size)
    
    return {
        "file_info": {
            "path": str(path),
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2)
        },
        "results": results,
        "analysis": analysis,
        "report": report
    }

def _baseline_read(file_path: Path) -> str:
    """标准文件读取方法"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def _chunked_read(file_path: Path, chunk_size: int = 8192) -> str:
    """分块读取方法"""
    content = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            content.append(chunk)
    return ''.join(content)

def _memory_mapped_read(file_path: Path) -> str:
    """内存映射读取方法"""
    import mmap
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        # 对于文本文件，使用普通读取
        return f.read()

def _buffered_read(file_path: Path, buffer_size: int = 8192) -> str:
    """缓冲读取方法"""
    content = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        while True:
            chunk = f.read(buffer_size)
            if not chunk:
                break
            content.append(chunk)
    return ''.join(content)
