from app.services.nlp_service import NLPService


def test_pdf_line_wrap_is_joined_without_merging_section_headings():
    text = "技能栈\nPy\nthon、Machine Learning、分布式计\n算\n工作经历\n负责服务端开发"

    skills = NLPService._extract_labeled_skill_section(text)

    assert "Python" in skills
    assert "Machine Learning" in skills
    assert "分布式计算" in skills
    assert "工作经历" not in skills
    assert "负责服务端开发" not in skills


def test_inline_skill_field_is_used_when_no_standalone_section_exists():
    text = "个人概述\n技能栈：Python、FastAPI\n项目经历\n构建接口服务"

    assert NLPService._extract_labeled_skill_section(text) == ["Python", "FastAPI"]
