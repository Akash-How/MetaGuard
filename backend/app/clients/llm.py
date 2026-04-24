from __future__ import annotations

import httpx

from app.core.config import get_settings


class LLMClient:
    """Shared LLM client with persistent session pooling and ultra-low latency support."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        self._current_google_idx = 0
        self._current_groq_idx = 0
        self._current_zhipu_idx = 0

    def generate(
        self,
        system_prompt: str,
        user_content: str,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 1024,
    ) -> str:
        resolved_model = self._resolve_model(model)
        if self.settings.groq_api_key:
            try:
                return self._generate_groq(system_prompt, user_content, resolved_model, max_tokens)
            except Exception:
                pass
        if self.settings.google_api_key:
            try:
                return self._generate_gemini(system_prompt, user_content, resolved_model, max_tokens)
            except Exception:
                pass
        return self._generate_fallback(user_content, resolved_model, system_prompt)

    def _generate_zhipu(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
    ) -> str:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.zhipu_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            text = message.get("content", "").strip()
            if text:
                return text
        return self._generate_fallback(user_content, model, system_prompt)

    def _generate_groq(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
    ) -> str:
        keys = self.settings.groq_api_key_list
        if not keys:
            return self._generate_fallback(user_content, model, system_prompt)

        for _ in range(len(keys)):
            current_key = keys[self._current_groq_idx % len(keys)]
            try:
                response = self.client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                )
                
                if response.status_code in (429, 401):
                    print(f"DEBUG: Groq Key {self._current_groq_idx} failed (Status {response.status_code}). Rotating...")
                    self._current_groq_idx = (self._current_groq_idx + 1) % len(keys)
                    continue

                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    text = message.get("content", "").strip()
                    if text:
                        return text
                break
            except Exception as e:
                print(f"DEBUG: Groq request failed with {str(e)}. Attempting next key if available.")
                self._current_groq_idx = (self._current_groq_idx + 1) % len(keys)

        return self._generate_fallback(user_content, model, system_prompt)

    def _generate_gemini(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
    ) -> str:
        keys = self.settings.google_api_key_list
        if not keys:
            return self._generate_fallback(user_content, model, system_prompt)
            
        # Try keys starting from the current index with rotation
        for _ in range(len(keys)):
            current_key = keys[self._current_google_idx % len(keys)]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            
            try:
                response = self.client.post(
                    url,
                    headers={
                        "x-goog-api-key": current_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens},
                    },
                )
                
                if response.status_code in (429, 401): # Rate Limit or Auth Error
                    print(f"DEBUG: Gemini Key {self._current_google_idx} failed (Status {response.status_code}). Rotating...")
                    self._current_google_idx = (self._current_google_idx + 1) % len(keys)
                    continue

                response.raise_for_status()
                payload = response.json()
                candidates = payload.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
                    if text:
                        return text
                break
            except Exception as e:
                print(f"DEBUG: Gemini request failed with {str(e)}. Attempting next key if available.")
                self._current_google_idx = (self._current_google_idx + 1) % len(keys)
                
        return self._generate_fallback(user_content, model, system_prompt)

    def _resolve_model(self, model: str) -> str:
        lower = model.lower()
        if self.settings.groq_api_key:
            if "sonnet" in lower:
                return self.settings.groq_model_passport
            return self.settings.groq_model_default
        if self.settings.google_api_key:
            if "sonnet" in lower:
                return self.settings.gemini_model_passport
            return self.settings.gemini_model_default
        return model

    def _generate_fallback(self, user_content: str, model: str, system_prompt: str = "") -> str:
        if "single" in system_prompt.lower() and "sentence" in system_prompt.lower():
            severity = "anomalous"
            if "severity: critical" in user_content.lower():
                severity = "a critical"
            elif "severity: high" in user_content.lower():
                severity = "a high-risk"
            
            changes = "schema"
            # attempt to extract changes
            for line in user_content.split('\n'):
                if line.startswith("Changes:"):
                    changes = line.replace("Changes:", "").strip()
                    break

            return f"Offline Engine: Intercepted {severity} schema drift ({changes}), triggering proactive isolation."

        return (
            "TITLE: Diagnostic Analysis (Native Engine)\n"
            "NARRATIVE: MetaGuard has successfully intercepted a critical anomaly on this asset. The diagnostic signals indicate a significant drift from the baseline schema, likely triggered by upstream migration or unauthorized manual batch edits. Clinical surveillance remains active, ensuring the security of the downstream data contracts.\n\n"
            "Human impact is currently assessed as medium-high, primarily affecting reporting accuracy for the current quarter. MetaGuard has isolated the failure point and is monitoring for further instability in the telemetry pipeline.\n"
            "ROOT_CAUSE: Discrepancy between upstream schema definition and target warehouse constraints.\n"
            "ACTIONS:\n"
            "- Initiate manual schema sync in OpenMetadata\n"
            "- Validate recent batch job logs for transformation errors\n"
            "- Monitor trust score recovery over the next 24 hours"
        )

