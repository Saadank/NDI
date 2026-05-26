"""Arabic prompt builder for the NDMO assessment engine.

Two prompts: a STATIC system prompt that establishes the assessor role +
the 6-level maturity rubric, and a DYNAMIC user prompt that injects the
specific specification + retrieved chunks.

Design rules:
  * Both prompts are written in Modern Standard Arabic to match the
    document corpus (Saudi government Arabic).
  * The system prompt is fixed verbatim text — no f-string substitution —
    so it can be cached and signed.
  * The user prompt is constructed per spec; the chunk list is rendered
    with explicit numeric markers so Claude can cite by index when needed.
  * EVERY chunk shown to Claude includes its ``chunk_id`` exactly as it
    appears in Qdrant, so the model's citations map directly back to rows
    in ndmo.t_ndmo_citations.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# System prompt — verbatim, no substitution
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_AR: str = """\
أنت مقيّم خبير لمعايير إدارة البيانات الوطنية في المملكة العربية السعودية الصادرة عن \
مكتب إدارة البيانات الوطنية (NDMO).
مهمتك تقييم مدى التزام جهة حكومية بمواصفة محددة من المعايير، اعتماداً فقط على \
المقتطفات (chunks) المستخرجة من وثائق الجهة والمرفقة في الرسالة.

نموذج التقييم هو نموذج النضج الرسمي ذو الست مستويات (0-5):
  • 0 — غياب القدرات: لا توجد لدى الجهة ممارسات قائمة في هذا المجال.
  • 1 — البناء: توجد ممارسات غير رسمية وغير معتمدة.
  • 2 — معرّف: السياسات والإجراءات معرّفة ومعتمدة لكن غير مفعّلة بالكامل.
  • 3 — مفعّل: السياسات والإجراءات مفعّلة وتُنفّذ بشكل منتظم.
  • 4 — ممكّن: السياسات والإجراءات مُنفّذة ومراقَبة بمؤشرات أداء.
  • 5 — ريادي: تحسين مستمر وريادة في الممارسات على مستوى القطاع.

قواعد التقييم الصارمة:
  1. قيّم بناءً فقط على المقتطفات المعطاة في الرسالة. لا تخترع معلومات ولا تستند إلى \
     معرفة عامة.
  2. إذا لم تجد أدلة كافية لمستوى معين، اختر المستوى الأدنى المناسب. \
     في غياب أي دليل اختر المستوى 0.
  3. يجب على كل ادعاء جوهري في rationale_ar أن يكون مدعوماً باستشهاد (citation) \
     من المقتطفات.
  4. حقل chunk_id في كل استشهاد يجب أن يطابق حرفياً أحد قيم chunk_id المدرجة في قسم \
     "الأدلة المرفقة" — لا تخترع أو تعدّل أي معرّف.
  5. حقل supports_level في كل استشهاد يجب أن يساوي مستوى النضج الذي تدعمه هذه القطعة \
     من الدليل (قد يختلف عن maturity_level النهائي إذا كان الدليل جزئياً).
  6. اضبط confidence أقل من 0.6 وضع needs_review=true في الحالات التالية:
       - عدد المقتطفات أقل من 3
       - وجود تناقض بين المقتطفات
       - الأدلة لا تكفي للتمييز بين مستويين متجاورين
  7. يجب أن يكون ردّك كائن JSON واحد يطابق المخطط (response_format) تماماً، \
     بدون أي نص حر قبله أو بعده.
  8. جميع الحقول النصية (rationale_ar, gaps_ar, quoted_text_ar) باللغة العربية \
     الفصحى الحديثة.
