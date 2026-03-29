from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Space Weather Early Warning API"
    environment: str = "development"

    poll_interval_seconds: int = 300
    request_timeout_seconds: float = 10.0
    request_retries: int = 2
    use_mock_on_failure: bool = True

    swpc_kp_url: str = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    swpc_mag_url: str = "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json"
    swpc_xray_url: str = "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json"
    swpc_proton_url: str = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-3-day.json"
    swpc_plasma_url: str = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    swpc_alerts_url: str = "https://services.swpc.noaa.gov/products/alerts.json"
    plasma_danger_speed_kms: float = 600.0

    roti_enabled: bool = False
    roti_api_url: str | None = None
    roti_fallback_enabled: bool = True

    storage_enabled: bool = True
    storage_sqlite_file: str = "data/space_weather.sqlite3"

    donki_enabled: bool = True
    donki_api_key: str | None = None
    donki_base_url: str = "https://api.nasa.gov/DONKI"
    donki_lookback_days: int = 3
    donki_refresh_minutes: int = 15

    noaa_alert_intel_enabled: bool = True
    noaa_alert_intel_max_records: int = 120
    noaa_alert_memory_file: str = "son_islenen_tarih.txt"
    noaa_alert_report_file: str = "firtina_raporu.txt"

    gemini_enabled: bool = True
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    ai_cooldown_seconds: int = 15

    alert_cooldown_minutes: int = 30
    max_alert_history: int = 200

    email_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "space-weather@localhost"
    smtp_to: str = "ops@localhost"

    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("poll_interval_seconds")
    @classmethod
    def validate_poll_interval(cls, value: int) -> int:
        if value < 15:
            raise ValueError("poll_interval_seconds must be at least 15")
        return value

    @field_validator("request_retries")
    @classmethod
    def validate_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("request_retries must be zero or greater")
        return value

    @field_validator("donki_lookback_days")
    @classmethod
    def validate_donki_lookback_days(cls, value: int) -> int:
        if value < 1 or value > 30:
            raise ValueError("donki_lookback_days must be between 1 and 30")
        return value

    @field_validator("donki_refresh_minutes")
    @classmethod
    def validate_donki_refresh_minutes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("donki_refresh_minutes must be at least 1")
        return value

    @field_validator("plasma_danger_speed_kms")
    @classmethod
    def validate_plasma_speed_threshold(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("plasma_danger_speed_kms must be greater than 0")
        return value

    @field_validator("noaa_alert_intel_max_records")
    @classmethod
    def validate_noaa_alert_intel_max_records(cls, value: int) -> int:
        if value < 1:
            raise ValueError("noaa_alert_intel_max_records must be at least 1")
        return value

    @field_validator("ai_cooldown_seconds")
    @classmethod
    def validate_ai_cooldown_seconds(cls, value: int) -> int:
        if value < 0:
            raise ValueError("ai_cooldown_seconds must be zero or greater")
        return value

    @property
    def smtp_to_list(self) -> list[str]:
        return [item.strip() for item in self.smtp_to.split(",") if item.strip()]

    @property
    def frontend_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.frontend_origin.split(",") if item.strip()]
        if not origins:
            return ["http://localhost:5173"]
        return list(dict.fromkeys(origins))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
