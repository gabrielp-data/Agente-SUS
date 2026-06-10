"""AWS Bedrock integration — supports API Key auth and boto3 auth."""
from __future__ import annotations

import time
from typing import Any

import requests

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger("bedrock_service")


class CredentialsExpiredError(Exception):
    """Raised when Bedrock returns 401/403."""


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

        Args:
            messages:    List of {"role": "user"|"assistant", "content": [{"text": str}]}
            system:      System prompt text
            model_id:    Override model (default: settings.bedrock_model_id)
            max_tokens:  Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            (response_text, usage_dict)
            usage_dict keys: input_tokens, output_tokens, latency_ms
        """
        model = model_id or self.settings.bedrock_model_id
        t0 = time.monotonic()

        # Sempre usar boto3 — suporta tanto API Key (AWS_BEARER_TOKEN_BEDROCK)
        # quanto credenciais AWS completas.
        text, usage = self._invoke_with_boto3(messages, system, model, max_tokens, temperature)

        usage["latency_ms"] = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Bedrock call — model=%s tokens_in=%d tokens_out=%d latency=%dms",
            model,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            usage["latency_ms"],
        )
        return text, usage

    def test_connection(self) -> tuple[bool, str]:
        """
        Testa conectividade com Bedrock.
        Tenta 2 estratégias:
          1) boto3 com AWS_BEARER_TOKEN_BEDROCK (recomendado pela AWS)
          2) HTTP direto com Authorization: Bearer (fallback)
        Inclui diagnósticos detalhados para facilitar debug.
        """
        import os
        self.settings.reload()

        api_key  = self.settings.bedrock_api_key
        region   = self.settings.aws_region
        model_id = self.settings.bedrock_model_id
        endpoint = self.settings.bedrock_endpoint.rstrip("/")

        # Diagnóstico inicial
        key_preview = f"{api_key[:20]}...{api_key[-6:]}" if len(api_key) > 26 else api_key
        diag = (
            f"🔍 **Diagnóstico**\n"
            f"- Chave: `{key_preview}` ({len(api_key)} chars)\n"
            f"- Região: `{region}`\n"
            f"- Modelo: `{model_id}`\n"
            f"- Endpoint: `{endpoint}`\n\n"
        )

        if not api_key or api_key == "bedrock-api-key-XXXXXXXXXXXXXXXX" or "XXXX" in api_key:
            return False, (
                diag +
                "❌ **Chave inválida ou placeholder detectado.**\n"
                "Abra ⚙️ Configurações, cole a chave real no campo API Key e clique **Salvar**."
            )

        # ── Tentativa 1: boto3 com bearer token ──────────────────────────────
        boto3_error = ""
        try:
            import boto3
            import botocore.exceptions

            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key
            os.environ["AWS_DEFAULT_REGION"] = region

            client = boto3.client("bedrock-runtime", region_name=region)
            resp = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": "OK"}]}],
                inferenceConfig={"maxTokens": 10},
            )
            text = resp["output"]["message"]["content"][0]["text"]
            return True, (
                diag +
                f"✅ **Conectado via boto3!**\n"
                f"Modelo: **{model_id}** | Resposta: `{text.strip()}`"
            )
        except Exception as exc:
            boto3_error = str(exc)

        # ── Tentativa 2: HTTP direto ──────────────────────────────────────────
        body = {
            "system": [{"text": "Responda somente: OK"}],
            "messages": [{"role": "user", "content": [{"text": "OK"}]}],
            "inferenceConfig": {"maxTokens": 10, "temperature": 0},
        }
        for model in [model_id, "us.anthropic.claude-haiku-4-5-20251001-v1:0", "us.amazon.nova-lite-v1:0"]:
            url = f"{endpoint}/model/{model}/converse"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=30)
                if resp.status_code == 200:
                    text = resp.json()["output"]["message"]["content"][0]["text"]
                    return True, (
                        diag +
                        f"✅ **Conectado via HTTP!**\n"
                        f"Modelo: **{model}** | Resposta: `{text.strip()}`"
                    )
                else:
                    boto3_error += f"\nHTTP [{model}] {resp.status_code}: {resp.text[:300]}"
            except Exception as exc:
                boto3_error += f"\nHTTP [{model}] erro: {exc}"

        return False, diag + f"❌ Todas as tentativas falharam:\n```\n{boto3_error}\n```"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_body(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        return {
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

    def _parse_response(self, data: dict) -> tuple[str, dict]:
        text = data["output"]["message"]["content"][0]["text"]
        usage_raw = data.get("usage", {})
        usage = {
            "input_tokens": usage_raw.get("inputTokens", 0),
            "output_tokens": usage_raw.get("outputTokens", 0),
        }
        return text, usage

    def _invoke_with_api_key(
        self,
        messages: list[dict],
        system: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        url = (
            f"{self.settings.bedrock_endpoint.rstrip('/')}"
            f"/model/{model_id}/converse"
        )
        # AWS Bedrock API keys usam Authorization: Bearer (AWS_BEARER_TOKEN_BEDROCK)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.bedrock_api_key}",
        }
        body = self._build_body(messages, system, max_tokens, temperature)

        resp = requests.post(url, headers=headers, json=body, timeout=120)

        if resp.status_code in (401, 403):
            raise CredentialsExpiredError(
                "Suas credenciais AWS Bedrock expiraram. "
                "Atualize-as na página ⚙️ Configurações."
            )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def _invoke_with_boto3(
        self,
        messages: list[dict],
        system: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        import os
        try:
            import boto3
            import botocore.exceptions
        except ImportError as exc:
            raise RuntimeError("boto3 não instalado. Execute: pip install boto3") from exc

        # Injeta API key como bearer token se disponível
        if self.settings.use_api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = self.settings.bedrock_api_key
            os.environ["AWS_DEFAULT_REGION"] = self.settings.aws_region
            client = boto3.client("bedrock-runtime", region_name=self.settings.aws_region)
        else:
            session = boto3.Session(
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                aws_session_token=self.settings.aws_session_token,
                region_name=self.settings.aws_region,
            )
            client = session.client("bedrock-runtime")

        body = self._build_body(messages, system, max_tokens, temperature)
        try:
            resp = client.converse(
                modelId=model_id,
                system=body["system"],
                messages=body["messages"],
                inferenceConfig=body["inferenceConfig"],
            )
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("ExpiredTokenException", "InvalidSignatureException",
                        "UnrecognizedClientException", "AccessDeniedException"):
                raise CredentialsExpiredError(
                    "Suas credenciais AWS Bedrock expiraram ou são inválidas. "
                    "Gere uma nova chave em AWS Console → Bedrock → API Keys e "
                    "atualize em ⚙️ Configurações."
                ) from exc
            raise

        text = resp["output"]["message"]["content"][0]["text"]
        usage = {
            "input_tokens": resp.get("usage", {}).get("inputTokens", 0),
            "output_tokens": resp.get("usage", {}).get("outputTokens", 0),
        }
        return text, usage
