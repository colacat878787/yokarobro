#!/usr/bin/env python3
"""
🍓 Raspberry Pi Zero 2W 備援系統
當主伺服器的優卡洛(幽芙優)離線時，自動啟動備援機器人
當主伺服器恢復上線時，自動關閉備援機器人

使用方式：
1. 在 Pi 上執行: python3 pi_failover.py
2. 確保 .env 中有 DISCORD_TOKEN（備援用的 token）
3. 確保 .env 中有 MAIN_SERVER_URL（主伺服器的狀態查詢網址）

建議搭配 systemd 服務自動啟動
"""

import os
import sys
import time
import json
import subprocess
import threading
import signal
import urllib.request
import urllib.error
from datetime import datetime

# ===== 設定 =====
POLL_INTERVAL = 30              # 輪詢主伺服器的間隔（秒）
FAILOVER_THRESHOLD = 4          # 連續失敗次數後啟動備援（30秒 * 4 = 120秒）
BOT_STARTUP_DELAY = 5           # 啟動備援前的延遲（秒）
LOG_FILE = "pi_failover.log"    # 日誌檔案

# ===== 全域狀態 =====
backup_process = None
is_backup_running = False
consecutive_failures = 0
main_server_online = False

def log(msg):
    """寫入日誌"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except:
        pass

def start_backup_bot():
    """啟動備援機器人"""
    global backup_process, is_backup_running
    
    if is_backup_running:
        log("⚠️ 備援機器人已經在運行中，跳過啟動")
        return
    
    log("🚨 主伺服器離線！正在啟動備援機器人...")
    time.sleep(BOT_STARTUP_DELAY)
    
    try:
        # 確保程式碼是最新的
        log("📥 正在拉取最新程式碼...")
        subprocess.run(["git", "pull", "origin", "main"], 
                      capture_output=True, timeout=30)
        
        # 安裝依賴
        log("📦 正在安裝依賴...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
                      capture_output=True, timeout=120)
        
        # 啟動機器人
        log("🤖 正在啟動幽芙優(小幽)備援機器人...")
        backup_process = subprocess.Popen(
            [sys.executable, "yokaro.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        is_backup_running = True
        log(f"✅ 備援機器人已啟動 (PID: {backup_process.pid})")
        
        # 啟動一個執行緒來監控備援機器人的輸出
        def monitor_output():
            global is_backup_running
            try:
                for line in backup_process.stdout:
                    log(f"[Bot] {line.strip()}")
            except:
                pass
            is_backup_running = False
            log("⚠️ 備援機器人程序已結束")
        
        threading.Thread(target=monitor_output, daemon=True).start()
        
    except Exception as e:
        log(f"❌ 啟動備援機器人失敗: {e}")
        is_backup_running = False

def stop_backup_bot():
    """停止備援機器人"""
    global backup_process, is_backup_running
    
    if not is_backup_running or backup_process is None:
        log("ℹ️ 備援機器人未在運行")
        return
    
    log("🛑 主伺服器已恢復上線，正在關閉備援機器人...")
    
    try:
        # 嘗試正常關閉
        backup_process.terminate()
        try:
            backup_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # 如果 10 秒內沒有關閉，強制殺死
            log("⚠️ 備援機器人未在時間內關閉，強制終止...")
            backup_process.kill()
            backup_process.wait(timeout=5)
        
        log("✅ 備援機器人已關閉")
    except Exception as e:
        log(f"❌ 關閉備援機器人失敗: {e}")
    finally:
        backup_process = None
        is_backup_running = False

class StatusHandler(BaseHTTPRequestHandler):
    """處理狀態查詢（用於主伺服器檢查 Pi 狀態）"""
    
    def do_GET(self):
        """提供狀態查詢"""
        if self.path == "/status":
            status = {
                "backup_running": is_backup_running,
                "main_server_online": main_server_online,
                "consecutive_failures": consecutive_failures,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 靜默 HTTP 日誌

def run_status_server():
    """啟動狀態查詢伺服器（可選）"""
    try:
        server = HTTPServer(("0.0.0.0", 8888), StatusHandler)
        log(f"🍓 狀態查詢伺服器已啟動 (埠: 8888)")
        server.serve_forever()
    except:
        log("⚠️ 狀態查詢伺服器啟動失敗（埠可能已被佔用）")

def check_main_server():
    """檢查主伺服器是否在線"""
    global consecutive_failures, main_server_online
    
    main_server_url = os.getenv("MAIN_SERVER_URL")
    if not main_server_url:
        log("❌ 未設定 MAIN_SERVER_URL，無法檢查主伺服器狀態")
        return False
    
    try:
        # 發送請求到主伺服器的狀態端點
        req = urllib.request.Request(
            f"{main_server_url}/status",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("status") == "ok"
    except urllib.error.URLError as e:
        log(f"⚠️ 無法連接主伺服器: {e}")
    except urllib.error.HTTPError as e:
        log(f"⚠️ 主伺服器回應錯誤: HTTP {e.code}")
    except Exception as e:
        log(f"⚠️ 檢查主伺服器時發生錯誤: {e}")
    
    return False

def monitor_loop():
    """監控迴圈：定期檢查主伺服器狀態"""
    global consecutive_failures, main_server_online
    
    log("🔍 監控迴圈已啟動")
    log(f"📡 輪詢間隔: {POLL_INTERVAL}秒")
    log(f"⚠️  備援觸發閥值: {FAILOVER_THRESHOLD}次連續失敗")
    
    while True:
        # 檢查主伺服器狀態
        is_online = check_main_server()
        
        if is_online:
            consecutive_failures = 0
            if not main_server_online:
                log("✅ 主伺服器已上線")
                main_server_online = True
            
            # 如果備援正在運行，停止它
            if is_backup_running:
                log("📡 主伺服器已恢復，正在停止備援...")
                stop_backup_bot()
        else:
            consecutive_failures += 1
            log(f"⚠️  主伺服器無回應 (連續失敗: {consecutive_failures}/{FAILOVER_THRESHOLD})")
            main_server_online = False
            
            # 如果連續失敗達到閥值，啟動備援
            if consecutive_failures >= FAILOVER_THRESHOLD and not is_backup_running:
                log(f"🚨 主伺服器離線！連續失敗 {consecutive_failures} 次")
                start_backup_bot()
        
        time.sleep(POLL_INTERVAL)

def signal_handler(sig, frame):
    """處理 Ctrl+C"""
    log("🛑 正在關閉備援系統...")
    if is_backup_running:
        stop_backup_bot()
    sys.exit(0)

def main():
    log("=" * 50)
    log("🍓 幽芙優(小幽) Raspberry Pi 備援系統")
    log(f"📡 輪詢間隔: {POLL_INTERVAL}秒")
    log(f"⏱️ 備援觸發: {FAILOVER_THRESHOLD}次連續失敗")
    log(f"📁 工作目錄: {os.getcwd()}")
    log("=" * 50)
    
    # 檢查 .env 檔案
    if not os.path.exists(".env"):
        log("❌ 找不到 .env 檔案！請確保在正確的目錄中執行")
        log("💡 提示：請在此目錄建立 .env 並設定 DISCORD_TOKEN 和 MAIN_SERVER_URL")
        return
    
    # 檢查 MAIN_SERVER_URL
    main_server_url = os.getenv("MAIN_SERVER_URL")
    if not main_server_url:
        log("❌ 未設定 MAIN_SERVER_URL！")
        log("💡 請在 .env 中加入主伺服器的狀態查詢網址")
        log("   例如: MAIN_SERVER_URL=https://yokaro.wayna1015.ccwu.cc")
        return
    
    log(f"🌐 主伺服器: {main_server_url}")
    
    # 註冊信號處理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 啟動狀態查詢伺服器（背景執行緒，可選）
    status_thread = threading.Thread(target=run_status_server, daemon=True)
    status_thread.start()
    
    # 等待伺服器啟動
    time.sleep(1)
    
    # 啟動監控迴圈
    try:
        monitor_loop()
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
