"""Tests for src.chart_renderer."""

import base64
from unittest.mock import AsyncMock, patch

import pytest

from src.chart_renderer import UI_URI_PATTERN, _wrap_chart, render_chart_if_present


class TestUiUriPattern:
    def test_matches_ui_uri(self):
        text = 'Chart available at ui://chart/sales-2024 for review'
        match = UI_URI_PATTERN.search(text)
        assert match is not None
        assert match.group(0) == "ui://chart/sales-2024"

    def test_no_match(self):
        assert UI_URI_PATTERN.search("no chart here") is None

    def test_stops_at_whitespace(self):
        text = "ui://chart/1 extra text"
        match = UI_URI_PATTERN.search(text)
        assert match.group(0) == "ui://chart/1"

    def test_stops_at_quote(self):
        text = '"ui://chart/1"'
        match = UI_URI_PATTERN.search(text)
        assert match.group(0) == "ui://chart/1"


class TestWrapChart:
    def test_returns_iframe(self):
        result = _wrap_chart("<h1>Chart</h1>")
        assert "<iframe" in result
        assert "sandbox=" in result

    def test_base64_encodes_html(self):
        html = "<h1>Test</h1>"
        result = _wrap_chart(html)
        encoded = base64.b64encode(html.encode()).decode()
        assert encoded in result

    def test_custom_height(self):
        result = _wrap_chart("<div/>", height=600)
        assert '600px' in result

    def test_default_height(self):
        result = _wrap_chart("<div/>")
        assert '480px' in result


class TestRenderChartIfPresent:
    @pytest.mark.asyncio
    async def test_no_uri_returns_none(self):
        server = AsyncMock()
        result = await render_chart_if_present("no chart", server)
        assert result is None

    @pytest.mark.asyncio
    async def test_with_uri_fetches_resource(self):
        server = AsyncMock()
        server.read_resource = AsyncMock(return_value="<h1>Chart</h1>")
        mock_text = object()  # sentinel
        with patch("src.chart_renderer.cl.Text", return_value=mock_text) as text_cls:
            result = await render_chart_if_present("see ui://chart/sales", server)
            assert result is mock_text
            server.read_resource.assert_called_once_with("ui://chart/sales")
            text_cls.assert_called_once()
            call_kwargs = text_cls.call_args[1]
            assert "iframe" in call_kwargs["content"]
            assert call_kwargs["display"] == "inline"

    @pytest.mark.asyncio
    async def test_server_error_returns_none(self):
        server = AsyncMock()
        server.read_resource = AsyncMock(side_effect=Exception("not found"))
        result = await render_chart_if_present("see ui://chart/sales", server)
        assert result is None
