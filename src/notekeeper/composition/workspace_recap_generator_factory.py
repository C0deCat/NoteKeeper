"""Build recap generators from current workspace settings."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import RecapGenerator
from notekeeper.domain import CampaignId
from notekeeper.infrastructure.deepseek import (
    DeepSeekRecapGenerator,
    LocalDeepSeekRequestLogger,
    NoOpDeepSeekRequestLogger,
)

from .factory import LocalServices


class WorkspaceRecapGeneratorFactory:
    def __init__(self, services: LocalServices) -> None:
        self._services = services

    def create(self, campaign_id: CampaignId) -> RecapGenerator:
        campaign = self._services.repositories.campaign_repository.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"campaign {campaign_id} was not found")
        override = self._services.workspace_settings_repository.get(
            campaign.workspace_id
        )
        settings = self._services.settings
        model_name = (
            override.deepseek_model_name
            if override is not None
            else settings.deepseek_model_name
        )
        temperature = (
            override.deepseek_temperature
            if override is not None
            else settings.deepseek_temperature
        )
        request_logger = (
            LocalDeepSeekRequestLogger(
                self._services.artifact_storage,
                include_payloads=settings.deepseek_log_full_payloads,
                now=self._services.clock.now,
            )
            if settings.deepseek_request_logging_enabled
            else NoOpDeepSeekRequestLogger()
        )
        return DeepSeekRecapGenerator(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model_name=model_name,
            temperature=temperature,
            timeout_seconds=settings.deepseek_timeout_seconds,
            retry_count=settings.deepseek_retry_count,
            retry_backoff_seconds=settings.deepseek_retry_backoff_seconds,
            request_logger=request_logger,
        )


__all__ = ["WorkspaceRecapGeneratorFactory"]
