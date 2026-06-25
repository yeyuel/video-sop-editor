import json

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.entities import (
    AssetEntity,
    ProjectEntity,
    PublishPlanEntity,
    RhythmPlanEntity,
    StoryboardSegmentEntity,
    ThemeEntity,
    UserEntity,
)
from app.services.auth import hash_password


def seed_demo_data(session: Session) -> None:
    _ensure_default_director(session)
    _ensure_demo_project(session)


def _ensure_default_director(session: Session) -> None:
    default_user = session.exec(select(UserEntity).where(UserEntity.username == "director")).first()
    if default_user:
        default_user.display_name = "Director"
        default_user.role = "director"
        default_user.ui_enabled = True
        session.add(default_user)
        session.commit()
        return

    session.add(
        UserEntity(
            id="user_director",
            username="director",
            display_name="Director",
            password_hash=hash_password("root123"),
            role="director",
            ui_enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    session.commit()


def _ensure_demo_project(session: Session) -> None:
    project = session.exec(select(ProjectEntity).where(ProjectEntity.id == "proj_001")).first()
    if not project:
        project = ProjectEntity(
            id="proj_001",
            name="阿勒泰雪国片",
            destination="阿勒泰",
            platform="xiaohongshu",
            target_duration_sec=60,
            video_type="emotion_film",
            style_preference="情绪氛围片",
            style_notes="冷蓝色调，以空镜和环境声氛围为主，结尾保留回味感。",
            route_text="将军山 - 喀纳斯 - 禾木",
            media_root=r"D:\素材库\阿勒泰项目",
            status="draft",
            selected_theme_id="theme_001",
        )
        session.add(project)
    else:
        project.name = "阿勒泰雪国片"
        project.destination = "阿勒泰"
        project.platform = "xiaohongshu"
        project.target_duration_sec = 60
        project.video_type = "emotion_film"
        project.style_preference = "情绪氛围片"
        project.style_notes = "冷蓝色调，以空镜和环境声氛围为主，结尾保留回味感。"
        project.route_text = "将军山 - 喀纳斯 - 禾木"
        project.media_root = r"D:\素材库\阿勒泰项目"
        project.status = "draft"
        project.selected_theme_id = "theme_001"
        session.add(project)

    _upsert_asset(
        session,
        AssetEntity(
            asset_id="KANAS_001",
            project_id="proj_001",
            location="喀纳斯",
            scene="蓝冰水流特写，前景带雪面纹理",
            relative_path=r"喀纳斯\drone\KANAS_001.mp4",
            media_type="drone_video",
            shot_type="subject_medium",
            emotion_tags=json.dumps(["冷", "静"], ensure_ascii=False),
            visual_tags=json.dumps(["冷蓝", "白雪"], ensure_ascii=False),
            information_density="medium",
            suggested_duration_sec=1.5,
            function_tags=json.dumps(["slow_climax"], ensure_ascii=False),
        ),
    )
    _upsert_asset(
        session,
        AssetEntity(
            asset_id="HEMU_002",
            project_id="proj_001",
            location="禾木",
            scene="木屋群远景，晨雾从屋顶掠过",
            relative_path=r"禾木\wide\HEMU_002.mp4",
            media_type="video",
            shot_type="wide",
            emotion_tags=json.dumps(["童话"], ensure_ascii=False),
            visual_tags=json.dumps(["蓝调", "木屋"], ensure_ascii=False),
            information_density="high",
            suggested_duration_sec=1.0,
            function_tags=json.dumps(["opening_hook"], ensure_ascii=False),
        ),
    )
    _upsert_asset(
        session,
        AssetEntity(
            asset_id="GENERAL_003",
            project_id="proj_001",
            location="将军山",
            scene="人物从雪道边经过，镜头轻跟拍",
            relative_path=r"将军山\people\GENERAL_003.mp4",
            media_type="mobile_video",
            shot_type="subject_medium",
            emotion_tags=json.dumps(["陪伴", "轻快"], ensure_ascii=False),
            visual_tags=json.dumps(["雪白", "运动"], ensure_ascii=False),
            information_density="medium",
            suggested_duration_sec=1.2,
            function_tags=json.dumps(["transition_buffer"], ensure_ascii=False),
        ),
    )

    _upsert_theme(
        session,
        ThemeEntity(
            id="theme_001",
            project_id="proj_001",
            title="阿勒泰情绪氛围片",
            summary="用雪国空镜和人物经过的瞬间，做一支带沉浸感的冬日旅行短片。",
            core_emotion="沉浸",
            rhythm_profile="前段抓人，中段放缓，结尾回味",
            platform_reason="适合小红书做氛围种草，也方便后续扩展成口播版本。",
        ),
    )
    _upsert_theme(
        session,
        ThemeEntity(
            id="theme_002",
            project_id="proj_001",
            title="阿勒泰路线纪实片",
            summary="按将军山、喀纳斯、禾木的路线推进，突出行程推进感。",
            core_emotion="纪实",
            rhythm_profile="按路线推进，节点处提速",
            platform_reason="适合保留路线清晰度，方便后续扩展攻略版本。",
        ),
    )

    _upsert_storyboard(
        session,
        StoryboardSegmentEntity(
            id="seg_001",
            project_id="proj_001",
            theme_id="theme_001",
            start_time=0.0,
            end_time=1.0,
            asset_id="HEMU_002",
            shot_description="禾木木屋群远景作为开头钩子",
            function_name="opening_hook",
            rhythm="tight_cut",
            beat_mode="beat_1",
            beat_points=json.dumps([0.0, 0.5, 1.0]),
            subtitle="像一脚走进了雪国童话",
        ),
    )
    _upsert_storyboard(
        session,
        StoryboardSegmentEntity(
            id="seg_002",
            project_id="proj_001",
            theme_id="theme_001",
            start_time=1.0,
            end_time=2.5,
            asset_id="GENERAL_003",
            shot_description="将军山人物经过镜头承上启下",
            function_name="transition_buffer",
            rhythm="balanced",
            beat_mode="beat_1",
            beat_points=json.dumps([1.0, 1.5, 2.0, 2.5]),
            subtitle="雪道上的人，把旅程真正带动起来",
        ),
    )

    _upsert_rhythm(
        session,
        RhythmPlanEntity(
            id="rhythm_001",
            project_id="proj_001",
            bgm_style="冷感氛围电子 + 轻鼓点",
            selected_track_name="snow-dream-demo",
            audio_file_name="",
            audio_file_path="",
            analysis_source="rule",
            analysis_notes=json.dumps(
                ["当前为规则生成节拍点，尚未上传真实音频。"],
                ensure_ascii=False,
            ),
            beat_mode="beat_1",
            beat_points=json.dumps([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]),
            rhythm_notes=json.dumps(
                [
                    "前 3 秒保证强开头，优先用高识别度空镜。",
                    "中段适当放慢切换频率，把雪国的安静感留出来。",
                    "高潮段回到最有动势的素材，形成记忆点。",
                ],
                ensure_ascii=False,
            ),
            dark_cut_suggestions=json.dumps([15.0, 30.0, 45.0]),
            photo_motion_suggestions=json.dumps(
                ["照片素材可用轻推或停留 1 到 2 拍，避免和视频一起快切。"],
                ensure_ascii=False,
            ),
        ),
    )

    _upsert_publish_plan(
        session,
        PublishPlanEntity(
            id="publish_001",
            project_id="proj_001",
            title="原来冬天的阿勒泰，真的像童话",
            short_title="阿勒泰雪国童话",
            description="把雪、木屋和路上的人，剪成一段安静但有记忆点的冬日旅程。",
            tags=json.dumps(["阿勒泰", "旅行剪辑", "冬日雪景"], ensure_ascii=False),
            cover_suggestion="优先使用禾木木屋群远景，标题放在右下角保留雪景留白。",
        ),
    )

    session.commit()


def _upsert_asset(session: Session, payload: AssetEntity) -> None:
    current = session.get(AssetEntity, payload.asset_id)
    if current:
        current.project_id = payload.project_id
        current.location = payload.location
        current.scene = payload.scene
        current.relative_path = payload.relative_path
        current.media_type = payload.media_type
        current.shot_type = payload.shot_type
        current.emotion_tags = payload.emotion_tags
        current.visual_tags = payload.visual_tags
        current.information_density = payload.information_density
        current.suggested_duration_sec = payload.suggested_duration_sec
        current.function_tags = payload.function_tags
        session.add(current)
        return
    session.add(payload)


def _upsert_theme(session: Session, payload: ThemeEntity) -> None:
    current = session.get(ThemeEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.title = payload.title
        current.summary = payload.summary
        current.core_emotion = payload.core_emotion
        current.rhythm_profile = payload.rhythm_profile
        current.platform_reason = payload.platform_reason
        session.add(current)
        return
    session.add(payload)


def _upsert_storyboard(session: Session, payload: StoryboardSegmentEntity) -> None:
    current = session.get(StoryboardSegmentEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.theme_id = payload.theme_id
        current.start_time = payload.start_time
        current.end_time = payload.end_time
        current.asset_id = payload.asset_id
        current.shot_description = payload.shot_description
        current.function_name = payload.function_name
        current.rhythm = payload.rhythm
        current.beat_mode = payload.beat_mode
        current.beat_points = payload.beat_points
        current.subtitle = payload.subtitle
        session.add(current)
        return
    session.add(payload)


def _upsert_rhythm(session: Session, payload: RhythmPlanEntity) -> None:
    current = session.get(RhythmPlanEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.bgm_style = payload.bgm_style
        current.selected_track_name = payload.selected_track_name
        current.audio_file_name = payload.audio_file_name
        current.audio_file_path = payload.audio_file_path
        current.analysis_source = payload.analysis_source
        current.analysis_notes = payload.analysis_notes
        current.beat_mode = payload.beat_mode
        current.beat_points = payload.beat_points
        current.rhythm_notes = payload.rhythm_notes
        current.dark_cut_suggestions = payload.dark_cut_suggestions
        current.photo_motion_suggestions = payload.photo_motion_suggestions
        session.add(current)
        return
    session.add(payload)


def _upsert_publish_plan(session: Session, payload: PublishPlanEntity) -> None:
    current = session.get(PublishPlanEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.title = payload.title
        current.short_title = payload.short_title
        current.description = payload.description
        current.tags = payload.tags
        current.cover_suggestion = payload.cover_suggestion
        session.add(current)
        return
    session.add(payload)
