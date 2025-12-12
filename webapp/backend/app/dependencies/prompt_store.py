from fastapi import Depends
from common.prompt_store import PromptStore
from app.auth.dependencies import get_db


def get_prompt_store(db=Depends(get_db)) -> PromptStore:  # type: ignore[name-defined]
    return PromptStore(db=db)
