"""AWS Bedrock integration — boto3 com API key (bearer) ou credenciais AWS."""
from __future__ import annotations

import os
import threading
import time

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger("bedrock_service")

# Cliente boto3 cacheado (criar um por chamada custa ~100ms)
_client = None
_client_key: tuple | None = None
_client_lock = threading.Lock()


class CredentialsExpiredError(Exception):
    """Raised when Bedrock rejects the credentials (expired/invalid key)."""


def _get_client(settings):
    """Retorna o cliente bedrock-runtime, recriando se a credencial mudou."""
    global _client, _client_key
    import boto3

    key = (settings.bedrock_api_key, settings.aws_region,
           settings.aws_access_key_id, settings.aws_session_token)
    with _client_lock:
        if _client is None or _client_key != key:
            if settings.use_api_key:
                os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.bedrock_api_key
                os.environ["AWS_DEFAULT_REGION"] = settings.aws_region
                _client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
            else:
                session = boto3.Session(
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    aws_session_token=settings.aws_session_token,
                    region_name=settings.aws_region,
                )
                _client = session.client("bedrock-runtime")
            _client_key = key
    return _client


def _raise_if_credentials(exc) -> None:
    """Converte erros de autenticação do boto3 em CredentialsExpiredError."""
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
    if code in ("ExpiredTokenException", "InvalidSignatureException",
                "UnrecognizedClientException", "AccessDeniedException"):
        raise CredentialsExpiredError(
            "Suas credenciais AWS Bedrock expiraram ou são inválidas. "
            "Gere uma nova chave em AWS Console → Bedrock → API Keys e "
            "atualize em ⚙️ Configurações."
        ) from exc


class BedrockService:
    """Wrapper around the Bedrock Converse API."""

    def __init__(self) -> None:
        self.settings = get_settings()

    # ── Public interface ──────────────────────────────────────────────────────

    def invoke(
        self,
        messages: list[dict],
        system: str,
        model_id: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> tuple[str, dict]:
        """
        Call the Bedrock Converse API.

        Returns:
            (response_text, usage_dict) — usage: input_tokens, output_tokens, latency_ms
        """
        import botocore.exceptions

        model = model_id or self.settings.bedrock_model_id
        t0 = time.monotonic()
        client = _get_client(self.settings)

        try:
            resp = client.converse(
                modelId=model,
                system=[{"text": system}],
                messages=messages,
                inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            )
        except botocore.exceptions.ClientError as exc:
            _raise_if_credentials(exc)
            raise

        text = resp["output"]["message"]["content"][0]["text"]
        usage = {
            "input_tokens": resp.get("usage", {}).get("inputTokens", 0),
            "output_tokens": resp.get("usage", {}).get("outputTokens", 0),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
        logger.info(
            "Bedrock call — model=%s tokens_in=%d tokens_out=%d latency=%dms",
            model, usage["input_tokens"], usage["output_tokens"], usage["latency_ms"],
        )
        return text, usage

    def test_connection(self) -> tuple[bool, str]:
        """Testa conectividade com diagnóstico detalhado."""
        self.settings.reload()
        api_key = self.settings.bedrock_api_key
        region = self.settings.aws_region
        model_id = self.settings.bedrock_model_id

        key_preview = f"{api_key[:20]}...{api_key[-6:]}" if len(api_key) > 26 else api_key
        diag = (
            f"🔍 **Diagnóstico**\n"
            f"- Chave: `{key_preview}` ({len(api_key)} chars)\n"
            f"- Região: `{region}` | Modelo: `{model_id}`\n\n"
        )

        if not api_key or "XXXX" in api_key:
            return False, (
                diag + "❌ **Chave inválida ou placeholder.** "
                "Cole a chave real no campo acima e clique Salvar."
            )

        try:
            text, _ = self.invoke(
                [{"role": "user", "content": [{"text": "OK"}]}],
                system="Responda somente: OK", max_tokens=10,
            )
            return True, diag + f"✅ **Conectado!** Resposta: `{text.strip()}`"
        except CredentialsExpiredError as exc:
            return False, diag + f"❌ {exc}"
        except Exception as exc:
            return False, diag + f"❌ Erro: {exc}"
