#!/usr/bin/env python3
"""jarvis_docs.py — Document Generator Engine: Word, Excel, PowerPoint, PDF"""
import json, os, time, tempfile, subprocess
from pathlib import Path

# Pre-import pptx at module level so sys.modules has it cached
try:
    import pptx as _PPX
except ImportError:
    _PPX = None

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DL_DIR = DATA_DIR / "downloads"
DL_DIR.mkdir(parents=True, exist_ok=True)

EXT_MAP = {"word": "docx", "excel": "xlsx", "powerpoint": "pptx", "pdf": "pdf"}

class DocGenerator:
    __slots__ = ()

    def _dl_url(self, path):
        return f"/downloads/{Path(path).name}"

    def _open(self, path):
        subprocess.Popen(["open", "-R", str(path)])

    def _sanitize(self, data):
        if isinstance(data, str):
            try: data = json.loads(data)
            except: pass
        if isinstance(data, dict):
            base = dict(data)
            base.setdefault("headers", [])
            base.setdefault("rows", base.pop("data", []))
            base.setdefault("title", "Documento")
            base.setdefault("text", "")
            return base
        if isinstance(data, list) and all(isinstance(r, dict) for r in data):
            if data:
                return {"headers": list(data[0].keys()), "rows": [list(r.values()) for r in data],
                        "title": "Report", "text": ""}
        return {"headers": [], "rows": [], "title": "Documento", "text": str(data)}

    # ── WORD ──
    def make_docx(self, data, output=None):
        import docx
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        d = self._sanitize(data)
        doc = docx.Document()
        title = doc.add_heading(d["title"], 0)
        if d["text"]:
            doc.add_paragraph(d["text"])
        if d["headers"] and d["rows"]:
            table = doc.add_table(rows=1 + len(d["rows"]), cols=len(d["headers"]))
            table.style = "Light Grid Accent 1"
            for i, h in enumerate(d["headers"]):
                cell = table.rows[0].cells[i]
                cell.text = str(h)
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True
            for ri, row in enumerate(d["rows"]):
                for ci, val in enumerate(row):
                    table.rows[ri + 1].cells[ci].text = str(val)
            doc.add_paragraph()
        if not output:
            output = str(DL_DIR / f"document_{int(time.time())}.docx")
        else:
            output = str(Path(output))
        doc.save(output)
        self._open(output)
        return output, self._dl_url(output)
    def make_docx_from_text(self, text, title="Documento", output=None):
        import docx
        doc = docx.Document()
        doc.add_heading(title, 0)
        for p in text.split("\n"):
            if p.strip():
                doc.add_paragraph(p.strip())
        if not output:
            output = str(DL_DIR / f"document_{int(time.time())}.docx")
        else:
            output = str(Path(output))
        doc.save(output)
        self._open(output)
        return output, self._dl_url(output)

    # ── EXCEL ──
    def make_xlsx(self, data, output=None):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.chart import BarChart, PieChart, LineChart, Reference
        from openpyxl.utils import get_column_letter
        d = self._sanitize(data)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = d["title"][:31]
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        thin = Side(style="thin", color="B4C6E7")
        border = Border(top=thin, left=thin, right=thin, bottom=thin)
        if d["headers"]:
            for ci, h in enumerate(d["headers"], 1):
                cell = ws.cell(row=1, column=ci, value=str(h))
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
                cell.border = border
            ws.row_dimensions[1].height = 22
        alt_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
        for ri, row in enumerate(d["rows"], 2):
            for ci, val in enumerate(row, 1):
                cell = ws.cell(row=ri, column=ci, value=val)
                cell.border = border
                if ri % 2 == 0:
                    cell.fill = alt_fill
        for ci in range(1, len(d["headers"]) + 1):
            col_letter = get_column_letter(ci)
            max_len = max((len(str(ws.cell(row=r, column=ci).value or "")) for r in range(1, len(d["rows"]) + 2)), default=10)
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)
        ws.auto_filter.ref = ws.dimensions if d["headers"] else None
        if not output:
            output = str(DL_DIR / f"data_{int(time.time())}.xlsx")
        else:
            output = str(Path(output))
        wb.save(output)
        self._open(output)
        return output, self._dl_url(output)

