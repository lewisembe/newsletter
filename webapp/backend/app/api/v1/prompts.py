"""
Prompts management endpoints for admin panel (read/update/test).
"""

from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from app.auth.dependencies import get_current_admin, get_db
from app.schemas.prompts import PromptResponse, PromptUpdate, PromptTestResponse
from common.postgres_db import PostgreSQLURLDatabase
import logging
from string import Formatter
from common.llm import LLMClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[PromptResponse])
async def list_prompts(
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """List all prompts for admin UI."""
    prompts = db.list_prompts()
    return prompts


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    updates: PromptUpdate,
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """Update a prompt (admin only)."""
    prompt = db.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt no encontrado"
        )

    success = db.update_prompt(prompt_id, updates.model_dump(exclude_none=True))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el prompt"
        )

    return db.get_prompt_by_id(prompt_id)


@router.post("/{prompt_id}/test", response_model=PromptTestResponse)
async def test_prompt(
    prompt_id: str,
    payload: Any = Body(...),
    execute: bool = Query(False, description="Ejecutar contra el LLM (false = solo render)"),
    admin: dict = Depends(get_current_admin),
    db: PostgreSQLURLDatabase = Depends(get_db)
):
    """
    Test prompt endpoint.

    - Por defecto (execute=false) solo renderiza placeholders y devuelve eco.
    - Con execute=true intenta llamar al LLM usando default_model/params del prompt.
      Si falla (sin API key, error de red), se devuelve nota de fallo.
    """
    prompt = db.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt no encontrado"
        )

    variables = payload if isinstance(payload, dict) else {}
    system_prompt = prompt.get("system_prompt") or ""
    user_prompt_template = prompt.get("user_prompt_template") or ""

    # Safe formatter to avoid KeyError
    def safe_format(template: str, values: dict) -> str:
        try:
            keys = {fn for _, fn, _, _ in Formatter().parse(template) if fn}
            missing = keys - set(values.keys())
            for m in missing:
                values[m] = f"{{missing:{m}}}"
            return template.format_map(values)
        except Exception:
            # Fallback simple replace
            rendered = template
            for k, v in values.items():
                rendered = rendered.replace("{" + str(k) + "}", str(v))
            return rendered

    rendered_user = safe_format(user_prompt_template, dict(variables))

    note = "Renderizado sin llamada LLM"
    if execute:
        try:
            llm = LLMClient()
            response_format = prompt.get("response_format")
            content = llm.call(
                prompt=rendered_user,
                system_prompt=system_prompt,
                model=prompt.get("default_model") or "gpt-4o-mini",
                temperature=prompt.get("temperature") or 0.2,
                max_tokens=prompt.get("max_tokens") or 500,
                response_format=response_format if response_format else None,
                stage=prompt.get("stage", "unknown"),
                operation=prompt.get("operation", "prompt_test")
            )
            note = "LLM ejecutado con éxito"
            rendered_user = content
        except Exception as e:
            note = f"Error al llamar LLM: {e}"

    return PromptTestResponse(
        prompt_id=prompt_id,
        stage=prompt['stage'],
        operation=prompt['operation'],
        received_payload=payload,
        note=note,
    )
