import os
import unittest
from unittest.mock import Mock, patch

import httpx
from groq import APITimeoutError, AuthenticationError, BadRequestError, RateLimitError

from app.services.llm_service import LLMServiceError, generate_repository_answer


class TestLLMService(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {
                "file_path": "auth.py",
                "chunk_type": "function",
                "symbol_name": "authenticate_user",
                "start_line": 1,
                "end_line": 3,
                "content": "def authenticate_user():\n    return True",
            }
        ]

    def test_empty_retrieval_does_not_require_groq_credentials(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            answer = generate_repository_answer("Explain this code", [])

        self.assertIn("could not find relevant code", answer)

    def test_missing_api_key_has_configuration_error(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": ""}):
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "groq_configuration_missing")
        self.assertEqual(raised.exception.status_code, 503)

    def test_answer_prompt_requires_clear_markdown_and_grounded_citations(self):
        client = Mock()
        client.chat.completions.create.return_value.choices = [
            Mock(message=Mock(content="This function authenticates a user [SOURCE 1]."))
        ]

        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"}), patch(
            "app.services.llm_service.Groq",
            return_value=client,
        ):
            generate_repository_answer("Explain this code", self.chunks)

        system_prompt = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("short opening", system_prompt)
        self.assertIn("descriptive Markdown headings", system_prompt)
        self.assertIn("tables only for genuine comparisons", system_prompt)
        self.assertIn("exact [SOURCE N] identifier", system_prompt)
        self.assertIn("Do not invent file paths, line numbers", system_prompt)
        self.assertIn("retrieved context is insufficient", system_prompt)

    def test_gemini_provider_uses_grounded_prompt_and_configured_model(self):
        response = Mock(text="This function authenticates a user [SOURCE 1].")
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-gemini-key",
                "GEMINI_MODEL": "gemini-test-model",
            },
        ), patch("google.genai.Client") as gemini_factory, patch(
            "app.services.llm_service.Groq"
        ) as groq_factory:
            gemini_factory.return_value.models.generate_content.return_value = response
            answer = generate_repository_answer("Explain this code", self.chunks)

        self.assertIn("[SOURCE 1]", answer)
        gemini_factory.assert_called_once()
        self.assertEqual(
            gemini_factory.call_args.kwargs["api_key"],
            "test-gemini-key",
        )
        self.assertEqual(
            gemini_factory.call_args.kwargs["http_options"].timeout,
            30_000,
        )
        request = gemini_factory.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(request["model"], "gemini-test-model")
        self.assertIn("Retrieved repository code", request["contents"])
        self.assertIn("Do not invent file paths", request["config"]["system_instruction"])
        groq_factory.assert_not_called()

    def test_gemini_is_default_when_provider_is_not_selected(self):
        response = Mock(text="Grounded response [SOURCE 1].")
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-gemini-key"},
            clear=True,
        ), patch("google.genai.Client") as gemini_factory:
            gemini_factory.return_value.models.generate_content.return_value = response
            answer = generate_repository_answer("Explain this code", self.chunks)

        self.assertIn("[SOURCE 1]", answer)
        request = gemini_factory.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(request["model"], "gemini-2.5-flash")

    def test_gemini_provider_requires_its_own_api_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": ""}):
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "gemini_configuration_missing")
        self.assertEqual(raised.exception.status_code, 503)

    def test_gemini_rate_limit_is_reported_without_revealing_provider_details(self):
        from google.genai.errors import APIError

        provider_error = APIError(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED", "message": "Rate limit reached"}},
        )
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"},
        ), patch("google.genai.Client") as gemini_factory:
            gemini_factory.return_value.models.generate_content.side_effect = provider_error
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "gemini_rate_limited")
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIs(raised.exception.__cause__, provider_error)

    def test_authentication_error_is_actionable_and_preserves_cause(self):
        response = httpx.Response(
            401,
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        )
        provider_error = AuthenticationError(
            "Invalid API Key",
            response=response,
            body={"error": {"code": "invalid_api_key"}},
        )
        client = Mock()
        client.chat.completions.create.side_effect = provider_error

        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key-not-logged"}), patch(
            "app.services.llm_service.Groq",
            return_value=client,
        ) as groq_factory:
            with self.assertLogs("app.services.llm_service", level="WARNING") as logs:
                with self.assertRaises(LLMServiceError) as raised:
                    generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "groq_authentication_failed")
        self.assertIn("process-level GROQ_API_KEY overrides", raised.exception.message)
        self.assertIs(raised.exception.__cause__, provider_error)
        self.assertEqual(groq_factory.call_args.kwargs["max_retries"], 0)
        self.assertNotIn("test-key-not-logged", "\n".join(logs.output))

    def test_rate_limit_error_is_not_retried_or_misreported_as_auth_failure(self):
        response = httpx.Response(
            429,
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        )
        provider_error = RateLimitError(
            "Rate limit reached",
            response=response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        client = Mock()
        client.chat.completions.create.side_effect = provider_error

        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"}), patch(
            "app.services.llm_service.Groq",
            return_value=client,
        ):
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "groq_rate_limited")
        self.assertEqual(raised.exception.status_code, 429)
        client.chat.completions.create.assert_called_once()

    def test_model_error_is_reported_without_switching_models(self):
        response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        )
        provider_error = BadRequestError(
            "Model unavailable",
            response=response,
            body={"error": {"code": "model_not_found", "message": "Model not found"}},
        )
        client = Mock()
        client.chat.completions.create.side_effect = provider_error

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"},
        ), patch("app.services.llm_service.Groq", return_value=client) as groq_factory:
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "groq_model_unavailable")
        self.assertEqual(groq_factory.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["model"],
            "openai/gpt-oss-120b",
        )

    def test_timeout_is_reported_as_gateway_timeout_without_retry(self):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        provider_error = APITimeoutError(request=request)
        client = Mock()
        client.chat.completions.create.side_effect = provider_error

        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"}), patch(
            "app.services.llm_service.Groq",
            return_value=client,
        ):
            with self.assertRaises(LLMServiceError) as raised:
                generate_repository_answer("Explain this code", self.chunks)

        self.assertEqual(raised.exception.code, "groq_timeout")
        self.assertEqual(raised.exception.status_code, 504)
        client.chat.completions.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
