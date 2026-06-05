from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import os
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_cache: Optional[dict] = None


def _load_raw(path: Path = _CONFIG_PATH) -> dict:
    global _cache
    if _cache is None:
        with open(path, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache


def _env(name: str) -> str:
    val = os.getenv(name)
    if val is None:
        raise EnvironmentError(f"Required env variable '{name}' is not set")
    return val


# ─── Dataclasses ──────────────────────────────────────────

@dataclass
class CameraConfig:
    ip: str
    username: str
    password: str
    latitude: float
    longitude: float
    preset_positions: list[int]
    preset_map: dict[int,str]


@dataclass
class ModelsConfig:
    sam3_model_id: str
    sam3_threshold: float
    sam3_crop_padding: int
    vlm_model_id: str
    vlm_adapter_path: str
    vlm_max_new_tokens: int


@dataclass
class DetectionConfig:
    time_interval: int
    max_retries: int
    retry_delay: int
    max_consecutive_failures: int


@dataclass
class TelegramConfig:
    bot_token: str
    review_threshold: int
    subscribers: list[int]


@dataclass
class PathsConfig:
    base: Path
    forestfire: Path
    nonfire: Path
    uncertain: Path
    no_smoke: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "forestfire": self.forestfire,
            "nonfire": self.nonfire,
            "uncertain": self.uncertain,
        }


@dataclass
class AppConfig:
    cameras: list[CameraConfig]
    detection: DetectionConfig
    models: ModelsConfig
    paths: PathsConfig
    telegram: TelegramConfig
    healthchecks_uuid: Optional[str]

    @classmethod
    def load(cls, path: Path = _CONFIG_PATH) -> AppConfig:
        raw = _load_raw(path)

        # --- Cameras ---
        cameras = []
        for cam in raw["cameras"]:
            cameras.append(CameraConfig(
                ip=cam["ip"],
                username=cam["username"],
                password=_env(cam["password_env"]),
                latitude=cam["latitude"],
                longitude=cam["longitude"],
                preset_positions=cam["preset_positions"],
                preset_map=dict(zip(cam["preset_positions"], cam["in_cam_preset_positions"])),
            ))

        # --- Detection ---
        d = raw["detection"]
        detection = DetectionConfig(
            time_interval=d["time_interval_seconds"],
            max_retries=d["max_retries"],
            retry_delay=d["retry_delay_seconds"],
            max_consecutive_failures=d["max_consecutive_failures"],
        )

        # --- Models ---
        m = raw["models"]
        models = ModelsConfig(
            sam3_model_id=m["sam3"]["model_id"],
            sam3_threshold=m["sam3"]["threshold"],
            sam3_crop_padding=m["sam3"]["crop_padding"],
            vlm_model_id=m["vlm"]["model_id"],
            vlm_adapter_path=m["vlm"]["adapter_path"],
            vlm_max_new_tokens=m["vlm"]["max_new_tokens"],
        )

        # --- Paths ---
        base = Path(raw["paths"]["base"])
        paths = PathsConfig(
            base=base,
            forestfire=base / raw["paths"]["forestfire_subdir"],
            nonfire=base / raw["paths"]["nonfire_subdir"],
            uncertain=base / raw["paths"]["uncertain_subdir"],
            no_smoke=base / raw["paths"]["no_smoke_subdir"],
        )

        # --- Telegram ---
        tg = raw["telegram"]
        telegram = TelegramConfig(
            bot_token=_env(tg["bot_token_env"]),
            review_threshold=tg["review_threshold"],
            subscribers=[s["chat_id"] for s in tg["subscribers"]],
        )

        # --- Healthchecks ---
        hc_env = raw["healthchecks"]["uuid_env"]
        hc_uuid = os.getenv(hc_env)  # optional, kein Fehler wenn nicht gesetzt

        return cls(
            cameras=cameras,
            detection=detection,
            models=models,
            paths=paths,
            telegram=telegram,
            healthchecks_uuid=hc_uuid,
        )
    
if __name__ == "__main__":
    cfg = AppConfig.load()
    print(cfg.telegram.subscribers)