# ── POWERPOINT SUPER SPECIAL v2.5 ──
    def make_pptx(self, data, slides_data=None, output=None):
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu, Cm
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.oxml.ns import qn, nsmap
        from lxml import etree

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        # ── Palette ──
        PALETTES = {
            "corporate": {"bg1":(0x1B,0x1B,0x2F),"bg2":(0xF8,0xF9,0xFC),
                "a1":(0x4F,0x46,0xE5),"a2":(0x06,0xB6,0xD4),
                "td":(0x1E,0x1E,0x2E),"tl":(0xF1,0xF5,0xF9),
                "th":(0x4F,0x46,0xE5),"tb":(0xC8,0xCB,0xE6)},
            "dark": {"bg1":(0x0D,0x0D,0x0D),"bg2":(0x1A,0x1A,0x1A),
                "a1":(0xE5,0x00,0x7F),"a2":(0x00,0xD2,0xFF),
                "td":(0xFF,0xFF,0xFF),"tl":(0xE0,0xE0,0xE0),
                "th":(0xE5,0x00,0x7F),"tb":(0x33,0x33,0x33)},
            "nature": {"bg1":(0x0A,0x1F,0x0A),"bg2":(0xF0,0xF7,0xED),
                "a1":(0x2E,0x7D,0x32),"a2":(0x8B,0xC3,0x4A),
                "td":(0x1B,0x2E,0x1B),"tl":(0xE8,0xF5,0xE1),
                "th":(0x2E,0x7D,0x32),"tb":(0xA5,0xD6,0xA7)},
            "sunset": {"bg1":(0x1A,0x0A,0x1E),"bg2":(0xFF,0xF5,0xEE),
                "a1":(0xFF,0x6B,0x35),"a2":(0xFF,0xD9,0x3D),
                "td":(0x2D,0x1B,0x2E),"tl":(0xFF,0xED,0xD6),
                "th":(0xFF,0x6B,0x35),"tb":(0xFF,0xCC,0xAA)},
        }

        def _R(t):
            return RGBColor(*t) if isinstance(t, tuple) else t

        def _hex(t):
            return f"{t[0]:02X}{t[1]:02X}{t[2]:02X}" if isinstance(t, tuple) else str(t)[:6]

        def _set_bg(slide, c):
            bg = slide.background; f = bg.fill; f.solid(); f.fore_color.rgb = _R(c)

        def _add_shape(slide, l, t, w, h, c, st=MSO_SHAPE.RECTANGLE):
            s = slide.shapes.add_shape(st, l, t, w, h); s.fill.solid()
            s.fill.fore_color.rgb = _R(c); s.line.fill.background()
            return s

        def _add_txt(slide, text, l, t, w, h, sz=18, b=False, c=None, a=PP_ALIGN.LEFT, fn="Calibri"):
            tb = slide.shapes.add_textbox(l, t, w, h)
            tf = tb.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.text = str(text)
            p.font.size = Pt(sz); p.font.bold = b; p.font.name = fn
            if c: p.font.color.rgb = _R(c)
            p.alignment = a
            return tb

        def _add_grad_bar(slide, l, t, w, h, c1, c2):
            s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
            s.line.fill.background()
            sp = s._element; spPr = sp.find(qn('p:spPr')) if sp.find(qn('p:spPr')) is not None else sp.find(qn('a:spPr')) if sp.find(qn('a:spPr')) is not None else None
            if spPr is None: return s
            gf = etree.SubElement(spPr, qn('a:gradFill'))
            gsL = etree.SubElement(gf, qn('a:gsLst'))
            e1 = etree.SubElement(gsL, qn('a:gs'), {'pos': '0'})
            etree.SubElement(e1, qn('a:srgbClr'), {'val': _hex(c1)})
            e2 = etree.SubElement(gsL, qn('a:gs'), {'pos': '100000'})
            etree.SubElement(e2, qn('a:srgbClr'), {'val': _hex(c2)})
            etree.SubElement(gf, qn('a:lin'), {'ang': '2700000', 'scaled': '1'})
            return s

        def _add_shadow(s, dist=Cm(0.3), ang=5400000):
            sp = s._element; spPr = sp.find(qn('p:spPr')) if sp.find(qn('p:spPr')) is not None else sp.find(qn('a:spPr'))
            if spPr is None: return
            effect = etree.SubElement(spPr, qn('a:effectLst'))
            shdw = etree.SubElement(effect, qn('a:outerShdw'), {'blurRad': Cm(0.4), 'dist': dist, 'dir': str(ang), 'algn': 'tl'})
            etree.SubElement(shdw, qn('a:srgbClr'), {'val': '000000'}).set('alpha', '30000')

        def _build_table(table, headers, rows, hc, ac):
            nc = len(headers); nr = 1 + len(rows)
            for ci in range(nc):
                cell = table.cell(0, ci); cell.text = str(headers[ci])
                for p in cell.text_frame.paragraphs:
                    p.alignment = PP_ALIGN.CENTER
                    for r in p.runs: r.font.bold = True; r.font.size = Pt(12); r.font.color.rgb = RGBColor(0xFF,0xFF,0xFF); r.font.name = "Calibri"
                tc = cell._tc; tcPr = tc.get_or_add_tcPr()
                solidFill = tcPr.makeelement(qn('a:solidFill'), {})
                solidFill.append(solidFill.makeelement(qn('a:srgbClr'), {'val': _hex(hc)}))
                tcPr.append(solidFill)
            for ri in range(len(rows)):
                for ci in range(nc):
                    cell = table.cell(ri+1, ci); cell.text = str(rows[ri][ci])
                    for p in cell.text_frame.paragraphs:
                        p.alignment = PP_ALIGN.CENTER
                        for r in p.runs: r.font.size = Pt(11); r.font.name = "Calibri"; r.font.color.rgb = RGBColor(0x33,0x33,0x33)
                    if ri % 2 == 0:
                        tc = cell._tc; tcPr = tc.get_or_add_tcPr()
                        solidFill = tcPr.makeelement(qn('a:solidFill'), {})
                        solidFill.append(solidFill.makeelement(qn('a:srgbClr'), {'val': _hex(ac)}))
                        tcPr.append(solidFill)

        def _bullets(slide, items, l, t, w, h, sz=14, c=None, sp=Pt(8)):
            c = c or (0xE0,0xE0,0xE0); tx = slide.shapes.add_textbox(l, t, w, h)
            tf = tx.text_frame; tf.word_wrap = True
            for i, item in enumerate(items):
                txt = item if isinstance(item, str) else item.get("text","")
                lv = 0 if isinstance(item, str) else item.get("level",0)
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.text = str(txt); p.level = lv
                p.font.size = Pt(sz - lv*2); p.font.color.rgb = _R(c); p.font.name = "Calibri"
                p.space_after = sp; pPr = p._p.get_or_add_pPr()
                pPr.append(pPr.makeelement(qn('a:buChar'), {'char': '●' if lv==0 else '○'}))

        d = self._sanitize(data)
        theme = d.get("theme", "corporate")
        pal = PALETTES.get(theme, PALETTES["corporate"])

        slides = slides_data or []
        if isinstance(slides, str):
            try: slides = json.loads(slides)
            except: slides = [{"title": d["title"], "content": d.get("text", "")}]
        if not slides:
            slides = [{"type":"title","title":d["title"],"subtitle":d.get("text","Report")}]
            if d["headers"]:
                slides.append({"type":"table","title":"Dettaglio Dati","headers":d["headers"],"rows":d["rows"]})
            slides.append({"type":"thank_you","title":"Grazie!","subtitle":"Domande?"})

        for si, sd in enumerate(slides):
            st = sd.get("type","content")
            title = sd.get("title",f"Slide {si+1}")
            subtitle = sd.get("subtitle",""); content = sd.get("content","")
            items = sd.get("items",sd.get("bullets",[]))
            headers = sd.get("headers",d.get("headers",[]))
            rows = sd.get("rows",d.get("rows",[]))
            img = sd.get("image","")

            sl = prs.slides.add_slide(prs.slide_layouts[6])

            if st in ("title","section","thank_you"):
                _set_bg(sl, pal["bg1"])
                _add_grad_bar(sl, Inches(0), Inches(0), prs.slide_width, Inches(0.12), pal["a1"], pal["a2"])
                if st == "title":
                    _add_txt(sl, title, Inches(1.5), Inches(1.8), Inches(10.3), Inches(1.5), sz=54, b=True, c=pal["tl"], a=PP_ALIGN.CENTER)
                    if subtitle: _add_txt(sl, subtitle, Inches(1.5), Inches(3.8), Inches(10.3), Inches(1.0), sz=22, c=pal["a2"], a=PP_ALIGN.CENTER)
                    _add_txt(sl, f"— {sd.get('author','J.A.R.V.I.S')} —", Inches(1.5), Inches(5.5), Inches(10.3), Inches(0.8), sz=14, c=(0x88,0x88,0xAA), a=PP_ALIGN.CENTER)
                elif st == "section":
                    _add_txt(sl, title, Inches(1.5), Inches(1.5), Inches(10.3), Inches(1.8), sz=44, b=True, c=pal["tl"], a=PP_ALIGN.CENTER)
                    if subtitle: _add_txt(sl, subtitle, Inches(1.5), Inches(3.7), Inches(10.3), Inches(1.0), sz=20, c=pal["a2"], a=PP_ALIGN.CENTER)
                    _add_txt(sl, f"{si+1:02d}", Inches(1.5), Inches(5.8), Inches(10.3), Inches(0.8), sz=60, b=True, c=(0x33,0x33,0x55), a=PP_ALIGN.CENTER)
                else: # thank_you
                    _add_txt(sl, title, Inches(1.5), Inches(1.5), Inches(10.3), Inches(1.5), sz=48, b=True, c=pal["tl"], a=PP_ALIGN.CENTER)
                    if subtitle: _add_txt(sl, subtitle, Inches(1.5), Inches(3.8), Inches(10.3), Inches(1.0), sz=24, c=pal["a2"], a=PP_ALIGN.CENTER)
                    _add_txt(sl, "J.A.R.V.I.S — Document Generator v2.5", Inches(1.5), Inches(6.0), Inches(10.3), Inches(0.8), sz=13, c=(0x66,0x66,0x88), a=PP_ALIGN.CENTER)
                continue

            _set_bg(sl, pal["bg2"])
            _add_grad_bar(sl, Inches(0), Inches(0), prs.slide_width, Inches(0.08), pal["a1"], pal["a2"])

            if st == "two_column":
                _add_txt(sl, title, Inches(1.0), Inches(0.3), Inches(11.3), Inches(0.7), sz=30, b=True, c=pal["td"])
                cols = sd.get("columns", [])
                c1 = cols[0] if cols else []; c2 = cols[1] if len(cols)>1 else []
                _add_shape(sl, Inches(6.5), Inches(1.3), Cm(0.08), Inches(5.5), pal["a2"])
                if c1:
                    _add_txt(sl, sd.get("col1_title",""), Inches(0.8), Inches(1.3), Inches(5.2), Inches(0.6), sz=20, b=True, c=pal["a1"])
                    _bullets(sl, c1 if isinstance(c1,list) else [c1], Inches(0.8), Inches(2.0), Inches(5.2), Inches(4.8), sz=14, c=pal["td"])
                if c2:
                    _add_txt(sl, sd.get("col2_title",""), Inches(6.9), Inches(1.3), Inches(5.2), Inches(0.6), sz=20, b=True, c=pal["a1"])
                    _bullets(sl, c2 if isinstance(c2,list) else [c2], Inches(6.9), Inches(2.0), Inches(5.2), Inches(4.8), sz=14, c=pal["td"])

            elif st == "chart":
                _add_txt(sl, title, Inches(1.0), Inches(0.2), Inches(11.3), Inches(0.7), sz=28, b=True, c=pal["td"])
                ct_name = sd.get("chart_type","bar")
                if headers and rows:
                    from pptx.chart.data import CategoryChartData
                    from pptx.enum.chart import XL_CHART_TYPE
                    cd2 = CategoryChartData()
                    cd2.categories = [str(r[0]) for r in rows[:12]]
                    for ci in range(1, min(len(headers),5)):
                        cd2.add_series(headers[ci], [r[ci] if isinstance(r[ci],(int,float)) else 0 for r in rows[:12]])
                    cmap = {"bar":XL_CHART_TYPE.COLUMN_CLUSTERED,"pie":XL_CHART_TYPE.PIE,
                            "line":XL_CHART_TYPE.LINE_MARKERS,"area":XL_CHART_TYPE.AREA}
                    ct = cmap.get(ct_name, XL_CHART_TYPE.COLUMN_CLUSTERED)
                    cf = sl.shapes.add_chart(ct, Cm(0.5), Cm(2), Cm(17), Cm(7), cd2)
                    ch = cf.chart; ch.has_legend = True

            elif st == "image":
                _add_txt(sl, title, Inches(1.0), Inches(0.2), Inches(11.3), Inches(0.7), sz=28, b=True, c=pal["td"])
                if img:
                    p_img = Path(img)
                    if p_img.exists():
                        sl.shapes.add_picture(str(p_img), Inches(1.5), Inches(1.5), Inches(10.3))
                if content:
                    _add_txt(sl, content, Inches(1.5), Inches(6.0), Inches(10.3), Inches(1.0), sz=14, c=pal["td"])

            else:
                # content / table
                _add_txt(sl, title, Inches(1.0), Inches(0.2), Inches(11.3), Inches(0.7), sz=30, b=True, c=pal["td"])
                if items:
                    _bullets(sl, items, Inches(1.2), Inches(1.2), Inches(10.8), Inches(5.5), sz=16, c=pal["td"])
                elif content:
                    lines = content.split("\n") if isinstance(content,str) else content
                    txt = lines if isinstance(lines,str) else "\n".join(lines)
                    _add_txt(sl, txt, Inches(1.2), Inches(1.2), Inches(10.8), Inches(5.5), sz=18, c=pal["td"])
                if headers and rows:
                    tshape = sl.shapes.add_table(1+len(rows), len(headers), Inches(1.0), Inches(2.0), Inches(11.3), Inches(5.0))
                    _build_table(tshape.table, headers, rows, pal["th"], (0xF0,0xF0,0xFF))
                if img:
                    p_img = Path(img)
                    if p_img.exists():
                        try: sl.shapes.add_picture(str(p_img), Inches(10.0), Inches(5.5), Inches(2.5))
                        except: pass

            # Footer
            try:
                _add_txt(sl, f"{si+1:02d}", Inches(12.0), Inches(7.0), Inches(1.0), Inches(0.4), sz=9, c=(0xAA,0xAA,0xAA), a=PP_ALIGN.RIGHT)
            except: pass

        if not output:
            output = str(DL_DIR / f"presentation_{int(time.time())}.pptx")
        else:
            output = str(Path(output))
        prs.save(output)
        self._open(output)
        return output, self._dl_url(output)

    # ── PDF ──
    def make_pdf(self, data, output=None):
        from fpdf import FPDF
        d = self._sanitize(data)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 15, d["title"], new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        if d["text"]:
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, d["text"])
            pdf.ln(3)
        if d["headers"] and d["rows"]:
            col_w = max(20, min(50, 190 // len(d["headers"])))
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(47, 84, 150)
            pdf.set_text_color(255, 255, 255)
            for h in d["headers"]:
                pdf.cell(col_w, 8, str(h), border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 8)
            for ri, row in enumerate(d["rows"]):
                if ri % 2 == 0:
                    pdf.set_fill_color(214, 228, 240)
                else:
                    pdf.set_fill_color(255, 255, 255)
                for val in row:
                    pdf.cell(col_w, 7, str(val)[:20], border=1, fill=True, align="C")
                pdf.ln()
                if ri > 50:
                    pdf.cell(0, 7, f"... e altre {len(d['rows']) - ri} righe", align="C")
                    break
        if not output:
            output = str(DL_DIR / f"report_{int(time.time())}.pdf")
        else:
            output = str(Path(output))
        pdf.output(output)
        self._open(output)
        return output, self._dl_url(output)

    # ── HTML PRESENTATION (da skill get.skills presentation-creator) ──
    def make_html_presentation(self, data, slides=None, output=None):
        """Genera presentazione HTML interattiva — stile Sentry design system.
        Supporta: title, section, content, two_column, table, chart (bar/pie/line), image, thank_you.
        Non richiede React/Vite — singolo file HTML autoportante.
        """
        d = self._sanitize(data)
        theme = d.get("theme", "corporate")

        PAL = {
            "corporate": {"bg":"#faf9fb","dk":"#1c1028","pu":"#6c5fc7","pl":"#b5aade","pb":"#ede8f5",
                          "mu":"#80708f","bd":"#dbd6e1","gr":"#2ba185","rd":"#f55459","am":"#d4953a",
                          "cat":["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ac"]},
            "dark": {"bg":"#1c1028","dk":"#faf9fb","pu":"#b5aade","pl":"#6c5fc7","pb":"#2d2040",
                     "mu":"#9a8aa9","bd":"#3d3050","gr":"#2ba185","rd":"#f55459","am":"#d4953a",
                     "cat":["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ac"]},
            "nature": {"bg":"#f0f7ed","dk":"#1b2e1b","pu":"#2e7d32","pl":"#8bc34a","pb":"#e0f0dc",
                       "mu":"#5a7a5a","bd":"#a5d6a7","gr":"#2e7d32","rd":"#c62828","am":"#f9a825",
                       "cat":["#2e7d32","#558b2f","#8bc34a","#aed581","#1b5e20","#689f38","#7cb342","#9ccc65","#c0ca33","#d4e157"]},
            "sunset": {"bg":"#fff5ee","dk":"#2d1b2e","pu":"#ff6b35","pl":"#ffd93d","pb":"#ffe8d6",
                       "mu":"#a08070","bd":"#ffccaa","gr":"#2ba185","rd":"#f55459","am":"#d4953a",
                       "cat":["#ff6b35","#ffd93d","#ff9f43","#ee5a24","#f368e0","#ff9ff3","#54a0ff","#5f27cd","#01a3a4","#00d2d3"]},
        }
        p = PAL.get(theme, PAL["corporate"])

        slides_list = slides or []
        if isinstance(slides_list, str):
            try: slides_list = json.loads(slides_list)
            except: slides_list = []
        if not slides_list:
            slides_list = [{"type":"title","title":d["title"],"subtitle":d.get("text","")}]
            if d.get("headers") and d.get("rows"):
                slides_list.append({"type":"table","title":"Dati","headers":d["headers"],"rows":d["rows"]})
            slides_list.append({"type":"thank_you","title":"Grazie!","subtitle":"Domande?"})

        # ── Build slides HTML ──
        slide_htmls = []
        for si, sd in enumerate(slides_list):
            st = sd.get("type","content")
            title = sd.get("title",f"Slide {si+1}")
            subtitle = sd.get("subtitle","")
            content = sd.get("content","")
            items = sd.get("items",sd.get("bullets",[]))
            headers = sd.get("headers",d.get("headers",[]))
            rows = sd.get("rows",d.get("rows",[]))
            chart_type = sd.get("chart_type","bar")
            img_src = sd.get("image","")
            author = sd.get("author","J.A.R.V.I.S")
            cols = sd.get("columns",[])
            col1_title = sd.get("col1_title","")
            col2_title = sd.get("col2_title","")

            def _row_html(r):
                return "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"

            def _table_html(h, r):
                if not h: return ""
                th = "".join(f"<th>{x}</th>" for x in h)
                tr = "".join(_row_html(row) for row in r)
                return f'<table class="compare"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'

            def _chart_data(h, r):
                if not h or not r: return "{}"
                labels = [str(row[0]) for row in r[:12]]
                def _num(v):
                    if isinstance(v,(int,float)): return v
                    if isinstance(v,str):
                        v = v.replace('%','').replace('€','').replace('$','').strip()
                        try: return float(v)
                        except: pass
                        # range "14-30" → midpoint
                        if '-' in v:
                            parts = v.split('-')
                            try: return (float(parts[0]) + float(parts[1])) / 2
                            except: pass
                        try: return float(v.split()[0])
                        except: return 0
                    return 0
                series = []
                for ci in range(1, min(len(h), 6)):
                    vals = [_num(row[ci]) for row in r[:12]]
                    series.append({"name":h[ci],"data":vals,"color":p["cat"][(ci-1)%10]})
                return json.dumps({"labels":labels,"series":series,"type":chart_type})

            if st == "title":
                slide_htmls.append(f"""<div class="slide active" data-idx="0">
  <div class="slide-content anim" style="text-align:center;padding-top:120px">
    <h1 style="font-size:3rem;font-weight:700;letter-spacing:-0.03em;margin-bottom:16px">{title}</h1>
    {f'<p class="subtitle" style="font-size:1.1rem;color:{p["mu"]};max-width:620px;margin:0 auto">{subtitle}</p>' if subtitle else ''}
    <p style="margin-top:60px;font-size:0.85rem;color:{p["mu"]}">— {author} —</p>
  </div>
</div>""")

            elif st in ("section","thank_you"):
                slide_htmls.append(f"""<div class="slide" data-idx="{si}">
  <div class="slide-content anim" style="text-align:center;padding-top:140px">
    <h1 style="font-size:2.8rem;font-weight:700;letter-spacing:-0.03em">{title}</h1>
    {f'<p class="subtitle" style="font-size:1.1rem;color:{p["mu"]};margin-top:12px">{subtitle}</p>' if subtitle else ''}
  </div>
</div>""")

            elif st == "two_column":
                c1 = cols[0] if cols else []
                c2 = cols[1] if len(cols) > 1 else []
                def _col_items(items):
                    if not items: return ""
                    lis = "".join(f"<li>{x}</li>" for x in items)
                    return f"<ul>{lis}</ul>"
                slide_htmls.append(f"""<div class="slide" data-idx="{si}">
  <div class="slide-content anim">
    <h2 class="d1">{title}</h2>
    <div class="cols d2" style="margin-top:24px">
      <div class="col">
        <h3 style="color:{p["pu"]};margin-bottom:8px">{col1_title}</h3>
        {_col_items(c1)}
      </div>
      <div class="col">
        <h3 style="color:{p["pu"]};margin-bottom:8px">{col2_title}</h3>
        {_col_items(c2)}
      </div>
    </div>
  </div>
</div>""")

            elif st == "chart":
                cd = _chart_data(headers, rows)
                slide_htmls.append(f"""<div class="slide" data-idx="{si}">
  <div class="slide-content anim">
    <h2 class="d1">{title}</h2>
    {f'<p class="subtitle d2" style="color:{p["mu"]}">{content}</p>' if content else ''}
    <div class="chart-wrap d3" data-chart='{cd}' style="height:360px;margin-top:20px"><canvas></canvas></div>
  </div>
</div>""")

            elif st == "image" and img_src:
                slide_htmls.append(f"""<div class="slide" data-idx="{si}">
  <div class="slide-content anim">
    <h2 class="d1">{title}</h2>
    <div class="d2" style="text-align:center;margin-top:20px">
      <img src="{img_src}" style="max-width:100%;max-height:60vh;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.12)">
    </div>
    {f'<p class="d3" style="color:{p["mu"]};text-align:center;margin-top:12px">{content}</p>' if content else ''}
  </div>
</div>""")

            else:  # content / table
                body = ""
                if items:
                    lis = "".join(f"<li>{i}</li>" for i in items)
                    body = f'<ul class="d2">{lis}</ul>'
                elif content:
                    body = f'<p class="d2" style="line-height:1.8;max-width:800px">{content}</p>'
                tbl = _table_html(headers, rows) if headers and rows else ""
                slide_htmls.append(f"""<div class="slide" data-idx="{si}">
  <div class="slide-content anim">
    <h2 class="d1">{title}</h2>
    {body}
    {f'<div class="d3" style="margin-top:20px">{tbl}</div>' if tbl else ''}
  </div>
</div>""")

        slides_js = "\n".join(slide_htmls)
        title_text = d.get("title", "Presentazione")

        # ── Sentry SVG paths ──
        sentry_glyph_path = '<path d="M68.5 55.9c2.3 4 0 8.9-3.9 10.8l-9.8 5.6c-1.9 1.1-4.2.7-5.6-.9L23.6 41.1c-3.3-3.7-8.6-5.1-13.6-4.2L5.7 53.1c-.8 2.4.5 5 2.9 5.8l10.2 3.5c1.4.5 2.3 1.9 2.3 3.4v11.2c0 2-1.6 3.6-3.6 3.6H2.6C1.2 80.6 0 79.4 0 77.9V44.8c0-.4.1-.9.2-1.3L14.1 3.5C14.9 1.2 17.6 0 20 0s5.1 1.2 5.9 3.5l13.9 40c.1.4.2.9.2 1.3v11.5c0 2-1.6 3.6-3.6 3.6h-5.9c-2 0-3.6-1.6-3.6-3.6v-5.8c0-.4.3-.7.7-.7h1.1c.4 0 .7.3.7.7v3.5c0 .4.3.7.7.7h4.8c.4 0 .7-.3.7-.7V49.7c0-.1 0-.3-.1-.4L24.2 10.6c-.1-.4-.5-.6-.9-.4-.1 0-.1.1-.2.2L9.7 49.2c-.1.2 0 .5.2.6.1 0 .2.1.3.1H26c.4 0 .7-.3.7-.7v-2.3c0-.4-.3-.7-.7-.7h-9.8c-.4 0-.7-.3-.7-.7v-1.4c0-.4.3-.7.7-.7h12.2c.4 0 .7.3.7.7v7.8c0 2-1.6 3.6-3.6 3.6h-10c-2 0-3.6-1.6-3.6-3.6v-5.8c0-2 1.6-3.6 3.6-3.6h5.8c.4 0 .7.3.7.7v1.4c0 .4-.3.7-.7.7h-5.8c-.9 0-1.6.7-1.6 1.6v5.8c0 .9.7 1.6 1.6 1.6h10c.9 0 1.6-.7 1.6-1.6v-5.7c0-.1 0-.3-.1-.4L27.7 37c-1.9-3.5-1.1-7.9 1.9-10.5l5.5-4.8c.8-.7 1.3-1.8 1.2-2.9-.1-1.5-1.1-2.7-2.5-3.3-1.2-.5-2.6-.3-3.6.6l-3.6 3.3c-.3.3-.8.2-1.1-.1-.1-.1-.1-.2-.2-.3L40.4 5.7c1-1.7 2.8-2.8 4.9-2.8s3.9 1.1 4.9 2.8l24.1 42c.1.2.2.5.2.7v22.8c0 1.5-1.2 2.7-2.7 2.7h-7.5c-1.5 0-2.7-1.2-2.7-2.7V73c0-.4.3-.7.7-.7h1.4c.4 0 .7.3.7.7v4.9c0 .4.3.7.7.7h4.8c.4 0 .7-.3.7-.7V56.2c0-.1 0-.3-.1-.4L48.4 18.5c-.1-.3-.5-.4-.8-.2-.1 0-.1.1-.2.2L33.5 53.3c-.1.2 0 .4.2.5.1 0 .2.1.3.1h13.2c.4 0 .7.3.7.7v1.4c0 .4-.3.7-.7.7H32c-1.5 0-2.7-1.2-2.7-2.7v-5.8c0-1.5 1.2-2.7 2.7-2.7h6.9c.4 0 .7-.3.7-.7v-1.4c0-.4-.3-.7-.7-.7h-6.9c-2.7 0-4.9 2.2-4.9 4.9v5.8c0 2.7 2.2 4.9 4.9 4.9h16.4c.4 0 .7.3.7.7v2.3c0 1.5-1.2 2.7-2.7 2.7H40c-.4 0-.7.3-.7.7v1.4c0 .4.3.7.7.7h9.8c.4 0 .7-.3.7-.7V75c0-.4.3-.7.7-.7h2.3c.4 0 .7.3.7.7v8c0 2.7-2.2 4.9-4.9 4.9H28.3c-2.7 0-4.9-2.2-4.9-4.9V64.8c0-.1 0-.3-.1-.4l-2-5.8c-.2-.7-.2-1.5 0-2.2L36.5 1.4C37.2-.5 39.4-.5 40 0h.1c.6-.5 2.8-.5 3.5 1.4l28.6 78.8c.5 1.4-.2 2.9-1.6 3.4-.3.1-.6.2-.9.2h-9c-1.5 0-2.7-1.2-2.7-2.7v-1.4c0-.4.3-.7.7-.7h1.1c.4 0 .7.3.7.7v1.4c0 .4.3.7.7.7h6.3c.4 0 .8-.2.9-.6.1-.2.1-.4 0-.6L42.9 7.3c-.8-2.2-4.1-2.2-4.9 0L14 52.3c-.1.3 0 .6.3.8l.2.1c.3.2.7.2 1.1 0l6.4-2.3c.4-.1.8-.2 1.2-.2 1.5 0 2.7 1.2 2.7 2.7v4.9c0 1.5-1.2 2.7-2.7 2.7H11.8c-1.5 0-2.7-1.2-2.7-2.7v-3.4c0-1.5 1.2-2.7 2.7-2.7h.6v1.4h-.6c-.4 0-.7.3-.7.7v3.4c0 .4.3.7.7.7h11.1c.4 0 .7-.3.7-.7v-4.9c0-.4-.3-.7-.7-.7h-.1l-6.4 2.3c-1.1.4-2.3.2-3.2-.5-.8-.6-1.3-1.6-1.3-2.6-.1-.9.3-1.8 1.1-2.4l14.1-11.9c1.4-1.2 3.5-1.2 4.9 0l16.5 14.2c.8.7 1.3 1.7 1.3 2.7 0 1-.4 2-1.2 2.7l-5.5 4.8c-1.4 1.2-3.5 1.2-4.9 0L27.8 41.6" fill="currentColor"/>'

        full_html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title_text}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ height:100%; overflow:hidden; font-family:'Rubik',system-ui,-apple-system,sans-serif; }}
