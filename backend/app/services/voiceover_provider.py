from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceoverProvider:
    id: str
    label: str
    description: str
    is_enabled: bool
    is_real_tts: bool
    output_format: str
    recommended_for: str


VOICEOVER_PROVIDERS: tuple[VoiceoverProvider, ...] = (
    VoiceoverProvider(
        id="mock_silence",
        label="本地占位静音 WAV",
        description="生成与分镜时间线等长的静音 WAV，用于验证口播音轨、下载、试听和剪映草稿链路。",
        is_enabled=True,
        is_real_tts=False,
        output_format="wav",
        recommended_for="开发验证和剪映草稿音轨占位",
    ),
    VoiceoverProvider(
        id="jianying_native_tts",
        label="剪映原生朗读",
        description="导出剪映草稿时写入统一的最终字幕与朗读源文本轨，打开剪映后可使用专业版内置朗读音色生成口播。",
        is_enabled=True,
        is_real_tts=False,
        output_format="jianying_text_track",
        recommended_for="使用剪映专业版音色库、减少外部 TTS 成本",
    ),
    VoiceoverProvider(
        id="openai",
        label="OpenAI / GPT TTS",
        description="预留真实 TTS Provider。后续接入后可基于口播稿生成自然旁白。",
        is_enabled=False,
        is_real_tts=True,
        output_format="mp3/wav",
        recommended_for="高质量旁白、情绪化口播",
    ),
    VoiceoverProvider(
        id="edge",
        label="Edge / 本地试听",
        description="预留本地或系统级 TTS Provider。适合低成本试听和离线验证。",
        is_enabled=False,
        is_real_tts=True,
        output_format="mp3/wav",
        recommended_for="低成本试听、快速验证口播节奏",
    ),
    VoiceoverProvider(
        id="custom",
        label="自定义 Provider",
        description="预留第三方 TTS 或自建服务接入点，例如 GLM、DeepSeek 生态或其他语音服务。",
        is_enabled=False,
        is_real_tts=True,
        output_format="mp3/wav",
        recommended_for="后续多供应商扩展",
    ),
)


def list_voiceover_providers() -> list[VoiceoverProvider]:
    return list(VOICEOVER_PROVIDERS)


def get_voiceover_provider(provider_id: str) -> VoiceoverProvider | None:
    normalized = provider_id.strip()
    if not normalized:
        return None
    return next((provider for provider in VOICEOVER_PROVIDERS if provider.id == normalized), None)


def is_voiceover_provider_enabled(provider_id: str) -> bool:
    provider = get_voiceover_provider(provider_id)
    return bool(provider and provider.is_enabled)
