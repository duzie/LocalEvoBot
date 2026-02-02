from langchain_core.tools import tool
import os
import concurrent.futures
from pathlib import Path
from .download_image import download_image

@tool
def download_multiple_images(urls, save_dir=None, prefix="image", concurrent=False):
    """
    批量下载多个图片
    
    Args:
        urls: 图片URL列表
        save_dir: 保存目录，如果为None则保存到临时目录
        prefix: 文件名前缀
        concurrent: 是否并发下载
    
    Returns:
        包含批量下载结果的字典
    """
    try:
        if not urls:
            return {
                "success": False,
                "message": "URL列表为空",
                "results": []
            }
        
        # 创建保存目录
        if save_dir is None:
            save_dir = Path(os.environ.get('TEMP', '.')) / "downloaded_images"
        else:
            save_dir = Path(save_dir)
        
        save_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        successful_downloads = []
        failed_downloads = []
        
        def download_single(url, index):
            """下载单个图片"""
            # 生成文件名
            filename = f"{prefix}_{index:03d}"
            save_path = str(save_dir / filename)
            
            # 下载图片
            result = download_image(url, save_path=save_path)
            
            # 添加索引信息
            result["index"] = index
            result["url"] = url
            
            return result
        
        if concurrent:
            # 并发下载
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(download_single, url, i): (url, i) 
                               for i, url in enumerate(urls)}
                
                for future in concurrent.futures.as_completed(future_to_url):
                    url, index = future_to_url[future]
                    try:
                        result = future.result()
                        results.append(result)
                        if result.get("success"):
                            successful_downloads.append(result["file_path"])
                        else:
                            failed_downloads.append(url)
                    except Exception as e:
                        error_result = {
                            "success": False,
                            "message": f"并发下载异常，URL: {url}",
                            "error": str(e),
                            "url": url,
                            "index": index
                        }
                        results.append(error_result)
                        failed_downloads.append(url)
        else:
            # 顺序下载
            for i, url in enumerate(urls):
                result = download_single(url, i)
                results.append(result)
                if result.get("success"):
                    successful_downloads.append(result["file_path"])
                else:
                    failed_downloads.append(url)
        
        # 统计结果
        total = len(urls)
        success_count = len(successful_downloads)
        fail_count = len(failed_downloads)
        
        return {
            "success": success_count > 0,
            "message": f"批量下载完成，成功{success_count}个，失败{fail_count}个，总计{total}个",
            "total": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "save_dir": str(save_dir),
            "successful_files": successful_downloads,
            "failed_urls": failed_downloads,
            "results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"批量下载过程中发生异常",
            "error": str(e),
            "results": []
        }