body {{ background:{p["bg"]}; color:{p["dk"]}; font-size:0.9rem; line-height:1.7; }}
.progress {{ position:fixed; top:0; left:0; height:3px; background:{p["pu"]}; transition:width 0.35s ease; z-index:10; }}
.slide {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; opacity:0; pointer-events:none; transition:opacity 0.45s ease; }}
.slide.active {{ opacity:1; pointer-events:auto; }}
.slide-content {{ width:100%; max-width:920px; padding:60px 48px 100px; }}
h1 {{ letter-spacing:-0.03em; line-height:1.2; }}
h2 {{ font-size:1.55rem; font-weight:600; letter-spacing:-0.02em; margin-bottom:16px; }}
.cols {{ display:flex; gap:40px; }}
.col {{ flex:1; }}
ul {{ list-style:none; padding:0; }}
li {{ padding:6px 0 6px 20px; position:relative; }}
li::before {{ content:'▸'; position:absolute; left:0; color:{p["pu"]}; }}
.compare {{ width:100%; border-collapse:collapse; font-size:0.85rem; }}
.compare th {{ text-align:left; font-weight:600; padding:10px 14px; border-bottom:2px solid {p["bd"]}; }}
.compare td {{ padding:10px 14px; border-bottom:1px solid {p["bd"]}40; }}
.chart-wrap {{ position:relative; }}
.chart-wrap canvas {{ width:100% !important; height:100% !important; }}
.tag {{ display:inline-block; font-size:0.66rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; padding:4px 10px; border-radius:4px; margin-bottom:8px; background:{p["pb"]}; color:{p["pu"]}; }}
.glyph-wm {{ position:fixed; top:20px; left:24px; z-index:8; opacity:0.12; pointer-events:none; display:flex; align-items:center; gap:10px; }}
.glyph-wm svg {{ width:28px; height:26px; fill:currentColor; }}
.glyph-wm span {{ font-size:0.85rem; font-weight:600; letter-spacing:-0.01em; }}
nav {{ position:fixed; bottom:0; left:0; right:0; display:flex; align-items:center; justify-content:center; gap:16px; padding:14px; z-index:5; }}
nav button {{ background:none; border:none; cursor:pointer; font-family:inherit; font-size:0.8rem; color:{p["mu"]}; padding:4px 8px; transition:color 0.2s; }}
nav button:hover {{ color:{p["dk"]}; }}
nav button:disabled {{ opacity:0.2; cursor:default; }}
.dots {{ display:flex; gap:6px; }}
.dot {{ width:6px; height:6px; border-radius:50%; background:{p["bd"]}; cursor:pointer; transition:background 0.2s; }}
.dot.on {{ background:{p["pu"]}; }}
.slide-num {{ font-size:0.75rem; color:{p["mu"]}; font-variant-numeric:tabular-nums; }}
@keyframes fadeUp {{ from {{ opacity:0; transform:translateY(16px); }} to {{ opacity:1; transform:translateY(0); }} }}
.anim h1,.anim h2,.anim .subtitle,.anim .cols,.anim ul,.anim p,.anim .compare,.anim .chart-wrap,.anim .tag {{ opacity:0; animation:fadeUp 0.5s ease both; }}
.d1 {{ animation-delay:0.1s !important; }} .d2 {{ animation-delay:0.2s !important; }} .d3 {{ animation-delay:0.3s !important; }}
</style>
</head>
<body>
<div class="progress" id="progress"></div>
<div class="glyph-wm" id="watermark" style="display:none"><svg viewBox="0 0 80 80" width="28" height="26">{sentry_glyph_path}</svg><span>{title_text}</span></div>
<div id="slides-container">{slides_js}</div>
<nav>
  <button id="prevBtn" disabled>←</button>
  <div class="dots" id="dots"></div>
  <button id="nextBtn">→</button>
  <span class="slide-num" id="slideNum">1 / {len(slide_htmls)}</span>
