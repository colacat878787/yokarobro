#!/usr/bin/env python3
"""
🍓 Raspberry Pi 備援系統快速檢查腳本
檢查 Pi 的環境、設定和連線狀態

使用方式：
python3 pi_check.py
"""

import os
import sys
import subprocess
import socket
import json
from datetime import datetime

# 顏色輸出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def check_command(cmd, name):
    """檢查指令是否存在"""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, check=True)
        print_success(f"{name} 已安裝")
        return True
    except:
        print_error(f"{name} 未安裝或不在 PATH 中")
        return False

def check_python_package(package):
    """檢查 Python 套件是否安裝"""
    try:
        __import__(package)
        print_success(f"Python 套件 '{package}' 已安裝")
        return True
    except ImportError:
        print_error(f"Python 套件 '{package}' 未安裝")
        return False

def check_file_exists(filepath, description):
    """檢查檔案是否存在"""
    if os.path.exists(filepath):
        print_success(f"{description} 存在: {filepath}")
        return True
    else:
        print_error(f"{description} 不存在: {filepath}")
        return False

def check_env_variable(var_name, required=True):
    """檢查環境變數是否設定"""
    value = os.getenv(var_name)
    if value:
        # 隱藏敏感資訊
        if 'TOKEN' in var_name or 'KEY' in var_name:
            display_value = value[:10] + "..." + value[-5:] if len(value) > 15 else "***"
        else:
            display_value = value
        print_success(f"{var_name} = {display_value}")
        return True
    else:
        if required:
            print_error(f"{var_name} 未設定（必要）")
        else:
            print_warning(f"{var_name} 未設定（可選）")
        return False

def test_main_server_connection(main_server_url):
    """測試與主伺服器的連線"""
    try:
        import urllib.request
        url = f"{main_server_url}/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("status") == "ok":
                    print_success(f"可以連接主伺服器 ({url})")
                    print_info(f"  機器人名稱: {data.get('bot_name', 'N/A')}")
                    print_info(f"  伺服器數量: {data.get('guilds', 'N/A')}")
                    print_info(f"  延遲: {data.get('latency', 'N/A')}ms")
                    return True
                else:
                    print_warning(f"主伺服器回應異常: {data}")
                    return False
    except urllib.error.URLError as e:
        print_error(f"無法連接主伺服器 ({url}): {e}")
        return False
    except urllib.error.HTTPError as e:
        print_error(f"主伺服器回應錯誤: HTTP {e.code}")
        return False
    except Exception as e:
        print_error(f"測試主伺服器連線時發生錯誤: {e}")
        return False

def check_port(port):
    """檢查埠號是否被佔用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            print_success(f"埠號 {port} 正在監聽")
            return True
        else:
            print_warning(f"埠號 {port} 未監聽（正常，如果服務未啟動）")
            return False
    except Exception as e:
        print_error(f"檢查埠號 {port} 時發生錯誤: {e}")
        return False

def check_service_status(service_name):
    """檢查 systemd 服務狀態"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        status = result.stdout.strip()
        if status == "active":
            print_success(f"服務 {service_name} 正在運行")
            return True
        else:
            print_warning(f"服務 {service_name} 狀態: {status}")
            return False
    except Exception as e:
        print_error(f"檢查服務時發生錯誤: {e}")
        return False

def test_heartbeat_endpoint(port=8888):
    """測試心跳端點"""
    try:
        import urllib.request
        url = f"http://localhost:{port}/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            print_success(f"心跳端點正常運作 (http://localhost:{port}/status)")
            print_info(f"  主伺服器狀態: {'在線' if data.get('main_server_online') else '離線'}")
            print_info(f"  備援狀態: {'運行中' if data.get('backup_running') else '未運行'}")
            print_info(f"  最後心跳: {data.get('last_heartbeat', 'N/A')}")
            return True
    except urllib.error.URLError:
        print_warning(f"心跳端點未啟動 (http://localhost:{port}/status)")
        return False
    except Exception as e:
        print_error(f"測試心跳端點時發生錯誤: {e}")
        return False

def check_git_repo():
    """檢查 Git 倉庫狀態"""
    try:
        # 檢查是否為 git 倉庫
        subprocess.run(["git", "status"], capture_output=True, check=True, cwd=os.getcwd())
        
        # 取得當前分支
        branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
        print_success(f"Git 倉庫正常（分支: {branch}）")
        
        # 檢查是否有未提交的變更
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if result.stdout.strip():
            print_warning("有未提交的變更")
        else:
            print_success("工作目錄乾淨")
        
        # 檢查與遠端的不同步
        result = subprocess.run(["git", "fetch"], capture_output=True, text=True)
        if result.returncode == 0:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/main"],
                capture_output=True,
                text=True
            )
            commits_behind = int(result.stdout.strip())
            if commits_behind > 0:
                print_warning(f"落後遠端 {commits_behind} 個 commit（建議執行 git pull）")
            else:
                print_success("與遠端同步")
        
        return True
    except subprocess.CalledProcessError:
        print_error("不是有效的 Git 倉庫")
        return False
    except Exception as e:
        print_error(f"檢查 Git 倉庫時發生錯誤: {e}")
        return False

