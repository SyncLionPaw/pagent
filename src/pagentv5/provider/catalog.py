PROVIDER_CATALOG = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "api_key_required": True,
        "api_protocol": "openai-responses",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key_required": True,
        "api_protocol": "openai-completions",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "api_key_required": True,
        "api_protocol": "openai-completions",
    },
    "mimo": {
        "base_url": "https://api.mimo-v2.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "api_key_required": True,
        "api_protocol": "openai-completions",
    },
    "longcat": {
        "base_url": "https://api.longcat.chat/openai/v1",
        "api_key_env": "LONGCAT_API_KEY",
        "api_key_required": True,
        "api_protocol": "openai-completions",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key_env": "OLLAMA_API_KEY",
        "api_key_required": False,
        "api_protocol": "openai-completions",
    },
    "vllm": {
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key_env": "VLLM_API_KEY",
        "api_key_required": False,
        "api_protocol": "openai-completions",
    },
    "sglang": {
        "base_url": "http://127.0.0.1:30000/v1",
        "api_key_env": "SGLANG_API_KEY",
        "api_key_required": False,
        "api_protocol": "openai-completions",
    },
}
