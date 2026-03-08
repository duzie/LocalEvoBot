# Git Skill 使用说明

## 功能概述

Git 技能提供了完整的 Git 版本控制操作支持，包括仓库管理、分支操作、代码提交、远程同步等功能。

## 工具列表

### 基础操作
- `git_status`: 查看仓库状态
- `git_diff`: 查看代码变更
- `git_log`: 查看提交历史

### 代码管理
- `git_add`: 添加文件到暂存区
- `git_commit`: 提交代码
- `git_checkout`: 切换分支

### 远程操作
- `git_push`: 推送代码到远程仓库
- `git_pull`: 从远程仓库拉取代码
- `git_clone`: 克隆远程仓库

### 分支管理
- `git_branch`: 分支管理（创建、删除、列表）

### 仓库管理
- `git_init`: 初始化 Git 仓库

## 使用示例

### 查看仓库状态
```python
git_status(repo_path="D:/my_project")
```

### 查看代码变更
```python
git_diff(repo_path="D:/my_project", staged=False)
```

### 提交代码
```python
git_add(repo_path="D:/my_project", all_files=True)
git_commit(repo_path="D:/my_project", message="feat: 添加新功能")
```

### 推送到远程仓库
```python
git_push(repo_path="D:/my_project", remote="origin", branch="main")
```

### 分支操作
```python
git_branch(repo_path="D:/my_project", list_all=True)
git_branch(repo_path="D:/my_project", create="feature-branch")
git_checkout(repo_path="D:/my_project", branch="feature-branch")
```

## 注意事项

1. 所有操作都需要提供有效的仓库路径
2. 远程操作需要配置好远程仓库
3. 某些操作可能需要 Git 凭证认证
4. 建议在执行推送/拉取操作前先查看状态