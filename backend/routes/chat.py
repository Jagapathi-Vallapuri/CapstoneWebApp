from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from utils.security import get_current_user
from typing import Any, Dict
import os
import requests
import logging
from utils.rag import profile_to_context
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from sqlalchemy.orm import Session
from db.session import get_db
from models.medical_profile import MedicalProfile

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    max_tokens: int | None = None
    temperature: float | None = None


class ChatResponse(BaseModel):
    reply: str
    raw: Dict[str, Any] | None = None
    meta: Dict[str, Any] | None = None


@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        from core.config import settings
    except Exception:
        settings = None

    # Get configuration with fallbacks (pydantic settings preferred)
    provider = (getattr(settings, 'LLM_PROVIDER', None) if settings else None) or os.getenv('LLM_PROVIDER', 'gemini')
    model = (getattr(settings, 'LLM_MODEL', None) if settings else None) or os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    api_key = (getattr(settings, 'LLM_API_KEY', None) if settings else None) or os.getenv('LLM_API_KEY')
    llm_url = (getattr(settings, 'LLM_API_URL', None) if settings else None) or os.getenv('LLM_API_URL')

    max_tokens = req.max_tokens or int(
        (getattr(settings, 'LLM_MAX_TOKENS', None) if settings else None) or os.getenv("LLM_MAX_TOKENS", "512")
    )
    temperature = req.temperature or float(
        (getattr(settings, 'LLM_TEMPERATURE', None) if settings else None) or os.getenv("LLM_TEMPERATURE", "0.2")
    )

    # Build RAG context from user's medical profile using an active DB session
    try:
        profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == getattr(current_user, 'id', None)).first()
    except Exception:
        profile = None
    profile_ctx = profile_to_context(profile)
    if profile_ctx:
        logging.info("Chat: including medical profile context (chars=%d)", len(profile_ctx))
    meta = {
        "used_context": bool(profile_ctx),
        "context_chars": len(profile_ctx) if profile_ctx else 0,
    }

    # If Gemini provider, construct URL if needed and call Gemini API branch
    if provider.lower() == 'gemini':
        if not model:
            model = 'gemini-2.5-flash'
        # Construct default Gemini endpoint if not provided
        if not llm_url:
            llm_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        # Append API key as query param
        if not api_key:
            logging.error('Gemini API key missing')
            raise HTTPException(status_code=500, detail='LLM API key not configured for Gemini')
        parsed = urlparse(llm_url)
        q = dict(parse_qsl(parsed.query))
        q['key'] = api_key
        llm_url = urlunparse(parsed._replace(query=urlencode(q)))

    # Build prompt with RAG context
        system_prompt = os.getenv('LLM_SYSTEM_PROMPT', 'You are a helpful assistant.')
        combined = f"{system_prompt}\n\n{profile_ctx}\n\nUser: {req.message}" if profile_ctx else f"{system_prompt}\n\nUser: {req.message}"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": combined}]}
            ],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_tokens)
            }
        }
        try:
            resp = requests.post(llm_url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            reply = None
            try:
                cands = data.get('candidates')
                if isinstance(cands, list) and cands:
                    content = cands[0].get('content') or {} 
                    parts = content.get('parts') or []
                    texts = [p.get('text', '') for p in parts if isinstance(p, dict) and 'text' in p]
                    reply = "".join(texts).strip()
            except Exception:
                reply = None

            if not reply:
                logging.warning(f"Unexpected response format from Gemini: {data}")
                reply = "I didn't get a response from the model."

            return {"reply": reply, "raw": data, "meta": meta}
        except requests.exceptions.Timeout:
            logging.error("Gemini request timed out")
            raise HTTPException(status_code=504, detail="Request to Gemini timed out")
        except requests.exceptions.RequestException as e:
            logging.exception("Gemini request failed")
            raise HTTPException(status_code=502, detail=f"Gemini request failed: {str(e)}")

    # Non-Gemini providers: Decide payload shape based on endpoint URL
    if not llm_url:
        logging.error('LLM API URL missing for non-Gemini provider')
        raise HTTPException(status_code=500, detail='LLM API URL not configured')
    lower_url = (llm_url or '').lower()
    is_chat_completions = 'chat/completions' in lower_url or '/v1/chat/completions' in lower_url
    is_completions = ('completions' in lower_url) and not is_chat_completions

    if is_chat_completions:
        # Chat completions expect messages + model + top-level max_tokens/temperature
        # build system prompt including user's medical profile as context
        system_prompt = os.getenv('LLM_SYSTEM_PROMPT', 'You are a helpful assistant.')
        if profile_ctx:
            system_prompt = system_prompt + "\n\n" + profile_ctx

        payload = {
            "model": model or None,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.message}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # remove explicit None model
        if not payload.get('model'):
            payload.pop('model', None)
    elif is_completions:
        # Older completions endpoints expect a 'prompt'
        # prefix the user's medical profile to the prompt
        prompt_text = (profile_ctx + "\n\n" + req.message) if profile_ctx else req.message
        payload = {
            "prompt": prompt_text,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if model:
            payload["model"] = model
    else:
        # LM Studio 'input' style
        input_text = (profile_ctx + "\n\n" + req.message) if profile_ctx else req.message
        payload = {
            "input": input_text,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
            },
        }
        if model:
            payload["model"] = model

    # prepare headers (Bearer) if API key provided
    headers = {}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        resp = requests.post(
            str(llm_url),
            json=payload,
            headers=headers or None,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        reply = None

        try:
            choices = data.get('choices')
            if isinstance(choices, list) and len(choices) > 0:
                first = choices[0]
                if isinstance(first.get('message'), dict):
                    reply = first['message'].get('content')
                else:
                    reply = first.get('text')
        except Exception:
            reply = None

        if not reply:
            reply = data.get('output') or data.get('generated_text') or data.get('text')

        if not reply and isinstance(data.get('results'), list) and len(data['results']) > 0:
            r0 = data['results'][0]
            if isinstance(r0, dict):
                reply = r0.get('output_text') or r0.get('content') or r0.get('text')
                if not reply and isinstance(r0.get('output'), dict):
                    reply = r0['output'].get('generated_text') or r0['output'].get('text')

        if not reply:
            logging.warning(f"Unexpected response format from LLM: {data}")
            reply = "I didn't get a response from the model."

        return {"reply": (reply or '').strip(), "raw": data, "meta": meta}

    except requests.exceptions.Timeout:
        logging.error("Upstream LLM request timed out")
        raise HTTPException(status_code=504, detail="Request to upstream LLM timed out")
    except requests.exceptions.RequestException as e:
        logging.exception("Upstream LLM request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Upstream LLM request failed: {str(e)}"
        )