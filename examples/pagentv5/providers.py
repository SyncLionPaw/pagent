"""pagentv5 Provider 配置 —— 三种构造方式。

Provider 负责身份凭据和 API 协议，complete() 产出模型无关的消息流。
构造方式由需求决定：

1. 具名 Provider：给 provider_id，base_url / api_key_env / api_protocol
   从 PROVIDER_CATALOG 取。最省事。
2. 自带 base_url + api_key：不给 provider_id，直接传 base_url 和
   api_protocol。中转站、私有部署、任意 OpenAI 兼容端点走这条。
3. 同厂商多模型：同一 provider_id 建多个 Provider，各绑一个 model_id，
   共享同一套目录配置（含 api_key_env）。

这个脚本只构造 Provider 并打印身份，不发起网络请求，无需真实 API key。

Usage:
    uv run python -m examples.pagentv5.providers
"""

from pagentv5 import PROVIDER_CATALOG, Provider


def show(label: str, provider: Provider) -> None:
    print(f"[{label}]")
    print(f"  provider_id  = {provider.provider_id}")
    print(f"  model_id     = {provider.model_id}")
    print(f"  api_protocol = {provider.api_protocol}")
    print(f"  base_url     = {provider.base_url}")
    print()


def main() -> None:
    print("目录内可用的 provider_id：", ", ".join(sorted(PROVIDER_CATALOG)))
    print()

    # 1. 具名 Provider：配置从目录取，只需 model_id + provider_id。
    named = Provider("deepseek-v4-flash", provider_id="deepseek", api_key="demo-key")
    show("named", named)

    # 2. 自带端点：中转站 / 私有部署，显式给 base_url 和 api_protocol。
    relay = Provider(
        "gpt-4o-mini",
        base_url="https://relay.example.com/v1",
        api_protocol="openai-completions",
        api_key="demo-key",
    )
    show("custom-endpoint", relay)

    # 3. 同厂商多模型：同一 provider_id，各绑一个 model_id，共享目录配置。
    flash = Provider("deepseek-v4-flash", provider_id="deepseek", api_key="demo-key")
    reasoner = Provider("deepseek-v4-pro", provider_id="deepseek", api_key="demo-key")
    show("deepseek/flash", flash)
    show("deepseek/pro", reasoner)


if __name__ == "__main__":
    main()
