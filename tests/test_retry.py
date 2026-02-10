"""Tests for retry logic in sticker generation."""

import sys
from unittest.mock import MagicMock, call, patch

import pytest
from PIL import Image

from sticker_generator.cli import main
from sticker_generator.core import generate_sticker


def _make_mock_response(has_image: bool = True) -> MagicMock:
    """Create a mock Gemini API response."""
    response = MagicMock()
    if has_image:
        part = MagicMock()
        part.inline_data = MagicMock()
        part.inline_data.mime_type = "image/png"
        # Create a minimal valid PNG in memory
        img = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        part.inline_data.data = buf.getvalue()
        part.text = None
        response.candidates = [MagicMock()]
        response.candidates[0].content.parts = [part]
    else:
        # Response with text only, no image
        part = MagicMock()
        part.inline_data = None
        part.text = "I cannot generate that image"
        response.candidates = [MagicMock()]
        response.candidates[0].content.parts = [part]
    return response


def _make_empty_response() -> MagicMock:
    """Create a mock Gemini API response with no candidates."""
    response = MagicMock()
    response.candidates = []
    return response


class TestGenerateStickerRetryParams:
    """Test that generate_sticker accepts and uses retry parameters."""

    @patch("sticker_generator.core.genai.Client")
    @patch("sticker_generator.core.genai.types.HttpOptions")
    @patch("sticker_generator.core.genai.types.HttpRetryOptions")
    def test_default_retry_params(
        self, mock_retry_opts_cls, mock_http_opts_cls, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response()

        generate_sticker("test prompt")

        # Verify HttpRetryOptions was configured with defaults
        mock_retry_opts_cls.assert_called_once_with(
            attempts=4,  # max_retries(3) + 1
            initial_delay=1.0,
            max_delay=8.0,  # 1.0 * 2^3
            exp_base=2,
            jitter=1.0,
        )

    @patch("sticker_generator.core.genai.Client")
    @patch("sticker_generator.core.genai.types.HttpOptions")
    @patch("sticker_generator.core.genai.types.HttpRetryOptions")
    def test_custom_retry_params(
        self, mock_retry_opts_cls, mock_http_opts_cls, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response()

        generate_sticker("test prompt", max_retries=5, retry_delay=2.0)

        mock_retry_opts_cls.assert_called_once_with(
            attempts=6,  # max_retries(5) + 1
            initial_delay=2.0,
            max_delay=64.0,  # 2.0 * 2^5
            exp_base=2,
            jitter=2.0,
        )

    @patch("sticker_generator.core.genai.Client")
    @patch("sticker_generator.core.genai.types.HttpOptions")
    @patch("sticker_generator.core.genai.types.HttpRetryOptions")
    def test_zero_retries(
        self, mock_retry_opts_cls, mock_http_opts_cls, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response()

        generate_sticker("test prompt", max_retries=0)

        mock_retry_opts_cls.assert_called_once_with(
            attempts=1,  # No retries
            initial_delay=1.0,
            max_delay=1.0,  # 1.0 * 2^0
            exp_base=2,
            jitter=1.0,
        )

    @patch("sticker_generator.core.genai.Client")
    @patch("sticker_generator.core.genai.types.HttpOptions")
    @patch("sticker_generator.core.genai.types.HttpRetryOptions")
    def test_api_key_with_retry_options(
        self, mock_retry_opts_cls, mock_http_opts_cls, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response()

        generate_sticker("test prompt", api_key="test-key", max_retries=2)

        client_call = mock_client_cls.call_args
        assert client_call[1]["api_key"] == "test-key"
        assert "http_options" in client_call[1]


class TestGenerateStickerNoImageRetry:
    """Test application-level retry when API returns no image."""

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_retries_on_no_image_then_succeeds(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # First two calls return no image, third succeeds
        mock_client.models.generate_content.side_effect = [
            _make_mock_response(has_image=False),
            _make_mock_response(has_image=False),
            _make_mock_response(has_image=True),
        ]

        result = generate_sticker("test prompt", max_retries=3, retry_delay=1.0)

        assert result is not None
        assert mock_client.models.generate_content.call_count == 3
        # Should have slept twice (after attempt 0 and 1)
        assert mock_sleep.call_count == 2

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_exponential_backoff_delays(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.models.generate_content.side_effect = [
            _make_empty_response(),
            _make_empty_response(),
            _make_mock_response(has_image=True),
        ]

        generate_sticker("test prompt", max_retries=3, retry_delay=1.0)

        # Verify exponential backoff: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_custom_retry_delay_backoff(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.models.generate_content.side_effect = [
            _make_empty_response(),
            _make_empty_response(),
            _make_empty_response(),
            _make_mock_response(has_image=True),
        ]

        generate_sticker("test prompt", max_retries=3, retry_delay=0.5)

        # Delays: 0.5 * 2^0 = 0.5, 0.5 * 2^1 = 1.0, 0.5 * 2^2 = 2.0
        assert mock_sleep.call_args_list == [call(0.5), call(1.0), call(2.0)]

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_raises_after_all_retries_exhausted(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # All attempts return no image
        mock_client.models.generate_content.return_value = _make_mock_response(
            has_image=False
        )

        with pytest.raises(ValueError, match="No image was generated after 3"):
            generate_sticker("test prompt", max_retries=2, retry_delay=0.1)

        # Should have tried 3 times total (1 initial + 2 retries)
        assert mock_client.models.generate_content.call_count == 3

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_raises_after_zero_retries(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_empty_response()

        with pytest.raises(ValueError, match="No image was generated after 1"):
            generate_sticker("test prompt", max_retries=0, retry_delay=0.1)

        assert mock_client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

    @patch("sticker_generator.core.genai.Client")
    def test_succeeds_on_first_attempt_no_retry(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_mock_response()

        result = generate_sticker("test prompt", max_retries=3)

        assert result is not None
        assert mock_client.models.generate_content.call_count == 1

    @patch("sticker_generator.core.time.sleep")
    @patch("sticker_generator.core.genai.Client")
    def test_retry_prints_progress(self, mock_client_cls, mock_sleep, capsys):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.models.generate_content.side_effect = [
            _make_empty_response(),
            _make_mock_response(has_image=True),
        ]

        generate_sticker("test prompt", max_retries=2, retry_delay=0.1)

        captured = capsys.readouterr()
        assert "No image in response, retrying (1/2)" in captured.out


class TestCreateStickerRetryPassthrough:
    """Test that create_sticker passes retry params to generate_sticker."""

    @patch("sticker_generator.core.generate_sticker")
    @patch("sticker_generator.core.remove_green_screen_hsv")
    @patch("sticker_generator.core.remove_green_screen_aggressive")
    @patch("sticker_generator.core.cleanup_edges")
    def test_default_retry_params_passed(
        self, mock_cleanup, mock_agg, mock_hsv, mock_gen
    ):
        from sticker_generator.core import create_sticker

        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        mock_gen.return_value = img
        mock_hsv.return_value = img
        mock_agg.return_value = img
        mock_cleanup.return_value = img

        create_sticker("test prompt")

        mock_gen.assert_called_once()
        kwargs = mock_gen.call_args[1]
        assert kwargs["max_retries"] == 3
        assert kwargs["retry_delay"] == 1.0

    @patch("sticker_generator.core.generate_sticker")
    @patch("sticker_generator.core.remove_green_screen_hsv")
    @patch("sticker_generator.core.remove_green_screen_aggressive")
    @patch("sticker_generator.core.cleanup_edges")
    def test_custom_retry_params_passed(
        self, mock_cleanup, mock_agg, mock_hsv, mock_gen
    ):
        from sticker_generator.core import create_sticker

        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        mock_gen.return_value = img
        mock_hsv.return_value = img
        mock_agg.return_value = img
        mock_cleanup.return_value = img

        create_sticker("test prompt", max_retries=5, retry_delay=2.0)

        kwargs = mock_gen.call_args[1]
        assert kwargs["max_retries"] == 5
        assert kwargs["retry_delay"] == 2.0


class TestSheetRetryPassthrough:
    """Test that sheet generation passes retry params to create_sticker."""

    @patch("sticker_generator.sheet.create_sticker")
    def test_default_retry_params_forwarded(self, mock_create):
        from sticker_generator.sheet import generate_sticker_sheet

        mock_create.return_value = Image.new("RGBA", (100, 100))

        generate_sticker_sheet(
            "test",
            variations=1,
            delay_between_requests=0,
        )

        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 3
        assert kwargs["retry_delay"] == 1.0

    @patch("sticker_generator.sheet.create_sticker")
    def test_custom_retry_params_forwarded(self, mock_create):
        from sticker_generator.sheet import generate_sticker_sheet

        mock_create.return_value = Image.new("RGBA", (100, 100))

        generate_sticker_sheet(
            "test",
            variations=1,
            sticker_max_retries=5,
            sticker_retry_delay=2.0,
            delay_between_requests=0,
        )

        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 5
        assert kwargs["retry_delay"] == 2.0


class TestCLIRetryFlags:
    """Test CLI retry flags."""

    @patch("sticker_generator.cli.create_sticker")
    def test_default_retry_flags(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 3
        assert kwargs["retry_delay"] == 1.0

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_max_retries(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--max-retries", "5"]):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 5

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_retry_delay(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--retry-delay", "2.5"]):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["retry_delay"] == 2.5

    @patch("sticker_generator.cli.create_sticker")
    def test_zero_retries_flag(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--max-retries", "0"]):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 0

    def test_negative_max_retries_rejected(self, capsys):
        with patch.object(sys, "argv", ["prog", "test prompt", "--max-retries", "-1"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "--max-retries must be non-negative" in captured.err

    def test_negative_retry_delay_rejected(self, capsys):
        with patch.object(
            sys, "argv", ["prog", "test prompt", "--retry-delay", "-0.5"]
        ):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "--retry-delay must be non-negative" in captured.err

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_retry_flags_passed_to_sheet(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "test prompt",
                "-n",
                "2",
                "--sheet",
                "--max-retries",
                "5",
                "--retry-delay",
                "2.0",
            ],
        ):
            result = main()

        assert result == 0
        kwargs = mock_sheet.call_args[1]
        assert kwargs["sticker_max_retries"] == 5
        assert kwargs["sticker_retry_delay"] == 2.0

    @patch("sticker_generator.cli.create_sticker")
    def test_both_retry_flags_together(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "test prompt",
                "--max-retries",
                "7",
                "--retry-delay",
                "0.5",
            ],
        ):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["max_retries"] == 7
        assert kwargs["retry_delay"] == 0.5
