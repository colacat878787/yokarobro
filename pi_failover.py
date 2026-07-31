#!/usr/bin/env python3
"""
🍓 Raspberry Pi Zero 2W 備援系統
當主伺服器的優卡洛(幽芙優)離線時，自動啟動備援機器人
當主伺服器恢復上線時，自動關閉備援機器人

使用方式：
1. 在 Pi 上執行: python3 pi_failover.py
2. 確保 .env 中有 DISCORD_TOKEN（備援用的 token）
3. 主伺服器會每 30 秒發送心跳訊號到這台 Pi

建議搭配 systemd 服務自動啟動
"""

import os
import sys
import time
import json
import subprocess
import threading
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ===== 設定 =====
HEARTBEAT_PORT = 8888           # 心跳監聽埠
HEARTBEAT_TIMEOUT = 120         # 心跳超時（秒），超過此時間未收到心跳就啟動備援
HEARTBEAT_INTERVAL = 30         # 主伺服器發送心跳的間隔（秒）
BOT_STARTUP_DELAY = 5           # 啟動備援前的延遲（秒）
LOG_FILE = "pi_failover.log"    # 日誌檔案

# ===== 全域狀態 =====
last_heartbeat = time.time()
backup_process = None
is_backup_running = False
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

class HeartbeatHandler(BaseHTTPRequestHandler):
    """處理來自主伺服器的心跳訊號"""
    
    def do_POST(self):
        global last_heartbeat, main_server_online
        
        if self.path == "/heartbeat":
            last_heartbeat = time.time()
            main_server_online = True
            
            # 如果備援正在運行，停止它
            if is_backup_running:
                log("📡 收到主伺服器心跳，正在停止備援...")
                stop_backup_bot()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "backup_running": is_backup_running}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """提供狀態查詢"""
        if self.path == "/status":
            status = {
                "main_server_online": main_server_online,
                "backup_running": is_backup_running,
                "last_heartbeat": datetime.fromtimestamp(last_heartbeat).strftime("%Y-%m-%d %H:%M:%S"),
                "uptime": int(time.time() - last_heartbeat),
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

def run_heartbeat_server():
    """啟動心跳監聽伺服器"""
    server = HTTPServer(("0.0.0.0", HEARTBEAT_PORT), HeartbeatHandler)
    log(f"🍓 心跳監聽伺服器已啟動 (埠: {HEARTBEAT_PORT})")
    server.serve_forever()

def monitor_loop():
    """監控迴圈：檢查心跳是否超時"""
    global main_server_online
    
    log("🔍 監控迴圈已啟動")
    
    while True:
        current_time = time.time()
        elapsed = current_time - last_heartbeat
        
        if elapsed > HEARTBEAT_TIMEOUT and not is_backup_running:
            # 心跳超時，主伺服器可能離線
            log(f"⚠️ 心跳超時 ({elapsed:.0f}秒)，主伺服器可能離線！")
            main_server_online = False
            start_backup_bot()
        elif elapsed <= HEARTBEAT_TIMEOUT and is_backup_running:
            # 收到心跳，但備援還在運行
            log("📡 主伺服器已恢復，正在停止備援...")
            stop_backup_bot()
        
        time.sleep(10)  # 每 10 秒檢查一次

def signal_handler(sig, frame):
    """處理 Ctrl+C"""
    log("🛑 正在關閉備援系統...")
    if is_backup_running:
        stop_backup_bot()
    sys.exit(0)

def main():
    log("=" * 50)
    log("🍓 幽芙優(小幽) Raspberry Pi 備援系統")
    log(f"📡 心跳埠: {HEARTBEAT_PORT}")
    log(f"⏱️ 超時設定: {HEARTBEAT_TIMEOUT}秒")
    log(f"📁 工作目錄: {os.getcwd()}")
    log("=" * 50)
    
    # 檢查 .env 檔案
    if not os.path.exists(".env"):
        log("❌ 找不到 .env 檔案！請確保在正確的目錄中執行")
        log("💡 提示：請在此目錄建立 .env 並設定 DISCORD_TOKEN")
        return
    
    # 註冊信號處理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 啟動心跳監聽伺服器（背景執行緒）
    heartbeat_thread = threading.Thread(target=run_heartbeat_server, daemon=True)
    heartbeat_thread.start()
    
    # 等待伺服器啟動
    time.sleep(1)
    
    # 啟動監控迴圈
    try:
        monitor_loop()
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()