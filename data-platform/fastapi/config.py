"""
config.py — Configuração centralizada via pydantic-settings.
============================================================
Substitui leituras diretas de os.environ espalhadas pelo código.
Todas as variáveis podem ser sobrescritas via ambiente (.env ou docker-compose).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação FastAPI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Aplicação ---
    app_title: str = "ComexStat API"
    app_version: str = "2.0.0"
    app_description: str = (
        "API de estatísticas de comércio exterior, investimentos estrangeiros (RDE), "
        "cadastro mineiro (SCM) e dados geoespaciais (Sigmine) do Ceará. "
        "Dados pré-computados via Airflow → PostgreSQL."
    )

    # --- Banco de dados ---
    database_url: str = (
        "postgresql://postgres:postgres_pass@postgres:5432/comexstat_platform"
    )
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # --- CORS ---
    cors_origins: list[str] = ["*"]
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]

    # --- URLs externas (referência para mensagens) ---
    airflow_url: str = "http://localhost:8080"

    @property
    def asyncpg_url(self) -> str:
        """URL normalizada para asyncpg (sem sufixos de driver SQLAlchemy)."""
        return (
            self.database_url
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
        )


@lru_cache
def get_settings() -> Settings:
    """Singleton de configurações (cacheado)."""
    return Settings()


settings = get_settings()
