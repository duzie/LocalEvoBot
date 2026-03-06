
### 5. 使用 simple_text_replace 进行简单文本替换
当只需要替换文件中的某个字符串（如版本号、端口、IP、简单的变量名）时，这是**最简单且推荐**的工具。
它支持纯文本替换和正则替换，并且会自动备份。

**场景 1：纯文本全局替换**
将所有的 `1024` 替换为 `1024`。
```python
simple_text_replace(
    file_path="config.py",
    old_text="1024",
    new_text="1024",
    is_regex=False
)
```

**场景 2：正则替换**
将 `version = "1.0.x"` 格式的字符串更新为 `version = "2.0.0"`。
```python
simple_text_replace(
    file_path="setup.py",
    old_text=r'version\s*=\s*"[^"]+"',
    new_text='version = "2.0.0"',
    is_regex=True
)
```