def check_network():
    """檢查網路連線"""
    try:
        # 檢查 DNS 解析
        socket.gethostbyname("discord.com")
        print_success("DNS 解析正常")
        
        # 檢查連線到 Discord
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("discord.com", 443))
        sock.close()
        if result == 0:
            print_success("可以連線到 Discord")
        else:
            print_error("無法連線到 Discord")
        
        return True
    except Exception as e:
        print_error(f"網路檢查失敗: {e}")
        return False

def main():
    print_header("🍓 幽芙優(小幽) Raspberry Pi 備援系統檢查")
    
    print(f"{Colors.BOLD}檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}")
    print(f"{Colors.BOLD}檢查目錄: {os.getcwd()}{Colors.RESET}\n")
    
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
    
    # 1. 系統需求檢查
    print_header("📋 系統需求檢查")
    
    checks = [
        ("python3", "Python 3"),
        ("pip3", "pip3"),
        ("git", "Git"),
        ("ffmpeg", "FFmpeg"),
    ]
    
    for cmd, name in checks:
        results["total"] += 1
        if check_command(cmd, name):
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # 2. Python 套件檢查
    print_header("📦 Python 套件檢查")
    
    packages = ["discord", "aiohttp", "dotenv"]
    for pkg in packages:
        results["total"] += 1
        if check_python_package(pkg):
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # 3. 檔案檢查
    print_header("📁 檔案檢查")
    
    files = [
        (".env", ".env 環境變數檔案"),
        ("yokaro.py", "主程式 yokaro.py"),
        ("pi_failover.py", "備援程式 pi_failover.py"),
        ("requirements.txt", "依賴清單 requirements.txt"),
    ]
    
    for filepath, desc in files:
        results["total"] += 1
        if check_file_exists(filepath, desc):
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # 4. 環境變數檢查
    print_header("⚙️  環境變數檢查")
    
    # 載入 .env
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()
        
        env_vars = [
            ("DISCORD_TOKEN", True),
            ("MAIN_SERVER_URL", True),
            ("GEMINI_API_KEY", False),
            ("GENIUS_ACCESS_TOKEN", False),
            ("DISCORD_CLIENT_SECRET", False),
        ]
        
        for var, required in env_vars:
            results["total"] += 1
            if check_env_variable(var, required):
                results["passed"] += 1
                if not required:
                    results["warnings"] += 1
            else:
                if required:
                    results["failed"] += 1
                else:
                    results["warnings"] += 1
    else:
        print_error(".env 檔案不存在，跳過環境變數檢查")
        results["failed"] += 1
    
    # 5. Git 倉庫檢查
    print_header("📊 Git 倉庫檢查")
    check_git_repo()
    
    # 6. 網路檢查
    print_header("🌐 網路檢查")
    check_network()
    
    # 7. 服務狀態檢查
    print_header("🔧 服務狀態檢查")
    
    results["total"] += 1
    if check_service_status("yokaro-failover"):
        results["passed"] += 1
    else:
        results["warnings"] += 1
    
    # 8. 埠號檢查
    print_header("🔌 埠號檢查")
    
    results["total"] += 1
    if check_port(8888):
        results["passed"] += 1
    else:
        results["warnings"] += 1
    
    # 9. 心跳端點測試
    if check_port(8888):
        test_heartbeat_endpoint()
    
    # 10. 主伺服器連線測試
    print_header("🌐 主伺服器連線測試")
    main_server_url = os.getenv("MAIN_SERVER_URL")
    if main_server_url:
        results["total"] += 1
        if test_main_server_connection(main_server_url):
            results["passed"] += 1
        else:
            results["failed"] += 1
    else:
        print_warning("未設定 MAIN_SERVER_URL，跳過主伺服器連線測試")
    
    # 總結
    print_header("📈 檢查總結")
    
    print(f"總檢查項目: {results['total']}")
    print_success(f"通過: {results['passed']}")
    if results['failed'] > 0:
        print_error(f"失敗: {results['failed']}")
    if results['warnings'] > 0:
        print_warning(f"警告: {results['warnings']}")
    
    # 建議
    print(f"\n{Colors.BOLD}💡 建議:{Colors.RESET}")
    
    if results['failed'] > 0:
        print("  • 請修正上述失敗的檢查項目")
    
    if results['warnings'] > 0:
        print("  • 警告項目不影響運行，但建議修正以獲得完整功能")
    
    if not os.path.exists(".env"):
        print("  • 複製 .env.pi.example 為 .env 並填入設定")
    
    if not check_service_status("yokaro-failover"):
        print("  • 啟動服務: sudo systemctl start yokaro-failover")
        print("  • 或執行安裝腳本: sudo bash pi_setup.sh")
    
    if not os.getenv("MAIN_SERVER_URL"):
        print("  • 設定主伺服器網址: 在 .env 中加入 MAIN_SERVER_URL")
    
    # 快速指令
    print(f"\n{Colors.BOLD}🚀 快速指令:{Colors.RESET}")
    print("  • 查看服務狀態: sudo systemctl status yokaro-failover")
    print("  • 查看日誌: sudo journalctl -u yokaro-failover -f")
    print("  • 重啟服務: sudo systemctl restart yokaro-failover")
    print("  • 測試狀態頁面: curl http://localhost:8888/status")
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}🍓 檢查完成！{Colors.RESET}\n")
    
    # 返回狀態碼
    return 0 if results['failed'] == 0 else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  檢查被中斷{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"檢查過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)