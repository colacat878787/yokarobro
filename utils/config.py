import json
import os

SETTINGS_FILE = "guild_settings.json"

class ConfigManager:
    def __init__(self):
        self.settings = self._load_all()

    def _load_all(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"❌ [Config] 無法讀取設定檔: {e}")
                return {}
        return {}

    def _save_all(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ [Config] 無法儲存設定檔: {e}")

    def get_guild_settings(self, guild_id: int):
        gid = str(guild_id)
        if gid not in self.settings:
            self.settings[gid] = {
                "verify_role": "星辰大合唱",
                "staff_role": "管理員",
                "welcome_channel": None,
                "log_channel": None,
                "modmail_category": None,
                "ticket_category": None,
                "xp_rate": 1.0,
                "ai_enabled": True
            }
            self._save_all()
        return self.settings[gid]

    def set_guild_setting(self, guild_id: int, key: str, value):
        gid = str(guild_id)
        if gid not in self.settings:
            self.get_guild_settings(guild_id)
        self.settings[gid][key] = value
        self._save_all()

config_manager = ConfigManager()
