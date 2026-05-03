"""Tests for src.mcp_servers."""

from unittest.mock import patch

from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from src.mcp_servers import _is_url, _make_server, get_mcp_servers_named


class TestIsUrl:
    def test_http(self):
        assert _is_url("http://localhost:8080") is True

    def test_https(self):
        assert _is_url("https://api.example.com/mcp") is True

    def test_local_path(self):
        assert _is_url("/home/user/mcp-server") is False

    def test_relative_path(self):
        assert _is_url("../mcp-server") is False

    def test_empty(self):
        assert _is_url("") is False


class TestMakeServer:
    def test_url_creates_streamable_http(self):
        server = _make_server("http://localhost:8080/mcp", "my_module", None)
        assert isinstance(server, MCPServerStreamableHTTP)

    def test_path_creates_stdio(self):
        server = _make_server("/opt/mcp-server", "my_module", None)
        assert isinstance(server, MCPServerStdio)


class TestGetMcpServersNamed:
    def test_empty_config_returns_empty(self):
        with patch("src.mcp_servers.settings") as mock_settings:
            mock_settings.analytics_server_dir = ""
            mock_settings.semantic_layer_server_dir = ""
            assert get_mcp_servers_named() == []

    def test_one_configured(self):
        with patch("src.mcp_servers.settings") as mock_settings:
            mock_settings.analytics_server_dir = "http://localhost:8001/mcp"
            mock_settings.semantic_layer_server_dir = ""
            result = get_mcp_servers_named()
            assert len(result) == 1
            name, server = result[0]
            assert name == "OrionBelt Analytics"
            assert isinstance(server, MCPServerStreamableHTTP)

    def test_both_configured(self):
        with patch("src.mcp_servers.settings") as mock_settings:
            mock_settings.analytics_server_dir = "http://localhost:8001/mcp"
            mock_settings.semantic_layer_server_dir = "/opt/semantic-layer"
            result = get_mcp_servers_named()
            assert len(result) == 2

    def test_returns_name_server_pairs(self):
        with patch("src.mcp_servers.settings") as mock_settings:
            mock_settings.analytics_server_dir = "/opt/analytics"
            mock_settings.semantic_layer_server_dir = "/opt/semantic"
            result = get_mcp_servers_named()
            names = [n for n, _ in result]
            assert names == ["OrionBelt Analytics", "OrionBelt Semantic Layer"]
