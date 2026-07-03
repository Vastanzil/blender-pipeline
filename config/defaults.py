"""Default configuration values for Blender Pipeline Studio."""

DEFAULTS = {
    "mcp_host":          "localhost",
    "mcp_port":          8000,
    "connection_mode":   "auto",   # "auto" | "mcpo" | "direct"
    "ai_backend":        "ollama",
    "ollama_host":       "http://localhost:11434",
    "coder_model":       "qwen2.5-coder:7b",
    "planner_model":     "qwen3:8b",
    "openai_api_key":    "",
    "anthropic_api_key": "",
    "gemini_api_key":    "",
    "output_dir":        "",
    "max_retries":       5,
    "poll_interval":     2.0,
    "theme":             "dark",
    "window_geometry":   "1600x900",
    "last_prompt":       "",
    "auto_connect":      True,
    "stream_ai":         True,
    "log_level":         "INFO",
}
