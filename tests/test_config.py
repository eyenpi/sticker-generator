"""Tests for TOML configuration file support."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sticker_generator.config import (
    ConfigError,
    StickerConfig,
    _parse_resize_value,
    find_config_files,
    format_config_for_display,
    format_config_paths,
    generate_config_template,
    get_config_paths,
    load_config,
    load_config_file,
    merge_configs,
)


class TestStickerConfig:
    """Tests for StickerConfig dataclass."""

    def test_all_fields_default_to_none(self):
        config = StickerConfig()
        assert config.api_key is None
        assert config.style is None
        assert config.output_format is None
        assert config.quality is None
        assert config.lossless is None
        assert config.hue_center is None
        assert config.hue_range is None
        assert config.min_saturation is None
        assert config.min_value is None
        assert config.green_threshold is None
        assert config.edge_threshold is None
        assert config.resize is None
        assert config.resize_exact is None
        assert config.max_retries is None
        assert config.retry_delay is None
        assert config.delay is None
        assert config.max_workers is None
        assert config.strict is None
        assert config.variations is None
        assert config.columns is None
        assert config.padding is None
        assert config.aspect_ratio is None
        assert config.save_raw is None
        assert config.save_intermediates is None

    def test_fields_are_settable(self):
        config = StickerConfig(style="kawaii", quality=90)
        assert config.style == "kawaii"
        assert config.quality == 90

    def test_mutable(self):
        config = StickerConfig()
        config.style = "minimal"
        assert config.style == "minimal"


class TestConfigPaths:
    """Tests for config path discovery."""

    def test_get_config_paths_returns_two_paths(self):
        paths = get_config_paths()
        assert len(paths) == 2

    def test_get_config_paths_home_first_cwd_second(self):
        paths = get_config_paths()
        # Home config is lower priority (first), CWD is higher (second)
        assert "config.toml" in str(paths[0])
        assert ".sticker-generator.toml" in str(paths[1])

    def test_home_config_path(self):
        paths = get_config_paths()
        expected = Path.home() / ".config" / "sticker-generator" / "config.toml"
        assert paths[0] == expected

    def test_cwd_config_path(self):
        paths = get_config_paths()
        expected = Path.cwd() / ".sticker-generator.toml"
        assert paths[1] == expected

    def test_find_config_files_returns_existing_only(self, tmp_path):
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text("")

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            found = find_config_files()
        assert found == [config_file]

    def test_find_config_files_returns_empty_when_none_exist(self, tmp_path):
        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "a.toml", tmp_path / "b.toml"],
        ):
            found = find_config_files()
        assert found == []


class TestLoadConfigFile:
    """Tests for loading a single TOML config file."""

    def test_empty_file(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("")
        config = load_config_file(f)
        assert config.style is None

    def test_api_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text('[api]\napi_key = "test-key-123"\n')
        config = load_config_file(f)
        assert config.api_key == "test-key-123"

    def test_style_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            '[style]\npreset = "kawaii"\noutput_format = "webp"\n'
            "quality = 85\nlossless = true\n"
        )
        config = load_config_file(f)
        assert config.style == "kawaii"
        assert config.output_format == "webp"
        assert config.quality == 85
        assert config.lossless is True

    def test_green_removal_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            "[green_removal]\nhue_center = 120\nhue_range = 30\n"
            "min_saturation = 20\nmin_value = 35\ngreen_threshold = 1.2\n"
        )
        config = load_config_file(f)
        assert config.hue_center == 120
        assert config.hue_range == 30
        assert config.min_saturation == 20
        assert config.min_value == 35
        assert config.green_threshold == 1.2

    def test_processing_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            '[processing]\nedge_threshold = 128\nresize = "512x256"\n'
            "resize_exact = true\n"
        )
        config = load_config_file(f)
        assert config.edge_threshold == 128
        assert config.resize == (512, 256)
        assert config.resize_exact is True

    def test_retry_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[retry]\nmax_retries = 5\nretry_delay = 2.0\n")
        config = load_config_file(f)
        assert config.max_retries == 5
        assert config.retry_delay == 2.0

    def test_batch_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[batch]\ndelay = 0.5\nmax_workers = 4\nstrict = true\n")
        config = load_config_file(f)
        assert config.delay == 0.5
        assert config.max_workers == 4
        assert config.strict is True

    def test_sheet_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[sheet]\nvariations = 6\ncolumns = 3\npadding = 20\n")
        config = load_config_file(f)
        assert config.variations == 6
        assert config.columns == 3
        assert config.padding == 20

    def test_output_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            '[output]\naspect_ratio = "16:9"\nsave_raw = true\n'
            'save_intermediates = "debug_dir"\n'
        )
        config = load_config_file(f)
        assert config.aspect_ratio == "16:9"
        assert config.save_raw is True
        assert config.save_intermediates == "debug_dir"

    def test_all_sections_combined(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            '[style]\npreset = "minimal"\n\n'
            "[green_removal]\nhue_center = 110\n\n"
            "[retry]\nmax_retries = 2\n"
        )
        config = load_config_file(f)
        assert config.style == "minimal"
        assert config.hue_center == 110
        assert config.max_retries == 2

    def test_unknown_section_warns(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[unknown]\nfoo = 1\n")
        with pytest.warns(match="unknown section.*unknown"):
            load_config_file(f)

    def test_unknown_key_warns(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[style]\nunknown_key = 123\n")
        with pytest.warns(match="unknown key.*unknown_key"):
            load_config_file(f)

    def test_top_level_key_warns(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text('top_level = "value"\n')
        with pytest.warns(match="ignoring top-level key"):
            load_config_file(f)

    def test_invalid_toml_raises(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[style\nbroken")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config_file(f)


class TestParseResizeValue:
    """Tests for _parse_resize_value."""

    def test_int_square(self):
        assert _parse_resize_value(512) == (512, 512)

    def test_string_square(self):
        assert _parse_resize_value("256") == (256, 256)

    def test_string_width_x_height(self):
        assert _parse_resize_value("512x256") == (512, 256)

    def test_string_case_insensitive(self):
        assert _parse_resize_value("512X256") == (512, 256)

    def test_array(self):
        assert _parse_resize_value([512, 256]) == (512, 256)

    def test_int_zero_raises(self):
        with pytest.raises(ConfigError, match="positive"):
            _parse_resize_value(0)

    def test_int_negative_raises(self):
        with pytest.raises(ConfigError, match="positive"):
            _parse_resize_value(-1)

    def test_string_invalid_raises(self):
        with pytest.raises(ConfigError, match="Invalid resize format"):
            _parse_resize_value("abc")

    def test_string_triple_x_raises(self):
        with pytest.raises(ConfigError, match="Invalid resize format"):
            _parse_resize_value("1x2x3")

    def test_array_wrong_length_raises(self):
        with pytest.raises(ConfigError, match="exactly 2 elements"):
            _parse_resize_value([1, 2, 3])

    def test_array_non_int_raises(self):
        with pytest.raises(ConfigError, match="must be integers"):
            _parse_resize_value(["a", "b"])

    def test_array_zero_raises(self):
        with pytest.raises(ConfigError, match="positive"):
            _parse_resize_value([0, 256])

    def test_invalid_type_raises(self):
        with pytest.raises(ConfigError, match="Invalid resize value type"):
            _parse_resize_value(3.14)  # type: ignore[arg-type]


class TestValidation:
    """Tests for config validation."""

    def test_invalid_quality_too_low(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[style]\nquality = 0\n")
        with pytest.raises(ConfigError, match="quality must be between 1 and 100"):
            load_config_file(f)

    def test_invalid_quality_too_high(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[style]\nquality = 101\n")
        with pytest.raises(ConfigError, match="quality must be between 1 and 100"):
            load_config_file(f)

    def test_invalid_max_retries(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[retry]\nmax_retries = -1\n")
        with pytest.raises(ConfigError, match="max_retries must be non-negative"):
            load_config_file(f)

    def test_invalid_max_workers(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[batch]\nmax_workers = 0\n")
        with pytest.raises(ConfigError, match="max_workers must be at least 1"):
            load_config_file(f)

    def test_invalid_edge_threshold_below(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[processing]\nedge_threshold = -1\n")
        with pytest.raises(ConfigError, match="edge_threshold must be between"):
            load_config_file(f)

    def test_invalid_edge_threshold_above(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[processing]\nedge_threshold = 256\n")
        with pytest.raises(ConfigError, match="edge_threshold must be between"):
            load_config_file(f)

    def test_invalid_style(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text('[style]\npreset = "nonexistent"\n')
        with pytest.raises(ConfigError, match="Unknown style"):
            load_config_file(f)

    def test_invalid_format(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text('[style]\noutput_format = "bmp"\n')
        with pytest.raises(ConfigError, match="Unknown output_format"):
            load_config_file(f)

    def test_valid_boundary_values(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            "[style]\nquality = 1\n\n"
            "[processing]\nedge_threshold = 0\n\n"
            "[retry]\nmax_retries = 0\n\n"
            "[batch]\nmax_workers = 1\n"
        )
        config = load_config_file(f)
        assert config.quality == 1
        assert config.edge_threshold == 0
        assert config.max_retries == 0
        assert config.max_workers == 1


class TestMergeConfigs:
    """Tests for merge_configs."""

    def test_override_wins(self):
        base = StickerConfig(style="kawaii")
        override = StickerConfig(style="minimal")
        merged = merge_configs(base, override)
        assert merged.style == "minimal"

    def test_base_fallback(self):
        base = StickerConfig(style="kawaii")
        override = StickerConfig()
        merged = merge_configs(base, override)
        assert merged.style == "kawaii"

    def test_both_none_stays_none(self):
        base = StickerConfig()
        override = StickerConfig()
        merged = merge_configs(base, override)
        assert merged.style is None

    def test_different_keys_merge(self):
        base = StickerConfig(style="kawaii", max_retries=5)
        override = StickerConfig(quality=90, max_retries=3)
        merged = merge_configs(base, override)
        assert merged.style == "kawaii"
        assert merged.quality == 90
        assert merged.max_retries == 3

    def test_returns_new_instance(self):
        base = StickerConfig(style="kawaii")
        override = StickerConfig()
        merged = merge_configs(base, override)
        assert merged is not base
        assert merged is not override


class TestLoadConfig:
    """Tests for load_config (full discovery + merge)."""

    def test_no_files_returns_all_none(self, tmp_path):
        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "a.toml", tmp_path / "b.toml"],
        ):
            config = load_config()
        assert config.style is None
        assert config.quality is None

    def test_cwd_overrides_home(self, tmp_path):
        home = tmp_path / "home.toml"
        home.write_text('[style]\npreset = "kawaii"\n')
        cwd = tmp_path / "cwd.toml"
        cwd.write_text('[style]\npreset = "minimal"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[home, cwd],
        ):
            config = load_config()
        assert config.style == "minimal"

    def test_different_keys_from_different_files(self, tmp_path):
        home = tmp_path / "home.toml"
        home.write_text('[style]\npreset = "kawaii"\n')
        cwd = tmp_path / "cwd.toml"
        cwd.write_text("[retry]\nmax_retries = 10\n")

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[home, cwd],
        ):
            config = load_config()
        assert config.style == "kawaii"
        assert config.max_retries == 10

    def test_single_file_only(self, tmp_path):
        home = tmp_path / "home.toml"
        home.write_text('[style]\npreset = "3d"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[home, tmp_path / "nonexistent.toml"],
        ):
            config = load_config()
        assert config.style == "3d"


class TestConfigTemplate:
    """Tests for generate_config_template."""

    def test_template_is_valid_toml(self):
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        template = generate_config_template()
        # The template should parse without errors (all values commented out)
        data = tomllib.loads(template)
        # All sections should exist but be empty (all values are comments)
        for section in data.values():
            assert isinstance(section, dict)

    def test_template_contains_all_sections(self):
        template = generate_config_template()
        for section in [
            "[api]",
            "[style]",
            "[green_removal]",
            "[processing]",
            "[retry]",
            "[batch]",
            "[sheet]",
            "[output]",
        ]:
            assert section in template

    def test_template_values_are_commented(self):
        template = generate_config_template()
        # No uncommented key = value lines (except section headers and blank lines)
        for line in template.strip().split("\n"):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("[")
            ):
                pytest.fail(f"Uncommented line found: {line!r}")


class TestFormatDisplay:
    """Tests for format_config_for_display."""

    def test_empty_config_shows_message(self):
        config = StickerConfig()
        result = format_config_for_display(config)
        assert "No configuration values set" in result

    def test_values_grouped_by_section(self):
        config = StickerConfig(style="kawaii", max_retries=5)
        result = format_config_for_display(config)
        assert "[style]" in result
        assert "[retry]" in result
        assert "preset = 'kawaii'" in result
        assert "max_retries = 5" in result

    def test_api_key_masked(self):
        config = StickerConfig(api_key="super-secret-key-12345")
        result = format_config_for_display(config)
        assert "super-secret-key-12345" not in result
        assert "supe****" in result

    def test_short_api_key_masked(self):
        config = StickerConfig(api_key="abc")
        result = format_config_for_display(config)
        assert "abc" not in result
        assert "****" in result

    def test_none_values_not_shown(self):
        config = StickerConfig(style="kawaii")
        result = format_config_for_display(config)
        assert "quality" not in result
        assert "hue_center" not in result


class TestFormatConfigPaths:
    """Tests for format_config_paths."""

    def test_shows_both_paths(self):
        result = format_config_paths()
        assert "config.toml" in result
        assert ".sticker-generator.toml" in result

    def test_marks_found(self, tmp_path):
        existing = tmp_path / "config.toml"
        existing.write_text("")
        missing = tmp_path / "other.toml"

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[existing, missing],
        ):
            result = format_config_paths()
        assert "[FOUND]" in result
        assert "[not found]" in result


class TestCLIConfigSubcommand:
    """Tests for CLI config subcommands."""

    def test_config_init_creates_cwd_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from sticker_generator.cli import main

        with patch.object(sys, "argv", ["prog", "config", "init"]):
            result = main()
        assert result == 0
        config_file = tmp_path / ".sticker-generator.toml"
        assert config_file.exists()
        content = config_file.read_text()
        assert "[style]" in content

    def test_config_init_global(self, tmp_path):
        from sticker_generator.cli import main

        global_dir = tmp_path / ".config" / "sticker-generator"
        with patch(
            "sticker_generator.cli.Path.home",
            return_value=tmp_path,
        ):
            with patch.object(sys, "argv", ["prog", "config", "init", "--global"]):
                result = main()
        assert result == 0
        assert (global_dir / "config.toml").exists()

    def test_config_init_does_not_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text("existing content")

        from sticker_generator.cli import main

        with patch.object(sys, "argv", ["prog", "config", "init"]):
            result = main()
        assert result == 1
        assert config_file.read_text() == "existing content"

    def test_config_show(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text('[style]\npreset = "kawaii"\n')

        from sticker_generator.cli import main

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "config", "show"]):
                result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "kawaii" in captured.out

    def test_config_path(self, capsys):
        from sticker_generator.cli import main

        with patch.object(sys, "argv", ["prog", "config", "path"]):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "config.toml" in captured.out

    def test_config_unknown_subcommand(self, capsys):
        from sticker_generator.cli import main

        with patch.object(sys, "argv", ["prog", "config", "unknown"]):
            result = main()
        assert result == 1


class TestCLIConfigIntegration:
    """Tests for CLI loading config values."""

    @patch("sticker_generator.cli.create_sticker")
    def test_cli_loads_config_values(self, mock_create, tmp_path, monkeypatch):
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text('[style]\npreset = "kawaii"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["style"] == "kawaii"

    @patch("sticker_generator.cli.create_sticker")
    def test_cli_flags_override_config(self, mock_create, tmp_path):
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text('[style]\npreset = "kawaii"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt", "-s", "minimal"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["style"] == "minimal"

    @patch("sticker_generator.cli.create_sticker")
    def test_no_config_flag_skips_loading(self, mock_create, tmp_path):
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text('[style]\npreset = "kawaii"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt", "--no-config"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["style"] is None

    @patch("sticker_generator.cli.create_sticker")
    def test_config_error_returns_1(self, mock_create, tmp_path):
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text("[style\nbroken")

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 1
        mock_create.assert_not_called()

    @patch("sticker_generator.cli.create_sticker")
    def test_config_provides_defaults(self, mock_create, tmp_path):
        """Config values fill in for unset CLI args."""
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text(
            "[green_removal]\nhue_center = 120\n\n[retry]\nmax_retries = 10\n"
        )

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["hue_center"] == 120
        assert call_kwargs["max_retries"] == 10

    @patch("sticker_generator.cli.create_sticker")
    def test_config_lossless_applied(self, mock_create, tmp_path):
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text("[style]\nlossless = true\n")

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["lossless"] is True

    @patch("sticker_generator.cli.create_sticker")
    def test_config_resize_applied(self, mock_create, tmp_path):
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )
        config_file = tmp_path / ".sticker-generator.toml"
        config_file.write_text('[processing]\nresize = "256x128"\n')

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "nonexistent.toml", config_file],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["resize"] == (256, 128)

    @patch("sticker_generator.cli.create_sticker")
    def test_defaults_applied_without_config(self, mock_create, tmp_path):
        """Without config files, hardcoded defaults should still apply."""
        mock_create.return_value = __import__("PIL.Image", fromlist=["Image"]).new(
            "RGBA", (100, 100)
        )

        with patch(
            "sticker_generator.config.get_config_paths",
            return_value=[tmp_path / "a.toml", tmp_path / "b.toml"],
        ):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output"] == "sticker.png"
        assert call_kwargs["edge_threshold"] == 64
        assert call_kwargs["hue_center"] == 115
        assert call_kwargs["max_retries"] == 3


# Import main here to avoid import-time side effects in class definitions above
from sticker_generator.cli import main  # noqa: E402
