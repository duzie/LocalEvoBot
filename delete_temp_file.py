import os

# 删除临时文件
temp_file = "wall_street_news_summary.txt"
if os.path.exists(temp_file):
    os.remove(temp_file)
    print(f"已删除临时文件: {temp_file}")
else:
    print(f"文件不存在: {temp_file}")