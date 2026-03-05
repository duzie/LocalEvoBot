from langchain_core.tools import tool
import os
import json
import ast
import re
from typing import List, Dict, Any, Tuple

# --- Constants & Configuration ---
def _get_base_dir():
    # Adjust based on file location: app/skills/deep_analysis_skill/scripts/deep_analysis_tools.py
    # Up 4 levels to reach root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

def _get_data_dir():
    base_dir = _get_base_dir()
    data_dir = os.path.join(base_dir, "app", "data", "deep_analysis")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def _get_index_path(index_id: str = "default") -> str:
    data_dir = _get_data_dir()
    safe_id = "".join([c if c.isalnum() else "_" for c in index_id])
    return os.path.join(data_dir, f"{safe_id}.json")

# --- Helper Functions ---
def _extract_symbols_from_file(file_path: str) -> Dict[str, List[str]]:
    """Extract key symbols (classes, functions, variables) from a file."""
    symbols = {"classes": [], "functions": [], "variables": []}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.py':
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        symbols["classes"].append(node.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols["functions"].append(node.name)
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                if target.id.isupper():
                                    symbols["variables"].append(target.id)
            except Exception:
                pass
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            symbols["classes"].extend(re.findall(r'class\s+(\w+)', content))
            symbols["functions"].extend(re.findall(r'function\s+(\w+)', content))
            symbols["functions"].extend(re.findall(r'const\s+(\w+)\s*=\s*\(', content))
            symbols["variables"].extend(re.findall(r'export\s+const\s+(\w+)', content))
        elif ext == '.cs':
            symbols["classes"].extend(re.findall(r'class\s+(\w+)', content))
            symbols["functions"].extend(re.findall(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:[\w\.<>\[\]]+\s+)?(\w+)\s*\(', content))

    except Exception:
        pass
        
    return {k: sorted(list(set(v)))[:20] for k, v in symbols.items()}

def _build_skeleton(root_path: str, max_depth: int = 5, include_hidden: bool = False):
    root_path = os.path.abspath(root_path)
    entries: List[Dict[str, Any]] = []
    
    for current, dirs, files in os.walk(root_path):
        rel_dir = os.path.relpath(current, root_path)
        if rel_dir == ".":
            rel_dir = ""
            
        depth = 0 if not rel_dir else rel_dir.count(os.sep) + 1
        if depth > max_depth:
            dirs[:] = []
            continue
            
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]
            
        for f in files:
            file_path = os.path.join(current, f)
            rel_path = os.path.join(rel_dir, f).replace("\\", "/")
            
            entry = {
                "path": rel_path,
                "type": "file",
                "size": os.path.getsize(file_path),
            }
            
            # Extract symbols for code files
            if f.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.cs', '.java', '.go', '.rs')):
                symbols = _extract_symbols_from_file(file_path)
                if any(symbols.values()):
                    entry["symbols"] = symbols
            
            entries.append(entry)
            
    return entries

def _extract_query_terms(query: str) -> List[str]:
    text = str(query or "").strip()
    if not text:
        return []
    terms = set()
    for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", text):
        terms.add(t.lower())
    for t in re.findall(r"[0-9]+", text):
        terms.add(t)
    for t in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        terms.add(t)
    return sorted(terms, key=len, reverse=True)[:48]

def _score_text_hits(text: str, terms: List[str]) -> int:
    if not text or not terms:
        return 0
    score = 0
    lower = text.lower()
    for term in terms:
        if not term:
            continue
        term_lower = term.lower()
        hit = lower.count(term_lower)
        if hit:
            score += min(20, hit) * max(1, min(8, len(term_lower)))
    return score

def _chunk_by_lines(content: str, target_chars: int = 1600, overlap_lines: int = 10) -> List[Tuple[int, int, str]]:
    lines = str(content or "").splitlines()
    if not lines:
        return []
    chunks: List[Tuple[int, int, str]] = []
    i = 0
    total = len(lines)
    while i < total:
        acc = 0
        j = i
        while j < total:
            next_len = len(lines[j]) + 1
            if acc + next_len > target_chars and j > i:
                break
            acc += next_len
            j += 1
            if acc >= target_chars:
                break
        start = i + 1
        end = j
        chunk_text = "\n".join(lines[i:j])
        chunks.append((start, end, chunk_text))
        if j >= total:
            break
        i = max(i + 1, j - max(0, overlap_lines))
    return chunks

def _load_index_files(index_id: str) -> Dict[str, str]:
    index_path = _get_index_path(index_id)
    if not os.path.exists(index_path):
        return {}
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            current_index = json.load(f)
    except Exception:
        return {}
    files_map: Dict[str, str] = {}
    if isinstance(current_index, dict) and isinstance(current_index.get("files"), dict):
        for p, item in current_index.get("files", {}).items():
            if isinstance(item, str):
                files_map[p] = item
            elif isinstance(item, dict):
                files_map[p] = str(item.get("content") or "")
    elif isinstance(current_index, dict):
        for p, item in current_index.items():
            if isinstance(item, str):
                files_map[p] = item
            elif isinstance(item, dict):
                files_map[p] = str(item.get("content") or "")
    return files_map

def _path_to_module(root_path: str, file_path: str) -> str:
    try:
        rel = os.path.relpath(file_path, root_path)
    except Exception:
        rel = str(file_path)
    rel = rel.replace("\\", "/")
    if rel.endswith("/__init__.py"):
        rel = rel[:-len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    rel = rel.strip(".")
    return rel.replace("/", ".").strip(".")

def _build_module_map(files_map: Dict[str, str]) -> Dict[str, str]:
    if not files_map:
        return {}
    paths = [p for p in files_map.keys() if isinstance(p, str)]
    root = os.path.commonpath(paths) if paths else ""
    module_map: Dict[str, str] = {}
    for p in paths:
        if p.endswith(".py"):
            module_name = _path_to_module(root, p)
            if module_name:
                module_map[module_name] = p
        base = os.path.splitext(os.path.basename(p))[0]
        if base:
            module_map.setdefault(base, p)
    return module_map

def _extract_py_symbols(content: str) -> Tuple[List[str], List[str], List[str]]:
    classes: List[str] = []
    functions: List[str] = []
    imports: List[str] = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name:
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception:
        return [], [], []
    return sorted(set(classes)), sorted(set(functions)), sorted(set(imports))

def _extract_js_symbols(content: str) -> Tuple[List[str], List[str], List[str]]:
    classes = re.findall(r'class\s+(\w+)', content)
    functions = re.findall(r'function\s+(\w+)', content)
    functions += re.findall(r'const\s+(\w+)\s*=\s*\(', content)
    imports = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
    imports += re.findall(r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
    return sorted(set(classes)), sorted(set(functions)), sorted(set(imports))

# --- Tools ---

@tool
def get_project_skeleton_analysis(
    root_path: str = ".",
    force_rebuild: bool = False,
    max_depth: int = 3,
    max_entries: int = 500,
    include_hidden: bool = False,
    include_symbols: bool = True,
    extensions: List[str] = None,
    max_lines: int = 200
) -> str:
    """
    扫描项目结构以返回目录树和文件签名（类/函数）。
    在读取具体文件之前，使用此工具定位相关文件。
    返回包含符号的文件列表 JSON 字符串。
    
    Args:
        root_path: 项目根目录路径。默认为当前目录。
        force_rebuild: 是否强制重建缓存。
        max_depth: 最大扫描深度。
        max_entries: 最大条目数。
        include_hidden: 是否包含隐藏文件/目录。
        include_symbols: 是否输出符号摘要。
        extensions: 仅输出指定扩展名的文件（例如 [".py", ".ts"]）。
        max_lines: 最多输出行数，避免上下文过大。
    """
    try:
        from app.skills.project_skeleton_skill.scripts.get_project_skeleton import get_project_skeleton
        if root_path == ".":
            root_path = os.getcwd()
        payload = get_project_skeleton.invoke({
            "root_path": root_path,
            "force_rebuild": force_rebuild,
            "max_depth": max_depth,
            "max_entries": max_entries,
            "include_hidden": include_hidden
        })
        if not isinstance(payload, dict) or not payload.get("ok"):
            err = payload.get("error") if isinstance(payload, dict) else None
            return f"扫描项目骨架时出错: {err or 'unknown'}"
        entries = payload.get("entries") or []
        allowed_ext = None
        if extensions:
            allowed_ext = {str(x).lower() for x in extensions if x}
        summary = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or ""
            if not path:
                continue
            if allowed_ext:
                ext = os.path.splitext(path)[1].lower()
                if ext not in allowed_ext:
                    continue
            line = f"- {path}"
            size = item.get("size")
            if size is not None:
                line += f" ({size} bytes)"
            if include_symbols and isinstance(item.get("symbols"), dict):
                syms = item.get("symbols") or {}
                parts = []
                if syms.get("classes"):
                    parts.append(f"Classes: {', '.join(syms['classes'])}")
                if syms.get("functions"):
                    parts.append(f"Funcs: {', '.join(syms['functions'])}")
                if syms.get("variables"):
                    parts.append(f"Vars: {', '.join(syms['variables'])}")
                if parts:
                    line += f" [{'; '.join(parts)}]"
            summary.append(line)
            if max_lines and len(summary) >= int(max_lines):
                break
        if not summary:
            return "未找到符合条件的文件条目。"
        return "\n".join(summary)
    except Exception as e:
        return f"扫描项目骨架时出错: {str(e)}"

@tool
def read_files_to_analysis_index(file_paths: List[str], index_id: str = "default") -> str:
    """
    读取指定文件并将其内容存入临时分析索引（旁路记忆）。
    返回结构化摘要（Imports, Classes, Functions）到 ChatHistory，但将完整内容隐藏在索引中。
    
    Args:
        file_paths: 要读取的文件路径列表（绝对路径或相对于 CWD）。
        index_id: 分析会话的可选 ID。默认为 "default"。
        
    Returns:
        读取内容的结构化摘要。
    """
    try:
        index_path = _get_index_path(index_id)
        
        # Load existing index
        current_index = {}
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                current_index = json.load(f)
        
        read_count = 0
        total_chars = 0
        failed_files = []
        summaries = []
        
        for path in file_paths:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                failed_files.append(f"{path} (未找到)")
                continue
            
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    current_index[abs_path] = content
                    read_count += 1
                    total_chars += len(content)
                    
                    # Generate structural summary
                    file_summary = f"文件: {path} ({len(content)} 字符)\n"
                    
                    # Extract imports (Python only for now)
                    if path.endswith(".py"):
                        imports = re.findall(r'^(?:from|import)\s+[\w\.]+', content, re.MULTILINE)
                        if imports:
                            # Limit imports to avoid noise
                            unique_imports = sorted(list(set(imports)))[:10]
                            file_summary += f"  导入: {', '.join(unique_imports)}\n"
                            
                    # Reuse symbol extraction
                    symbols = _extract_symbols_from_file(abs_path)
                    if symbols["classes"]:
                        file_summary += f"  类: {', '.join(symbols['classes'])}\n"
                    if symbols["functions"]:
                        file_summary += f"  函数: {', '.join(symbols['functions'])}\n"
                    
                    summaries.append(file_summary)
                    
            except Exception as e:
                failed_files.append(f"{path} (错误: {str(e)})")
        
        # Save updated index
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(current_index, f, ensure_ascii=False, indent=2)
            
        result = f"成功将 {read_count} 个文件读入分析索引 '{index_id}'。\n"
        if summaries:
            result += "--- 结构化摘要 (完整内容已隐藏在索引中) ---\n"
            result += "\n".join(summaries)
        
        if failed_files:
            result += f"\n读取失败: {', '.join(failed_files)}"
            
        return result
    except Exception as e:
        return f"读取文件到索引时出错: {str(e)}"

@tool
def get_analysis_index_status(index_id: str = "default") -> str:
    """
    返回分析索引的当前状态，包括已索引的文件列表和总大小。
    使用此工具检查当前有哪些文件可用于分析。
    
    Args:
        index_id: 分析会话的可选 ID。默认为 "default"。
    """
    try:
        index_path = _get_index_path(index_id)
        if not os.path.exists(index_path):
            return f"分析索引 '{index_id}' 为空。"
            
        with open(index_path, 'r', encoding='utf-8') as f:
            current_index = json.load(f)
            
        if not current_index:
            return f"分析索引 '{index_id}' 为空。"
            
        files = sorted(current_index.keys())
        total_chars = sum(len(content) for content in current_index.values())
        
        summary = [f"分析索引 '{index_id}' 状态:"]
        summary.append(f"- 文件总数: {len(files)}")
        summary.append(f"- 字符总数: {total_chars}")
        summary.append("- 已索引文件:")
        for path in files:
            size = len(current_index[path])
            summary.append(f"  - {path} ({size} 字符)")
            
        return "\n".join(summary)
    except Exception as e:
        return f"获取分析索引状态时出错: {str(e)}"

@tool
def query_analysis_index(
    query: str,
    index_id: str = "default",
    top_k_files: int = 8,
    top_k_chunks: int = 20,
    max_context_chars: int = 22000
) -> str:
    """
    针对分析索引提出具体问题。
    系统将使用存储的文件内容来回答问题。
    这返回聚合后的结论。
    
    Args:
        query: 关于已索引文件的问题。
        index_id: 分析会话的可选 ID。默认为 "default"。
        
    Returns:
        源自已索引文件的答案。
    """
    try:
        from app.agent import create_llm
        from langchain_core.prompts import ChatPromptTemplate
        
        index_path = _get_index_path(index_id)
        if not os.path.exists(index_path):
            return "分析索引为空。请先读取文件到索引中。"
            
        with open(index_path, 'r', encoding='utf-8') as f:
            current_index = json.load(f)
            
        if not current_index:
            return "分析索引为空。"

        files_map = {}
        if isinstance(current_index, dict) and isinstance(current_index.get("files"), dict):
            for p, item in current_index.get("files", {}).items():
                if isinstance(item, str):
                    files_map[p] = item
                elif isinstance(item, dict):
                    files_map[p] = str(item.get("content") or "")
        elif isinstance(current_index, dict):
            for p, item in current_index.items():
                if isinstance(item, str):
                    files_map[p] = item
                elif isinstance(item, dict):
                    files_map[p] = str(item.get("content") or "")

        if not files_map:
            return "分析索引为空。"

        safe_top_files = max(1, min(int(top_k_files or 8), 20))
        safe_top_chunks = max(1, min(int(top_k_chunks or 20), 60))
        safe_max_context_chars = max(4000, min(int(max_context_chars or 22000), 50000))
        terms = _extract_query_terms(query)

        file_rank = []
        for path, content in files_map.items():
            p_text = str(path or "")
            c_text = str(content or "")
            head = c_text[:12000]
            score = _score_text_hits(p_text, terms) * 4 + _score_text_hits(head, terms)
            if not terms:
                score = max(1, len(head) // 2000)
            file_rank.append((score, p_text, c_text))
        file_rank.sort(key=lambda x: x[0], reverse=True)

        selected_files = [(p, c) for s, p, c in file_rank if s > 0][:safe_top_files]
        if not selected_files:
            selected_files = [(p, c) for _, p, c in file_rank[:safe_top_files]]

        chunk_candidates = []
        for path, content in selected_files:
            chunks = _chunk_by_lines(content, target_chars=1600, overlap_lines=10)
            if not chunks:
                continue
            local = []
            for start, end, chunk_text in chunks:
                score = _score_text_hits(chunk_text, terms)
                if terms:
                    score += _score_text_hits(path, terms) * 2
                local.append((score, path, start, end, chunk_text))
            local.sort(key=lambda x: x[0], reverse=True)
            kept = [item for item in local if item[0] > 0][:max(1, safe_top_chunks // max(1, len(selected_files)))]
            if not kept:
                kept = local[:1]
            chunk_candidates.extend(kept)

        chunk_candidates.sort(key=lambda x: x[0], reverse=True)
        selected_chunks = chunk_candidates[:safe_top_chunks]
        if not selected_chunks:
            return "分析索引中没有可用内容。"

        context_parts = []
        used = 0
        for _, path, start, end, chunk_text in selected_chunks:
            block = f"--- 文件: {path} | 行: {start}-{end} ---\n{chunk_text}\n"
            if used + len(block) > safe_max_context_chars:
                break
            context_parts.append(block)
            used += len(block)
        context_str = "\n".join(context_parts)
        if not context_str.strip():
            return "上下文预算不足，请减小 top_k_chunks 或提高 max_context_chars。"
            
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "你是一个代码关联分析助手。必须严格基于给定片段回答，先给跨文件关系，再给证据（文件+行号），证据不足要明确说明。"),
            ("user", "上下文片段:\n{context}\n\n问题: {query}\n\n输出要求：\n1) 关键文件与职责\n2) 关联关系/调用链\n3) 证据清单（文件+行号）\n4) 未确认点")
        ])
        
        llm = create_llm()
        prompt_value = prompt_template.invoke({"context": context_str, "query": query})
        messages = prompt_value.to_messages() if hasattr(prompt_value, "to_messages") else prompt_template.format_messages(context=context_str, query=query)
        response = llm.invoke(messages)
        
        return (
            f"已选取 {len(selected_files)} 个文件、{len(context_parts)} 个片段进入分析（上下文约 {used} 字符）。\n"
            + str(response.content)
        )
        
    except Exception as e:
        return f"Error querying analysis index: {str(e)}"

@tool
def build_project_logic_graph(
    index_id: str = "default",
    focus_paths: List[str] = None,
    max_files: int = 30,
    max_nodes: int = 200,
    max_edges: int = 400
) -> str:
    """
    基于分析索引构建项目逻辑图（文件/符号/导入关系的紧凑图）。
    """
    try:
        files_map = _load_index_files(index_id)
        if not files_map:
            return "分析索引为空。请先读取文件到索引中。"
        focus = [str(p).replace("\\", "/").lower() for p in (focus_paths or []) if p]
        items = []
        for path, content in files_map.items():
            p_norm = str(path).replace("\\", "/")
            if focus:
                if not any(f in p_norm.lower() or os.path.basename(p_norm).lower() == f for f in focus):
                    continue
            items.append((p_norm, content))
        if not items:
            items = [(str(p), c) for p, c in files_map.items()]
        items.sort(key=lambda x: len(x[1] or ""), reverse=True)
        safe_max_files = max(1, min(int(max_files or 30), 120))
        items = items[:safe_max_files]

        module_map = _build_module_map({p: c for p, c in items})
        nodes: Dict[str, Dict[str, str]] = {}
        edges: Dict[str, Dict[str, str]] = {}

        def add_node(node_id: str, node_type: str, label: str, path: str = ""):
            if node_id in nodes:
                return
            if len(nodes) >= max(10, int(max_nodes or 200)):
                return
            payload = {"id": node_id, "type": node_type, "label": label}
            if path:
                payload["path"] = path
            nodes[node_id] = payload

        def add_edge(source: str, target: str, edge_type: str):
            if len(edges) >= max(20, int(max_edges or 400)):
                return
            key = f"{source}::{edge_type}::{target}"
            if key in edges:
                return
            edges[key] = {"source": source, "target": target, "type": edge_type}

        for path, content in items:
            file_id = f"file:{path}"
            add_node(file_id, "file", os.path.basename(path), path)
            ext = os.path.splitext(path)[1].lower()
            classes: List[str] = []
            functions: List[str] = []
            imports: List[str] = []
            if ext == ".py":
                classes, functions, imports = _extract_py_symbols(content)
            elif ext in {".js", ".ts", ".jsx", ".tsx"}:
                classes, functions, imports = _extract_js_symbols(content)
            for name in classes:
                sym_id = f"symbol:{path}:{name}"
                add_node(sym_id, "class", name, path)
                add_edge(file_id, sym_id, "defines")
            for name in functions:
                sym_id = f"symbol:{path}:{name}"
                add_node(sym_id, "function", name, path)
                add_edge(file_id, sym_id, "defines")
            for imp in imports:
                target_path = module_map.get(imp)
                if target_path:
                    target_id = f"file:{target_path}"
                    add_node(target_id, "file", os.path.basename(target_path), target_path)
                    add_edge(file_id, target_id, "imports")
                else:
                    mod_id = f"module:{imp}"
                    add_node(mod_id, "module", imp)
                    add_edge(file_id, mod_id, "imports")

        result = {
            "index_id": index_id,
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "stats": {
                "file_count": len(items),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "truncated": len(nodes) >= int(max_nodes or 200) or len(edges) >= int(max_edges or 400)
            }
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"生成项目逻辑图失败: {str(e)}"

@tool
def clear_analysis_index(index_id: str = "default") -> str:
    """
    Clears the current Analysis Index to free up resources or start a fresh analysis.
    
    Args:
        index_id: Optional ID for the analysis session. Defaults to "default".
    """
    try:
        index_path = _get_index_path(index_id)
        if os.path.exists(index_path):
            os.remove(index_path)
            return f"Analysis Index '{index_id}' cleared."
        return f"Analysis Index '{index_id}' was already empty."
    except Exception as e:
        return f"Error clearing analysis index: {str(e)}"
