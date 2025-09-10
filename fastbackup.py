#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastBackup - 一行导入式实验备份工具
只需要在main函数开头 import fastbackup 即可自动备份
"""

import os
import sys
import shutil
import datetime
import json
import hashlib
import inspect
from pathlib import Path
import atexit


class FastBackup:
    def __init__(self):
        # 自动检测调用脚本的目录作为项目根目录
        caller_frame = inspect.currentframe().f_back
        caller_file = caller_frame.f_globals['__file__']
        self.project_path = Path(caller_file).parent.resolve()

        # 备份目录设置为项目根目录下的 .fastbackup
        self.backup_root = self.project_path / '.fastbackup'
        self.backup_root.mkdir(exist_ok=True)

        # 创建 .gitignore 文件忽略备份目录
        gitignore_path = self.project_path / '.gitignore'
        self._update_gitignore(gitignore_path)

        # 执行备份
        self.backup_dir = self._auto_backup()

        # 注册退出时的清理函数
        atexit.register(self._on_exit)

    def _update_gitignore(self, gitignore_path):
        """更新.gitignore文件，忽略备份目录"""
        gitignore_entry = ".fastbackup/"

        if gitignore_path.exists():
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if gitignore_entry not in content:
                with open(gitignore_path, 'a', encoding='utf-8') as f:
                    if not content.endswith('\n'):
                        f.write('\n')
                    f.write(f"{gitignore_entry}\n")
        else:
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(f"{gitignore_entry}\n")

    def _get_python_files(self):
        """获取项目中所有Python文件"""
        python_files = []
        exclude_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', 'env',
                        '.venv', 'node_modules', '.fastbackup', '.idea', '.vscode'}

        for root, dirs, files in os.walk(self.project_path):
            # 过滤掉不需要的目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    python_files.append(file_path)

        return python_files

    def _calculate_file_hash(self, file_path):
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def _has_changes(self):
        """检查是否有文件变化"""
        latest_backup = self._get_latest_backup()
        if not latest_backup:
            return True

        info_file = latest_backup / "backup_info.json"
        if not info_file.exists():
            return True

        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                last_info = json.load(f)
        except:
            return True

        # 检查当前文件哈希
        current_files = self._get_python_files()
        current_hashes = {}

        for file_path in current_files:
            rel_path = str(file_path.relative_to(self.project_path))
            file_hash = self._calculate_file_hash(file_path)
            if file_hash:
                current_hashes[rel_path] = file_hash

        last_hashes = last_info.get('file_hashes', {})
        return current_hashes != last_hashes

    def _get_latest_backup(self):
        """获取最新的备份目录"""
        backup_dirs = [d for d in self.backup_root.iterdir() if d.is_dir()]
        if not backup_dirs:
            return None
        return max(backup_dirs, key=lambda x: x.name)

    def _auto_backup(self):
        """自动执行备份"""
        # 检查是否需要备份
        if not self._has_changes():
            latest_backup = self._get_latest_backup()
            if latest_backup:
                print(f"🔄 FastBackup: 使用现有备份 {latest_backup.name}")
            return latest_backup

        # 创建新备份
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_dir = self.backup_root / backup_name
        backup_dir.mkdir(exist_ok=True)

        python_files = self._get_python_files()

        if not python_files:
            print("⚠️  FastBackup: 没有找到Python文件")
            return None

        print(f"💾 FastBackup: 创建备份 {backup_name} ({len(python_files)} 个文件)")

        # 备份信息
        backup_info = {
            "timestamp": timestamp,
            "project_path": str(self.project_path),
            "file_count": len(python_files),
            "file_hashes": {},
            "files": []
        }

        # 复制文件
        for file_path in python_files:
            try:
                rel_path = file_path.relative_to(self.project_path)
                target_path = backup_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target_path)

                file_hash = self._calculate_file_hash(file_path)
                file_info = {
                    "path": str(rel_path),
                    "size": file_path.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    "hash": file_hash
                }

                backup_info["files"].append(file_info)
                if file_hash:
                    backup_info["file_hashes"][str(rel_path)] = file_hash

            except Exception as e:
                print(f"⚠️  FastBackup: 备份失败 {file_path}: {e}")

        # 保存备份信息
        with open(backup_dir / "backup_info.json", 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)

        return backup_dir

    def _on_exit(self):
        """程序退出时的处理"""
        if hasattr(self, 'backup_dir') and self.backup_dir:
            # 可以在这里添加一些退出时的处理逻辑
            pass

    @classmethod
    def list_backups(cls, project_path=None):
        """列出所有备份（类方法，可以独立调用）"""
        if project_path is None:
            # 自动检测当前项目路径
            caller_frame = inspect.currentframe().f_back
            caller_file = caller_frame.f_globals['__file__']
            project_path = Path(caller_file).parent.resolve()
        else:
            project_path = Path(project_path).resolve()

        backup_root = project_path / '.fastbackup'

        if not backup_root.exists():
            print("📁 没有找到备份目录")
            return

        backup_dirs = sorted([d for d in backup_root.iterdir() if d.is_dir()],
                             key=lambda x: x.name, reverse=True)

        if not backup_dirs:
            print("📁 没有找到任何备份")
            return

        print(f"📋 FastBackup 历史记录 ({len(backup_dirs)} 个备份):")
        print("-" * 60)

        for i, backup_dir in enumerate(backup_dirs[:10]):  # 只显示最近10个
            info_file = backup_dir / "backup_info.json"

            if info_file.exists():
                try:
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)

                    timestamp = info.get('timestamp', '')
                    file_count = info.get('file_count', 0)

                    # 格式化时间显示
                    try:
                        dt = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = timestamp

                    print(f"{i + 1:2d}. {time_str} | {file_count} 文件 | {backup_dir.name}")

                except Exception:
                    print(f"{i + 1:2d}. {backup_dir.name} (信息读取失败)")
            else:
                print(f"{i + 1:2d}. {backup_dir.name} (无信息文件)")

        if len(backup_dirs) > 10:
            print(f"... 还有 {len(backup_dirs) - 10} 个更早的备份")

    @classmethod
    def restore_backup(cls, backup_name, project_path=None):
        """恢复指定的备份"""
        if project_path is None:
            caller_frame = inspect.currentframe().f_back
            caller_file = caller_frame.f_globals['__file__']
            project_path = Path(caller_file).parent.resolve()
        else:
            project_path = Path(project_path).resolve()

        backup_root = project_path / '.fastbackup'
        backup_dir = backup_root / backup_name

        if not backup_dir.exists():
            print(f"❌ 备份不存在: {backup_name}")
            return False

        print(f"🔄 恢复备份: {backup_name}")

        # 读取备份信息
        info_file = backup_dir / "backup_info.json"
        if info_file.exists():
            with open(info_file, 'r', encoding='utf-8') as f:
                backup_info = json.load(f)

            restored_count = 0
            for file_info in backup_info.get('files', []):
                src_path = backup_dir / file_info['path']
                dst_path = project_path / file_info['path']

                if src_path.exists():
                    try:
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        restored_count += 1
                        print(f"  ✅ {file_info['path']}")
                    except Exception as e:
                        print(f"  ❌ {file_info['path']}: {e}")

            print(f"✨ 恢复完成! 共恢复 {restored_count} 个文件")
            return True
        else:
            print("❌ 找不到备份信息文件")
            return False


# 全局变量，避免重复初始化
_backup_instance = None


def _ensure_backup():
    """确保备份实例已创建（延迟初始化）"""
    global _backup_instance
    if _backup_instance is None:
        _backup_instance = FastBackup()
    return _backup_instance


# 导出的便捷函数
def backup():
    """手动触发备份"""
    return _ensure_backup()


def list_backups():
    """列出所有备份"""
    FastBackup.list_backups()


def restore(backup_name):
    """恢复指定备份"""
    return FastBackup.restore_backup(backup_name)


# 当模块被导入时自动执行备份
_ensure_backup()

# 如果直接运行此文件，提供命令行功能
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='FastBackup - 快速实验备份工具')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有备份')
    parser.add_argument('--restore', '-r', help='恢复指定备份')
    parser.add_argument('--project', '-p', help='项目路径（默认当前目录）')

    args = parser.parse_args()

    if args.list:
        FastBackup.list_backups(args.project or os.getcwd())
    elif args.restore:
        FastBackup.restore_backup(args.restore, args.project or os.getcwd())
    else:
        print("FastBackup - 一行导入式实验备份工具")
        print("使用方法:")
        print("  在你的Python脚本开头添加: import fastbackup")
        print("  命令行查看备份: python fastbackup.py --list")
        print("  恢复备份: python fastbackup.py --restore backup_20240101_120000")