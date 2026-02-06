# Usage

## Scope
文档读取和搜索技能，用于读取文档部分内容、搜索关键词、截取文档片段、获取文档统计信息，以及在指定行插入内容（解决长文档/代码截断问题）。
当文档内容过大无法一次性读取，或者只需要关注文档的特定部分时，应优先使用此技能。

## Tools

### 1. read_document_part
读取文档的部分内容，支持按行数范围截取。

- **Args**:
    - `file_path` (str): 文档文件路径。
    - `start_line` (int): 起始行号（从0开始，默认0）。
    - `end_line` (int, optional): 结束行号（包含），如果为None则读取到文件末尾。
    - `max_chars` (int): 最大字符数限制（默认5000），超过会被截断。
    - `encoding` (str): 文件编码（默认"utf-8"）。

- **Returns**: 包含文档内容(`content`)和统计信息(`stats`)的字典。

### 2. search_document
在文档中搜索关键词，返回包含关键词的行及其上下文。

- **Args**:
    - `file_path` (str): 文档文件路径。
    - `keyword` (str): 搜索关键词。
    - `context_lines` (int): 返回关键词前后多少行上下文（默认3）。
    - `case_sensitive` (bool): 是否区分大小写（默认False）。
    - `max_results` (int): 最大返回结果数（默认10）。
    - `encoding` (str): 文件编码（默认"utf-8"）。

- **Returns**: 包含搜索结果列表(`results`)和统计信息(`stats`)的字典。

### 3. extract_document_section
提取文档中特定章节或标记的内容（例如 Markdown 的标题章节）。

- **Args**:
    - `file_path` (str): 文档文件路径。
    - `section_marker` (str): 章节标记（如 "## 功能说明"）。
    - `include_marker` (bool): 是否包含标记行本身（默认True）。
    - `next_section_marker` (str, optional): 下一章节标记，用于确定提取范围。如果不提供，默认提取到文件末尾。
    - `encoding` (str): 文件编码（默认"utf-8"）。

- **Returns**: 包含提取内容(`content`)的字典。

### 4. get_document_stats
获取文档统计信息（行数、字符数、大小、代码块数量等）。

- **Args**:
    - `file_path` (str): 文档文件路径。
    - `encoding` (str): 文件编码（默认"utf-8"）。

- **Returns**: 包含文档统计信息的字典。

### 5. insert_text_at_line
按行号向文本文件插入内容。主要用于解决生成的代码或文本过长被截断的问题，可以通过多次调用此工具分段写入。

- **Args**:
    - `file_path` (str): 文件路径。
    - `line_number` (int): 目标行号（从 1 开始）。允许等于 total_lines+1 表示追加到末尾。
    - `text` (str): 要插入的文本（支持多行）。
    - `position` (str): 插入位置，"before"（默认）表示插入到该行前，"after" 表示插入到该行后。
    - `encoding` (str): 文件编码（默认"utf-8"）。

- **Returns**: 包含插入结果与新行数的字典。

## Examples

### 场景1：处理长代码文件
当需要读取一个非常长的代码文件时，不要直接读取全文。
1. 先获取文件统计信息：
   ```python
   get_document_stats(file_path="large_file.py")
   ```
2. 根据行数分段读取（例如读取前100行）：
   ```python
   read_document_part(file_path="large_file.py", start_line=0, end_line=99)
   ```
3. 或者搜索感兴趣的函数定义：
   ```python
   search_document(file_path="large_file.py", keyword="def process_data")
   ```

### 场景2：提取Markdown文档特定章节
当只需要查看 README.md 中的 "Usage" 章节时：
```python
extract_document_section(
    file_path="README.md",
    section_marker="## Usage",
    next_section_marker="## Configuration"
)
```

### 场景3：解决长代码写入截断问题
当 Agent 生成的代码太长（例如超过 200 行），可能会在输出时被截断。可以使用 `insert_text_at_line` 分段写入。

假设 `app.py` 原有 50 行，需要在最后追加一段长代码：
1. 先写入第一部分（例如追加到末尾）：
   ```python
   insert_text_at_line(
       file_path="app.py",
       line_number=51, # 假设原文件50行，51表示追加
       text="...第一部分代码...",
       position="before"
   )
   ```
2. 写入第二部分（根据第一部分插入后的行数计算新位置，或者继续追加）：
   ```python
   # 假设第一部分插入了 100 行，现在文件共 150 行
   insert_text_at_line(
       file_path="app.py",
       line_number=151,
       text="...第二部分代码...",
       position="before"
   )
   ```
或者，如果是在文件中间（例如第 10 行）插入一大段代码：
```python
insert_text_at_line(
    file_path="app.py",
    line_number=10,
    text="...要插入的长代码...",
    position="before"
)
```
