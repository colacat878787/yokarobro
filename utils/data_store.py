import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

DATA_DIR = "data"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_data_path(filename: str) -> str:
    ensure_data_dir()
    return os.path.join(DATA_DIR, filename)

class DataStore:
    """通用 JSON 資料儲存類"""
    
    def __init__(self, filename: str):
        self.path = get_data_path(filename)
        self.data: Dict[str, Any] = self._load()
    
    def _load(self) -> dict:
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"讀取 {self.path} 失敗: {e}")
        return {}
    
    def save(self):
        try:
            ensure_data_dir()
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存 {self.path} 失敗: {e}")
    
    def get(self, key: str, default=None):
        return self.data.get(str(key), default)
    
    def set(self, key: str, value):
        self.data[str(key)] = value
        self.save()
    
    def delete(self, key: str):
        if str(key) in self.data:
            del self.data[str(key)]
            self.save()
    
    def get_all(self) -> dict:
        return self.data

# ===== 各功能專用資料儲存 =====

# 打招呼系統
greeting_store = DataStore("greetings.json")

# 簽到系統
checkin_store = DataStore("checkin.json")

# 成就系統
achievement_store = DataStore("achievements.json")

# 匿名告白
confession_store = DataStore("confessions.json")

# 寵物系統
pet_store = DataStore("pets.json")

# 賭場系統
casino_store = DataStore("casino.json")

# 抽卡系統
card_store = DataStore("cards.json")

# 拍賣系統
auction_store = DataStore("auctions.json")

# 頭銜系統
title_store = DataStore("titles.json")

# ===== 工具函數 =====

def parse_time_string(time_str: str) -> int:
    """解析時間字串 1h, 30m, 60s -> 秒數"""
    time_str = time_str.strip().lower()
    import re
    pattern = re.match(r'^(\d+)\s*([hms])$', time_str)
    if not pattern:
        raise ValueError(f"無法解析時間格式：{time_str}")
    value = int(pattern.group(1))
    unit = pattern.group(2)
    if unit == 'h':
        return value * 3600
    elif unit == 'm':
        return value * 60
    elif unit == 's':
        return value
    return value

def format_duration(seconds: int) -> str:
    """秒數 -> 可讀文字"""
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}小時{m}分鐘" if m else f"{h}小時"
    elif seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m}分鐘{s}秒" if s else f"{m}分鐘"
    return f"{seconds}秒"

def get_today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_weekday_name() -> str:
    weekdays = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    return weekdays[datetime.now().weekday()]