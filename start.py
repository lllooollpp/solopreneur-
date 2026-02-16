#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Solopreneur 前后端启动脚本
自动 kill 端口占用并启动前后端服务
"""
import os
import sys
import time
import subprocess
import signal
from pathlib import Path
from typing import Optional

# Windows 控制台 UTF-8 设置 (必须在最开始设置)
if sys.platform == "win32":
    # 设置控制台代码页为 UTF-8
    os.system("chcp 65001 > nul 2>&1")
    # 设置 Python 环境变量
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    # 强制重配 stdout/stderr 为 UTF-8 (Python 3.7+)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_HOST = "0.0.0.0"  # 允许所有 IP 访问 (局域网/公网)
FRONTEND_HOST = "0.0.0.0"  # 允许所有 IP 访问 (局域网/公网)

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def log(message: str, color: str = Colors.CYAN):
    """输出彩色日志"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}]{Colors.END} {message}")

def log_info(message: str):
    log(f"[INFO] {message}", Colors.CYAN)

def log_success(message: str):
    log(f"[OK] {message}", Colors.GREEN)

def log_warning(message: str):
    log(f"[WARN] {message}", Colors.YELLOW)

def log_error(message: str):
    log(f"[ERR] {message}", Colors.RED)

def log_debug(message: str):
    log(f"[DBG] {message}", Colors.BLUE)

def get_process_on_port(port: int) -> Optional[int]:
    """获取占用端口的进程 PID"""
    try:
        # Windows: netstat -ano | findstr :<port>
        if sys.platform == "win32":
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.split()
                        pid = int(parts[-1])
                        log_debug(f"端口 {port} 被进程 {pid} 占用")
                        return pid
        # Linux/macOS: lsof -ti:<port>
        else:
            result = subprocess.run(
                f"lsof -ti:{port}",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip())
                log_debug(f"端口 {port} 被进程 {pid} 占用")
                return pid
    except Exception as e:
        log_debug(f"检查端口 {port} 时出错: {e}")
    
    return None

def kill_process(pid: int, port: int):
    """强制 kill 进程及其子进程树"""
    try:
        if sys.platform == "win32":
            # /T = kill 整个进程树（含子进程）
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True,
                           capture_output=True)  # 不 check，避免进程已退出时报错
        else:
            os.kill(pid, signal.SIGKILL)
        log_success(f"已 kill 进程 {pid} (端口 {port})")
    except Exception as e:
        log_error(f"Kill 进程 {pid} 失败: {e}")

def ensure_port_free(port: int, service_name: str):
    """确保端口空闲，最多重试 3 次"""
    log_info(f"检查 {service_name} 端口 {port}...")
    pid = get_process_on_port(port)
    if not pid:
        log_success(f"端口 {port} 空闲")
        return

    log_warning(f"端口 {port} 被占用，正在 kill 进程 {pid}...")
    kill_process(pid, port)

    # 等待端口释放，最多重试 3 次
    for attempt in range(3):
        time.sleep(1.5)
        pid = get_process_on_port(port)
        if not pid:
            log_success(f"端口 {port} 已释放")
            return
        log_debug(f"端口 {port} 仍被占用 (PID {pid})，重试 kill... ({attempt + 1}/3)")
        kill_process(pid, port)

    log_error(f"端口 {port} 仍被占用，请手动处理")
    sys.exit(1)

def check_dependencies():
    """检查依赖"""
    log_info("检查项目依赖...")
    
    # 检查 Python 虚拟环境
    venv_python = Path(".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
    if not venv_python.exists():
        log_error("未找到虚拟环境，请先运行: python -m venv .venv && .venv/Scripts/activate && pip install -e .")
        sys.exit(1)
    
    # 检查前端依赖
    node_modules = Path("ui/node_modules")
    if not node_modules.exists():
        log_warning("前端依赖未安装，正在安装...")
        try:
            subprocess.run("npm install", cwd="ui", shell=True, check=True)
            log_success("前端依赖安装完成")
        except subprocess.CalledProcessError:
            log_error("前端依赖安装失败")
            sys.exit(1)
    
    log_success("依赖检查完成")

def start_backend():
    """启动后端服务"""
    log_info(f"启动后端服务 (http://{BACKEND_HOST}:{BACKEND_PORT})...")
    
    # 使用虚拟环境的 Python
    if sys.platform == "win32":
        python_exe = Path(".venv/Scripts/python.exe").resolve()
    else:
        python_exe = Path(".venv/bin/python").resolve()
    
    # 启动 uvicorn
    cmd = [
        str(python_exe),
        "-m", "uvicorn",
        "solopreneur.api.main:app",
        "--host", BACKEND_HOST,
        "--port", str(BACKEND_PORT),
        "--reload",
        "--log-level", "debug"
    ]
    
    log_debug(f"后端命令: {' '.join(cmd)}")
    
    # 设置 UTF-8 环境变量（解决 Windows GBK 编码问题）
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout，避免 PowerShell 红字误报
        text=True,
        bufsize=1,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',  # 遇到无法解码的字符用 ? 替换
        env=env  # 使用 UTF-8 环境
    )
    
    return process