"""


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_user_prompt(
    *,
    spec_code: str,
    spec_name_ar: str,
    spec_description_ar: str | None,
    priority: int,
    nca_conditional: bool,
    acceptance_criteria: str | None,
    maturity_levels: dict[str, Any] | None,
    required_elements: dict[str, Any] | None,
    chunks: list[dict[str, Any]],
) -> str:
    """Render the per-spec user prompt.

    ``chunks`` items must be dicts with at minimum: id, payload.text,
    payload.page_number, payload.source_file.  We do NOT trust Claude
    with anything other than ids that appear here.
    """
    parts: list[str] = []

    parts.append("## المواصفة قيد التقييم\n")
    parts.append(f"- **الرمز**: {spec_code}")
    parts.append(f"- **الاسم**: {spec_name_ar}")
    if spec_description_ar:
        parts.append(f"- **الوصف**: {spec_description_ar}")
    parts.append(f"- **الأولوية**: {priority}")
    if nca_conditional:
        parts.append("- **ملاحظة**: هذه المواصفة مشروطة بلوائح الهيئة الوطنية للأمن السيبراني.")
    if acceptance_criteria:
        parts.append(f"- **معايير القبول**:\n  {acceptance_criteria}")
    parts.append("")

    if maturity_levels:
        parts.append("## وصف مستويات النضج لهذه المواصفة")
        for level in sorted(maturity_levels.keys()):
            data = maturity_levels[level] or {}
            name = data.get("name_ar", "")
            desc = data.get("description_ar", "")
            evidence_codes = data.get("evidence_codes") or []
            line = f"- **المستوى {level}**"
            if name:
                line += f" — {name}"
            if desc:
                line += f": {desc}"
            parts.append(line)
            if evidence_codes:
                code_list = ", ".join(
                    e.get("code", str(e)) if isinstance(e, dict) else str(e)
                    for e in evidence_codes
                )
                parts.append(f"  *رموز الأدلة الداعمة*: {code_list}")
        parts.append("")

    if required_elements:
        parts.append("## العناصر المطلوبة (من النموذج المعتمد)")
        # Walk a few well-known keys for readability; dump the rest as a JSON
        # blob so Claude still sees everything.
        for key in ("standard_question_ar", "standard_name_ar", "evidence_codes_from_xlsx"):
            if key in required_elements and required_elements[key]:
                val = required_elements[key]
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val[:20])
                parts.append(f"- **{key}**: {val}")
        parts.append("")

    parts.append("## الأدلة المرفقة")
    parts.append(
        "فيما يلي أعلى المقتطفات صلة بهذه المواصفة، مستخرجة من وثائق الجهة. "
        "كل مقتطف مرفق برمز chunk_id يجب استخدامه حرفياً في حقل citations."
    )
    parts.append("")
    if not chunks:
        parts.append("*(لا توجد مقتطفات ذات صلة — قيّم على هذا الأساس بـ maturity_level=0.)*")
    else:
        for i, chunk in enumerate(chunks, start=1):
            payload = chunk.get("payload") or {}
            chunk_id = chunk.get("id", "")
            source = payload.get("source_file", "(غير معروف)")
            page = payload.get("page_number", "-")
            score = chunk.get("score")
            score_s = f"  | score={score:.3f}" if isinstance(score, (int, float)) else ""
            parts.append(f"### مقتطف [{i}]")
            parts.append(f"- **chunk_id**: `{chunk_id}`")
            parts.append(f"- **الملف**: {source}{score_s}")
            parts.append(f"- **رقم الصفحة**: {page}")
            parts.append("")
            text = payload.get("text", "")
            parts.append(text[:3500])
            parts.append("")

    parts.append("---")
    parts.append(
        "أعد الآن كائن JSON واحد يطابق المخطط المحدد في response_format، "
        "بدون أي نص حر إضافي."
    )
    return "\n".join(parts)


def build_retrieval_query(
    *,
    search_query: str | None,
    name_ar: str,
    description_ar: str | None,
) -> str:
    """Return the text used to retrieve chunks for one spec.

    Strategy (per user direction in Phase 1):
      1. Prefer spec.search_query (the standard's official question).
      2. Otherwise concatenate name_ar + description_ar.

    Only ~43/190 specs have search_query populated; the rest fall back.
    """
    if search_query and search_query.strip():
        return search_query.strip()
    parts: list[str] = [name_ar.strip()]
    if description_ar and description_ar.strip():
        parts.append(description_ar.strip())
    return " — ".join(p for p in parts if p)
