from __future__ import annotations

from app.models.schemas import ExportPlanRead, ExportValidationRead, NarrativeThemeRead, ProjectRead

EXPORT_TEXT_MIN_LENGTH = 2


def _normalize_text(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip()).lower()


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_keyword = keyword.strip().lower()
    if len(normalized_keyword) < EXPORT_TEXT_MIN_LENGTH:
        return False
    return normalized_keyword in text


def build_export_validation(
    *,
    project: ProjectRead | None,
    theme: NarrativeThemeRead | None,
    export_plan: ExportPlanRead | None,
) -> ExportValidationRead:
    if not project or not export_plan:
        return ExportValidationRead(
            destinationMentioned=False,
            themeConsistencyPassed=False,
            message="导出信息不完整，暂无法校验。",
            issues=["缺少项目或导出文案"],
        )

    export_text = _normalize_text(
        export_plan.title,
        export_plan.shortTitle,
        export_plan.description,
        " ".join(export_plan.tags),
    )
    destination = project.destination.strip()
    issues: list[str] = []

    destination_mentioned = _contains_keyword(export_text, destination)
    if destination and not destination_mentioned:
        issues.append(f"导出文案未提及目的地「{destination}」")

    theme_consistency_passed = True
    if theme:
        theme_title = theme.title.strip()
        theme_hint = _normalize_text(theme.title, theme.coreEmotion, theme.summary)
        title_match = _contains_keyword(export_text, theme_title) if theme_title else False
        emotion_match = (
            _contains_keyword(export_text, theme.coreEmotion.strip())
            if theme.coreEmotion.strip()
            else False
        )
        theme_consistency_passed = title_match or emotion_match or destination_mentioned
        if not theme_consistency_passed:
            issues.append(f"导出文案与当前主题「{theme.title}」关联偏弱")

    passed = not issues
    message = (
        "导出文案与项目目的地、主题一致。"
        if passed
        else "；".join(issues)
    )
    return ExportValidationRead(
        destinationMentioned=destination_mentioned,
        themeConsistencyPassed=theme_consistency_passed,
        message=message,
        issues=issues,
    )
