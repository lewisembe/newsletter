"""
API v1 router - aggregates all endpoint routers.
"""

from fastapi import APIRouter
from app.api.v1 import (
    health, newsletters, auth, users, categories, api_keys, sources, stage_executions,
    newsletter_configs, newsletter_executions, system_config, cookies, scheduled_executions,
    newsletter_subscriptions
)

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(newsletters.router, tags=["newsletters"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(cookies.router, prefix="/cookies", tags=["cookies"])
api_router.include_router(stage_executions.router, prefix="/stage-executions", tags=["stage-executions"])

# Newsletter Management routers
api_router.include_router(newsletter_configs.router, prefix="/newsletter-configs", tags=["newsletter-configs"])
api_router.include_router(newsletter_executions.router, prefix="/newsletter-executions", tags=["newsletter-executions"])
api_router.include_router(system_config.router, prefix="/system-config", tags=["system-config"])
api_router.include_router(scheduled_executions.router, prefix="/scheduled-executions", tags=["scheduled-executions"])
api_router.include_router(newsletter_subscriptions.router, prefix="/newsletter-subscriptions", tags=["newsletter-subscriptions"])