</nav>
<script>
const TOTAL = {len(slide_htmls)};
let cur = 0, touchX = 0, touchY = 0, wheelTimer = null;
const slides = document.querySelectorAll('.slide');
const dots = document.getElementById('dots');
const progress = document.getElementById('progress');
const wm = document.getElementById('watermark');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const slideNum = document.getElementById('slideNum');
for(let i=0;i<TOTAL;i++){{const d=document.createElement('div');d.className='dot'+(i===0?' on':'');d.addEventListener('click',()=>go(i));dots.appendChild(d);}}
function go(n){{if(n<0||n>=TOTAL)return;cur=n;slides.forEach((s,i)=>{{s.classList.toggle('active',i===cur);const c=s.querySelector('.slide-content');if(c){{c.classList.remove('anim');void c.offsetWidth;c.classList.add('anim');}}}});dots.querySelectorAll('.dot').forEach((d,i)=>d.classList.toggle('on',i===cur));progress.style.width=((cur+1)/TOTAL*100)+'%';wm.style.display=cur>0?'flex':'none';prevBtn.disabled=cur===0;nextBtn.disabled=cur===TOTAL-1;slideNum.textContent=(cur+1)+' / '+TOTAL;}}

// ── Keyboard navigation ──
document.addEventListener('keydown',e=>{{if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;if(e.key==='ArrowRight'||e.key===' '||e.key==='ArrowDown'){{e.preventDefault();go(cur+1);}}if(e.key==='ArrowLeft'||e.key==='ArrowUp'){{e.preventDefault();go(cur-1);}}}});

