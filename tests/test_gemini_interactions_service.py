import unittest
from unittest.mock import MagicMock, patch

from api.app.services.gemini_interactions_service import GeminiInteractionRequest, create_text_interaction


class GeminiInteractionsServiceTest(unittest.TestCase):
    def test_private_default_uses_store_false(self):
        fake_interaction = MagicMock()
        fake_interaction.id = "interaction_1"
        fake_interaction.output_text = "hello"
        fake_interaction.model_dump.return_value = {"id": "interaction_1", "output_text": "hello"}
        fake_client = MagicMock()
        fake_client.interactions.create.return_value = fake_interaction

        with patch("api.app.services.gemini_interactions_service.genai.Client", return_value=fake_client):
            result = create_text_interaction(
                GeminiInteractionRequest(
                    input="hello",
                    model="gemini-2.5-flash",
                    system_instruction="Be concise.",
                )
            )

        fake_client.interactions.create.assert_called_once()
        kwargs = fake_client.interactions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-2.5-flash")
        self.assertEqual(kwargs["input"], "hello")
        self.assertFalse(kwargs["store"])
        self.assertNotIn("background", kwargs)
        self.assertEqual(result["output_text"], "hello")

    def test_rejects_background_when_store_false(self):
        with self.assertRaises(ValueError):
            create_text_interaction(
                GeminiInteractionRequest(
                    input="private JD",
                    background=True,
                    store=False,
                )
            )


if __name__ == "__main__":
    unittest.main()
