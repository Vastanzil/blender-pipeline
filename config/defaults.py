"""Default configuration values for BlenderCopilot."""

DEFAULTS = {
    "mcp_host":        "localhost",
    "mcp_port":        8000,
    "connection_mode": "auto",   # "auto" | "mcpo" | "direct"
    "ai_backend":      "manifest",
    "manifest_host":   "http://localhost:2099",
    "manifest_token":  "",
    "manifest_model":  "auto",
    "output_dir":      "",
    "rag_corpus_dir":  "",
    "max_retries":     5,
    "poll_interval":   2.0,
    "ai_timeout":      120,
    "theme":           "dark",
    "window_geometry": "1600x900",
    "last_prompt":     "",
    "auto_connect":      True,
    "stream_ai":         True,
    "log_level":         "INFO",
    "ref_loop_max_iter":   3,
    "ref_loop_threshold":  75,
    "hybrid_mode":           False,
    "blenderllm_server_url": "http://127.0.0.1:8080",
    "blenderllm_timeout":    180,
    "blenderllm_home":       "",
    "capture_wireframe":     True,
    "local_layout_llm_url":        "",  # <-- new key for blueprint planning LLM
}