// ── Mouse wheel / trackpad scrolling ──
document.addEventListener('wheel',e=>{{if(e.target.closest('.chart-wrap')||e.target.closest('.slide-content')?.scrollHeight>e.target.closest('.slide-content')?.clientHeight)return;e.preventDefault();if(wheelTimer)clearTimeout(wheelTimer);wheelTimer=setTimeout(()=>{{if(e.deltaY>0)go(cur+1);else go(cur-1);}},80);}},{{passive:false}});

// ── Touch swipe ──
document.addEventListener('touchstart',e=>{{touchX=e.changedTouches[0].screenX;touchY=e.changedTouches[0].screenY;}},{{passive:true}});
document.addEventListener('touchend',e=>{{const dx=e.changedTouches[0].screenX-touchX,dy=e.changedTouches[0].screenY-touchY;if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.5){{go(dx<0?cur+1:cur-1);}}else if(Math.abs(dy)>50&&Math.abs(dy)>Math.abs(dx)*1.5){{go(dy<0?cur+1:cur-1);}}}},{{passive:true}});

// ── Area chart variant with gradients ──
function drawGradient(ctx,x0,y0,x1,y1,color){{
  const g=ctx.createLinearGradient(x0,y0,x1,y1);
  g.addColorStop(0,color);g.addColorStop(1,color+'00');
  return g;
}}

