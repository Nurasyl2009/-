"""Export user-reviewed draft text; never claims legal completeness."""
from pathlib import Path
from uuid import uuid4


def export_draft(state, directory):
    if not state.get('done'):
        raise ValueError('Завершите диалог перед экспортом.')
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from assistant import render, FLOWS
    text = render(state['kind'], state['data'])
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(.8)
    section.left_margin = section.right_margin = Inches(.9)
    for name in ('Normal', 'Title'):
        style = document.styles[name]
        style.font.name = 'Arial'
        style.font.color.rgb = RGBColor(0, 0, 0)
    document.styles['Normal'].font.size = Pt(11)
    document.styles['Normal'].paragraph_format.space_after = Pt(6)
    document.add_paragraph(FLOWS[state['kind']][0], style='Title')
    document.add_paragraph('Черновик для проверки председателем. Подготовлен по введённым сведениям.')
    for line in text.splitlines():
        if line:
            document.add_paragraph(line)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / uuid4().hex
    docx_path, txt_path = base.with_suffix('.docx'), base.with_suffix('.txt')
    document.save(docx_path)
    txt_path.write_text('Черновик для проверки председателем.\n\n' + text, encoding='utf-8')
    return txt_path, docx_path
