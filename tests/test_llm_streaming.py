from __future__ import annotations

import json
import unittest

import httpx

from performance_planning_qa.config import LLMSettings
from performance_planning_qa.llm import LiteLLMClient


class GLMStreamingTests(unittest.TestCase):
    def test_streams_reasoning_and_collects_answer_content(self) -> None:
        stream_body = "\n\n".join(
            [
                'data: {"choices":[{"delta":{"reasoning_content":"Plan"}}]}',
                'data: {"choices":[{"delta":{"reasoning_content":" first."}}]}',
                'data: {"choices":[{"delta":{"content":"{\\"answer\\":"}}]}',
                'data: {"choices":[{"delta":{"content":"\\"done\\"}"}}]}',
                "data: [DONE]",
            ]
        )

        def handle_request(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertTrue(payload["stream"])
            return httpx.Response(200, text=stream_body, request=request)

        settings = LLMSettings(
            provider="glm",
            endpoint="https://llm.example/chat/completions",
            model="GLM-5.2",
            api_key="test-key",
            verify_ssl=False,
            stream=True,
            timeout_seconds=30.0,
            max_retries=0,
            retry_backoff_seconds=0.0,
            sql_temperature=0.0,
            answer_temperature=0.2,
            sql_max_tokens=100,
            answer_max_tokens=100,
        )
        client = LiteLLMClient(settings)
        client._client = httpx.Client(transport=httpx.MockTransport(handle_request))
        reasoning_parts: list[str] = []

        try:
            content = client.complete(
                [{"role": "user", "content": "test"}],
                temperature=0.0,
                max_tokens=100,
                reasoning_callback=reasoning_parts.append,
            )
        finally:
            client.close()

        self.assertEqual("".join(reasoning_parts), "Plan first.")
        self.assertEqual(content, '{"answer":"done"}')


if __name__ == "__main__":
    unittest.main()
