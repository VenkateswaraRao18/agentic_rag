from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


def infer_bedrock_provider(model_id: str) -> str:
    mid = model_id.lower().strip()
    if mid.startswith("anthropic."):
        return "anthropic"
    if "titan-text" in mid or mid.startswith("amazon.titan-text"):
        return "amazon_titan"
    if mid.startswith("meta.llama"):
        return "meta_llama"
    if mid.startswith("mistral."):
        return "mistral"
    if mid.startswith("google.gemma"):
        return "google_gemma"
    return ""


def resolve_provider() -> str:
    explicit = (settings.bedrock_provider or "auto").strip().lower()
    if explicit not in ("", "auto"):
        return explicit
    guessed = infer_bedrock_provider(settings.bedrock_model_id)
    if guessed:
        return guessed
    raise ValueError(
        "Set BEDROCK_PROVIDER to one of: anthropic, amazon_titan, meta_llama, mistral, google_gemma "
        "(or use a model_id whose prefix is recognized). "
        "Inference profile ARNs require an explicit BEDROCK_PROVIDER."
    )


def _invoke(model_id: str, body: dict[str, Any]) -> dict[str, Any]:
    client = _bedrock_client()
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())


def _anthropic_body(user_message: str, system_prompt: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": settings.bedrock_max_tokens,
        "messages": [{"role": "user", "content": user_message}],
    }
    if system_prompt:
        body["system"] = system_prompt
    return body


def _anthropic_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in payload.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts).strip()


def _titan_body(system_prompt: str | None, user_message: str) -> dict[str, Any]:
    if system_prompt:
        input_text = f"User: {system_prompt}\n\n{user_message}\nBot:"
    else:
        input_text = f"User: {user_message}\nBot:"
    max_count = min(max(settings.bedrock_max_tokens, 1), 8192)
    return {
        "inputText": input_text,
        "textGenerationConfig": {
            "maxTokenCount": max_count,
            "stopSequences": [],
            "temperature": settings.bedrock_temperature,
            "topP": settings.bedrock_top_p,
        },
    }


def _titan_text(payload: dict[str, Any]) -> str:
    results = payload.get("results") or []
    if not results:
        return ""
    return str(results[0].get("outputText", "")).strip()


def _llama_prompt(system_prompt: str | None, user_message: str) -> str:
    # Official Llama 3 chat template (Amazon Bedrock docs).
    if system_prompt:
        return (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_message}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )
    return (
        f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_message}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def _llama_body(system_prompt: str | None, user_message: str) -> dict[str, Any]:
    max_len = min(max(settings.bedrock_max_tokens, 1), 2048)
    return {
        "prompt": _llama_prompt(system_prompt, user_message),
        "max_gen_len": max_len,
        "temperature": settings.bedrock_temperature,
        "top_p": settings.bedrock_top_p,
    }


def _llama_text(payload: dict[str, Any]) -> str:
    return str(payload.get("generation", "")).strip()


def _mistral_prompt(system_prompt: str | None, user_message: str) -> str:
    if system_prompt:
        blob = f"{system_prompt}\n\n{user_message}"
    else:
        blob = user_message
    return f"<s>[INST] {blob} [/INST]"


def _mistral_body(system_prompt: str | None, user_message: str) -> dict[str, Any]:
    max_tok = min(max(settings.bedrock_max_tokens, 1), 8192)
    return {
        "prompt": _mistral_prompt(system_prompt, user_message),
        "max_tokens": max_tok,
        "temperature": settings.bedrock_temperature,
        "top_p": settings.bedrock_top_p,
    }


def _mistral_text(payload: dict[str, Any]) -> str:
    outs = payload.get("outputs") or []
    if not outs:
        return ""
    return str(outs[0].get("text", "")).strip()


def _gemma_messages(system_prompt: str | None, user_message: str) -> list[dict[str, Any]]:
    if system_prompt:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    return [{"role": "user", "content": user_message}]


def _gemma_body(system_prompt: str | None, user_message: str) -> dict[str, Any]:
    # Amazon Bedrock InvokeModel for Gemma 3 — see model card sample code.
    max_tok = min(max(settings.bedrock_max_tokens, 1), 8192)
    body: dict[str, Any] = {
        "messages": _gemma_messages(system_prompt, user_message),
        "max_tokens": max_tok,
        "temperature": settings.bedrock_temperature,
        "top_p": settings.bedrock_top_p,
    }
    return body


def _gemma_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        ch0 = choices[0]
        if isinstance(ch0, dict):
            msg = ch0.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    texts: list[str] = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            texts.append(str(part.get("text", "")))
                    joined = "".join(texts).strip()
                    if joined:
                        return joined
            text = ch0.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    if payload.get("generation"):
        return str(payload["generation"]).strip()
    outs = payload.get("outputs") or []
    if outs and isinstance(outs[0], dict) and outs[0].get("text"):
        return str(outs[0]["text"]).strip()
    output = payload.get("output")
    if isinstance(output, dict):
        msg = output.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list) and content:
                block = content[0]
                if isinstance(block, dict) and "text" in block:
                    return str(block["text"]).strip()
    return ""


def invoke_bedrock(user_message: str, system_prompt: str | None = None) -> str:
    model_id = settings.bedrock_model_id
    provider = resolve_provider()

    if provider == "anthropic":
        payload = _invoke(model_id, _anthropic_body(user_message, system_prompt))
        text = _anthropic_text(payload)
    elif provider == "amazon_titan":
        payload = _invoke(model_id, _titan_body(system_prompt, user_message))
        text = _titan_text(payload)
    elif provider == "meta_llama":
        payload = _invoke(model_id, _llama_body(system_prompt, user_message))
        text = _llama_text(payload)
    elif provider == "mistral":
        payload = _invoke(model_id, _mistral_body(system_prompt, user_message))
        text = _mistral_text(payload)
    elif provider == "google_gemma":
        payload = _invoke(model_id, _gemma_body(system_prompt, user_message))
        text = _gemma_text(payload)
    else:
        raise ValueError(f"Unsupported BEDROCK_PROVIDER: {provider}")

    if not text:
        raise ValueError("Empty Bedrock model output")
    return text


def try_bedrock(user_message: str, system_prompt: str | None = None) -> str | None:
    try:
        return invoke_bedrock(user_message, system_prompt=system_prompt)
    except (ClientError, BotoCoreError, ValueError, json.JSONDecodeError) as e:
        logger.warning("Bedrock call failed, using fallback composer: %s", e)
        return None
