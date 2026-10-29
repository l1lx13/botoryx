from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_ids: str = ""
    proxy_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admins(self) -> set[int]:
        result: set[int] = set()

        for item in self.admin_ids.split(","):
            item = item.strip()
            if item:
                try:
                    result.add(int(item))
                except ValueError:
                    continue

        return result


settings = Settings()