// ── Charts via canvas (enhanced) ──
const CHART_COLORS = {json.dumps(p["cat"])};
const GRID_COLOR = "{p['bd']}", TXT_COLOR = "{p['mu']}", AXIS_COLOR = "{p['bd']}80", ACCENT_COLOR = "{p['pu']}";
document.querySelectorAll('[data-chart]').forEach(el => {{
  try {{
    const cd = JSON.parse(el.dataset.chart);
    const canvas = el.querySelector('canvas');
    if (!canvas || !cd.labels || !cd.series) return;
    const ctx = canvas.getContext('2d');
    const W = el.clientWidth || 880, H = 360;
    canvas.width = W * 2; canvas.height = H * 2;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    ctx.scale(2,2);
    const pad = {{top:30,bottom:50,left:60,right:30}};
    const cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
    const allVals = cd.series.flatMap(s=>s.data);
    const maxVal = Math.max(...allVals,1);
    const step = cw / Math.max(cd.labels.length-1,1);

    // subtle grid
    ctx.strokeStyle = AXIS_COLOR; ctx.lineWidth = 0.5;
    for(let i=0;i<=4;i++){{const y=pad.top+ch-ch*i/4;ctx.beginPath();ctx.moveTo(pad.left,y);ctx.lineTo(W-pad.right,y);ctx.stroke();ctx.fillStyle=TXT_COLOR;ctx.font='10px Rubik,sans-serif';ctx.textAlign='right';ctx.fillText(Math.round(maxVal*i/4),pad.left-8,y+4);}}

    // axes
    ctx.strokeStyle = AXIS_COLOR; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.left,pad.top); ctx.lineTo(pad.left,pad.top+ch); ctx.lineTo(W-pad.right,pad.top+ch); ctx.stroke();

    if (cd.type === 'bar') {{
      const bw = step * 0.55 / cd.series.length;
      cd.series.forEach((s,si) => {{
        s.data.forEach((v,i) => {{
          const x = pad.left + i*step - bw*cd.series.length/2 + si*bw + bw/2;
          const h = (v/maxVal)*ch;
          const grd = ctx.createLinearGradient(0,pad.top+ch-h,0,pad.top+ch);
          grd.addColorStop(0,s.color);grd.addColorStop(1,s.color+'80');
          ctx.fillStyle = grd;
          ctx.beginPath();ctx.roundRect(x-bw/2,pad.top+ch-h,bw-1,h,{{upperLeft:3,upperRight:3}});ctx.fill();
        }});
      }});
    }} else if (cd.type === 'area') {{
      cd.series.forEach((s,si) => {{
        ctx.beginPath();
        s.data.forEach((v,i) => {{const x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}});
        ctx.lineTo(pad.left+(s.data.length-1)*step,pad.top+ch);ctx.lineTo(pad.left,pad.top+ch);ctx.closePath();
        const grd=createGradient(ctx,0,pad.top,0,pad.top+ch,s.color);
        ctx.fillStyle=grd;ctx.fill();
        ctx.strokeStyle=s.color;ctx.lineWidth=2.5;ctx.stroke();
        s.data.forEach((v,i) => {{const x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x,y,3.5,0,Math.PI*2);ctx.fill();ctx.strokeStyle=s.color;ctx.lineWidth=2;ctx.stroke();}});
      }});
    }} else if (cd.type === 'pie') {{
      const cx = W/2, cy = H/2-20, r = Math.min(cw,ch)/2 - 10;
      const total = allVals.reduce((a,b)=>a+b,0);
      let startAngle = -Math.PI/2;
      cd.series.forEach((s,i) => {{
        const sliceAngle = (allVals[i]/total)*Math.PI*2;
        ctx.fillStyle = s.color;
        ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy,r,startAngle,startAngle+sliceAngle); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
        const mid = startAngle + sliceAngle/2;
        const lx = cx + Math.cos(mid)*r*0.7, ly = cy + Math.sin(mid)*r*0.7;
        ctx.fillStyle = '#fff'; ctx.font = 'bold 12px Rubik,sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(Math.round(allVals[i]/total*100)+'%', lx, ly);
        startAngle += sliceAngle;
      }});
      let ly = pad.top + ch + 4;
      cd.series.forEach((s,i) => {{ctx.fillStyle=s.color;ctx.fillRect(pad.left+60,ly,10,10);ctx.fillStyle=TXT_COLOR;ctx.font='11px Rubik,sans-serif';ctx.textAlign='left';ctx.fillText(s.name,pad.left+60+16,ly+9);ly+=16;}});
    }} else {{ // line
      cd.series.forEach((s,si) => {{
        ctx.strokeStyle = s.color; ctx.lineWidth = 2.5; ctx.beginPath();
        s.data.forEach((v,i) => {{const x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}}); ctx.stroke();
        s.data.forEach((v,i) => {{const x=pad.left+i*step,y=pad.top+ch-(v/maxVal)*ch;ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.strokeStyle=s.color;ctx.lineWidth=2;ctx.stroke();}});
      }});
    }}

    ctx.fillStyle = TXT_COLOR; ctx.font = '10px Rubik,sans-serif'; ctx.textAlign = 'center';
    cd.labels.forEach((l,i) => {{const x=pad.left+i*step;ctx.fillText(l,x,pad.top+ch+18);}});
  }} catch(e) {{ console.error('Chart error:',e); }}
}});
go(0);
</script>
</body>
</html>"""

        if not output:
            output = str(DL_DIR / f"presentation_{int(time.time())}.html")
        else:
            output = str(Path(output))
        Path(output).write_text(full_html, encoding="utf-8")
        self._open(output)
        return output, self._dl_url(output)


    def make_presenton_html(self, data, slides=None, output=None, theme=None):
        """Genera HTML presentazione con template Presenton-style.
        Supporta tutti i temi: corporate, dark, nature, sunset, ocean, midnight.
        Se slides è None, tenta la generazione AI dal topic.
        """
        from presenton_engine import render_html, generate_slides, HTML_TEMPLATES

        d = self._sanitize(data)
        title = d.get("title", "Presentazione")
        author = d.get("author", "J.A.R.V.I.S")
        theme = theme or d.get("theme", "corporate")
        if theme not in HTML_TEMPLATES:
            theme = "corporate"

        slides_list = slides or []
        if isinstance(slides_list, str):
            try:
                slides_list = json.loads(slides_list)
            except:
                slides_list = []

        if not slides_list:
            topic = d.get("text", "") or d.get("topic", "") or title
            if topic:
                n_slides = d.get("n_slides", 8)
                language = d.get("language", "Italian")
                tone = d.get("tone", "default")
                instructions = d.get("instructions", "")
                slides_list = generate_slides(
                    topic=topic,
                    n_slides=n_slides,
                    language=language,
                    tone=tone,
                    instructions=instructions
                )
            if not slides_list:
                slides_list = [
                    {"type": "title", "title": title, "subtitle": "Generata da J.A.R.V.I.S"},
                    {"type": "content", "title": "Introduzione", "items": ["Contenuto in fase di generazione"]},
                    {"type": "thank_you", "title": "Grazie!", "subtitle": "Domande?"}
                ]

        full_html = render_html(d, slides_list, theme=theme, title=title, author=author)

        if not output:
            output = str(DL_DIR / f"presentation_{int(time.time())}.html")
        else:
            output = str(Path(output))
        Path(output).write_text(full_html, encoding="utf-8")
        self._open(output)
        return output, self._dl_url(output)


docgen = DocGenerator()
