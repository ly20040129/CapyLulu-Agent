"""配置加载 + 动态更新（LLM + UI 配色 + 数据目录 data_dir）"""
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 项目根（含 config.yaml / data / assets）


class Config:
    """读写项目根目录 config.yaml（LLM + UI 配色 + 数据目录）。"""

    def __init__(self, config_path: str = "config.yaml"):
        self._path = Path(config_path)
        if not self._path.is_absolute():
            self._path = PROJECT_ROOT / self._path
        self._data = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        with open(self._path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save(self):
        """写回 yaml"""
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    @property
    def llm(self) -> dict:
        return self._data.get("llm", {})

    @property
    def llm_provider(self) -> str:
        return self.llm.get("provider", "zhipu")

    @property
    def llm_config(self) -> dict:
        return self.llm.get(self.llm_provider, {})

    @property
    def agent(self) -> dict:
        return self._data.get("agent", {})

    @property
    def general(self) -> dict:
        """通用配置段（general.data_dir 等）。"""
        return self._data.get("general", {})

    @property
    def data_dir(self) -> Path:
        """用户数据目录（绝对 Path）。

        config.yaml 的 general.data_dir 可自定义；相对路径以项目根为基准，
        默认 "data"。会话 / 任务 / 日志 / agents / skills / memory 全部随它走。
        """
        raw = self.general.get("data_dir") or "data"
        p = Path(str(raw))
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    def update_data_dir(self, new_dir: str) -> str:
        """写回 general.data_dir（返回新路径字符串或错误信息）。"""
        new_dir = (new_dir or "").strip()
        if not new_dir:
            return "数据目录不能为空"
        self._data.setdefault("general", {})
        self._data["general"]["data_dir"] = new_dir
        try:
            self._save()
        except Exception as e:
            return f"配置保存失败（内存已更新）: {e}"
        return new_dir

    @property
    def ui(self) -> dict:
        """界面配置（标题、配色名等）"""
        return self._data.get("ui", {})

    @property
    def palette(self) -> str:
        """当前配色方案名，默认琥珀暖暗"""
        return self.ui.get("palette", "琥珀暖暗")

    def update_palette(self, name: str) -> str:
        """保存配色到 yaml"""
        self._data.setdefault("ui", {})
        self._data["ui"]["palette"] = name
        try:
            self._save()
        except Exception as e:
            return f"配色已应用（写入失败: {e}）"
        return name

    # ---- 可选的厂商预设 ----
    PROVIDER_PRESETS = {
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4/",
            "model": "glm-4-plus",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
        },
    }

    def update_llm(self, provider: str, api_key: str, model: str = "", base_url: str = "") -> str:
        """动态更新 LLM 配置并写回 yaml，返回状态消息"""
        provider = provider.lower()
        if provider not in self.PROVIDER_PRESETS:
            return f"未知厂商: {provider}"
        preset = self.PROVIDER_PRESETS[provider]
        if not base_url:
            base_url = preset["base_url"]
        if not model:
            model = preset["model"]

        # 更新内存
        self._data.setdefault("llm", {})
        self._data["llm"]["provider"] = provider
        self._data["llm"][provider] = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }
        # 保留另一家厂商的旧配置（如果有），方便切换
        try:
            self._save()
        except Exception as e:
            return f"配置保存失败（内存已更新）: {e}"
        return f"已切换到 {provider} / {model}"


# 全局单例
config = Config()
