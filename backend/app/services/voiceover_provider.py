from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceoverVoice:
    id: str
    label: str
    gender: str
    description: str


@dataclass(frozen=True)
class VoiceoverProvider:
    id: str
    label: str
    description: str
    is_enabled: bool
    is_real_tts: bool
    output_format: str
    recommended_for: str
    voices: tuple[VoiceoverVoice, ...] = ()


EDGE_VOICES: tuple[VoiceoverVoice, ...] = (
    VoiceoverVoice("auto", "智能匹配", "auto", "根据口播风格和情绪自动选择音色。"),
    VoiceoverVoice("zh-CN-XiaoxiaoNeural", "晓晓（女声）", "female", "自然温暖，适合旅行叙事和治愈内容。"),
    VoiceoverVoice("zh-CN-XiaoyiNeural", "晓伊（女声）", "female", "明快活泼，适合种草和轻快短视频。"),
    VoiceoverVoice("zh-CN-YunxiNeural", "云希（男声）", "male", "年轻清晰，适合攻略和旅行向导。"),
    VoiceoverVoice("zh-CN-YunjianNeural", "云健（男声）", "male", "沉稳有力，适合纪录片和风光旁白。"),
    VoiceoverVoice("zh-CN-YunyangNeural", "云扬（男声）", "male", "专业清楚，适合信息密集型讲解。"),
)


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
        label="Edge TTS（真实口播）",
        description="使用微软在线神经网络音色生成中文 MP3，可直接试听、下载并写入剪映草稿。",
        is_enabled=True,
        is_real_tts=True,
        output_format="mp3",
        recommended_for="低成本生成真实口播、快速验证语速与画面对齐",
        voices=EDGE_VOICES,
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


def get_voiceover_voice(provider_id: str, voice_id: str) -> VoiceoverVoice | None:
    provider = get_voiceover_provider(provider_id)
    normalized = voice_id.strip() or "auto"
    if not provider:
        return None
    return next((voice for voice in provider.voices if voice.id == normalized), None)