def start_frontend():
    """启动前端服务"""
    log_info(f"启动前端服务 (http://{FRONTEND_HOST}:{FRONTEND_PORT})...")
    
    # 使用 npm run dev
    cmd = "npm run dev"
    
    log_debug(f"前端命令: {cmd}")
    
    # 设置 UTF-8 环境变量
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    process = subprocess.Popen(
        cmd,
        cwd="ui",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',  # 遇到无法解码的字符用 ? 替换
        env=env  # 使用 UTF-8 环境
    )
    
    return process

def stream_output(process, prefix: str, color: str):
    """流式输出进程日志"""
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"{color}[{prefix}]{Colors.END} {line.rstrip()}")
    process.stdout.close()

def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}>>> Solopreneur Launcher{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}\n")
    
    try:
        # 1. 检查依赖
        check_dependencies()
        
        # 2. 确保端口空闲
        ensure_port_free(BACKEND_PORT, "后端")
        ensure_port_free(FRONTEND_PORT, "前端")
        
        # 3. 启动后端
        backend_process = start_backend()
        log_success(f"后端进程已启动 (PID: {backend_process.pid})")
        time.sleep(2)  # 等待后端启动
        
        # 4. 启动前端
        frontend_process = start_frontend()
        log_success(f"前端进程已启动 (PID: {frontend_process.pid})")
        
        # 5. 显示访问信息
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}[OK] All services started!{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}\n")
        print(f"  Backend API:  {Colors.CYAN}http://localhost:{BACKEND_PORT}{Colors.END}")
        print(f"  API Docs:     {Colors.CYAN}http://localhost:{BACKEND_PORT}/docs{Colors.END}")
        print(f"  Frontend UI:  {Colors.CYAN}http://localhost:{FRONTEND_PORT}{Colors.END}")
        print(f"\n{Colors.YELLOW}局域网访问:{Colors.END}")
        # 获取本机 IP
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"  Backend API:  {Colors.CYAN}http://{local_ip}:{BACKEND_PORT}{Colors.END}")
            print(f"  API Docs:     {Colors.CYAN}http://{local_ip}:{BACKEND_PORT}/docs{Colors.END}")
            print(f"  Frontend UI:  {Colors.CYAN}http://{local_ip}:{FRONTEND_PORT}{Colors.END}")
        except Exception:
            pass
        print(f"\n  Press {Colors.YELLOW}Ctrl+C{Colors.END} to stop\n")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}\n")
        
        # 6. 流式输出日志
        import threading
        
        backend_thread = threading.Thread(
            target=stream_output,
            args=(backend_process, "后端", Colors.BLUE),
            daemon=True
        )
        frontend_thread = threading.Thread(
            target=stream_output,
            args=(frontend_process, "前端", Colors.GREEN),
            daemon=True
        )
        
        backend_thread.start()
        frontend_thread.start()
        
        # 7. 等待进程
        try:
            backend_process.wait()
            frontend_process.wait()
        except KeyboardInterrupt:
            log_warning("\n收到停止信号，正在关闭服务...")
            
            # 终止进程
            backend_process.terminate()
            frontend_process.terminate()
            
            # 等待进程结束
            time.sleep(1)
            
            # 强制 kill
            if backend_process.poll() is None:
                backend_process.kill()
            if frontend_process.poll() is None:
                frontend_process.kill()
            
            log_success("服务已停止")
    
    except Exception as e:
        log_error(f"启动失败: {e}")
        import traceback
        log_debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
