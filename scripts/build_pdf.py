"""Bangun PDF jawaban dan ERD; sumber narasi di docs/jawaban.md."""
from pathlib import Path
import json
import re
import textwrap
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Preformatted,Table,TableStyle,Image,Flowable
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Polygon
from reportlab.graphics import renderSVG

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
META=json.loads((ROOT/'submission.json').read_text(encoding='utf-8'))
DEST=ROOT/'Jawaban_UTS_Zidan.pdf'
W,H=A4
WIDTH=W-90
BLUE=colors.HexColor('#15334A'); MUTED=colors.HexColor('#516273'); GRID=colors.HexColor('#D9D9D9')
regular='Helvetica';bold='Helvetica-Bold';mono='Courier'
fonts=Path('C:/Windows/Fonts')
if (fonts/'arial.ttf').exists():
    pdfmetrics.registerFont(TTFont('Body',str(fonts/'arial.ttf')))
    pdfmetrics.registerFont(TTFont('BodyBold',str(fonts/'arialbd.ttf')))
    regular='Body';bold='BodyBold'
if (fonts/'consola.ttf').exists():
    pdfmetrics.registerFont(TTFont('Code',str(fonts/'consola.ttf')));mono='Code'

BODY=ParagraphStyle('Body',fontName=regular,fontSize=10.1,leading=14.6,spaceAfter=8,textColor=colors.black)
H1=ParagraphStyle('H1',parent=BODY,fontName=bold,fontSize=19,leading=24,spaceAfter=15,keepWithNext=True)
H2=ParagraphStyle('H2',parent=BODY,fontName=bold,fontSize=11.8,leading=16,spaceBefore=7,spaceAfter=7,keepWithNext=True)
SMALL=ParagraphStyle('Small',parent=BODY,fontSize=8.5,leading=11.5)
CODE=ParagraphStyle('Code',fontName=mono,fontSize=7.8,leading=9.8,spaceBefore=6,spaceAfter=9)


def text(value):
    value=escape(value)
    # URL menyertakan tautan klik; pemenggalan kata panjang diatur Paragraph.
    value=re.sub(r'(https?://[^\s]+)',lambda m:f'<link href="{m.group(1)}" color="#205C80">{m.group(1)}</link>',value)
    value=re.sub(r'`([^`]+)`',lambda m:f'<font name="{mono}" size="9">{m.group(1)}</font>',value)
    return value


def para(value,style=BODY): return Paragraph(text(value),style)


class LinkField(Flowable):
    def __init__(self): super().__init__(); self.width=WIDTH;self.height=60
    def draw(self):
        c=self.canv
        url=META.get('repository_or_drive_url','')
        c.setFont(regular,8.5);c.setFillColor(MUTED)
        c.drawString(0,46,'URL repositori publik atau Google Drive')
        c.acroForm.textfield(name='tautan_pengumpulan',tooltip='Tautan repo atau Drive artefak jawaban',
          value=url,x=0,y=10,width=WIDTH,height=28,relative=True,borderWidth=.7,
          borderColor=GRID,fillColor=colors.white,textColor=colors.black,
          fontName='Helvetica',fontSize=9,maxlen=1000,forceBorder=True)


def erd():
    d=Drawing(505,265)
    def box(x,y,title,fields,w=235,h=119):
        d.add(Rect(x,y,w,h,fillColor=colors.white,strokeColor=GRID))
        d.add(Rect(x,y+h-26,w,26,fillColor=colors.HexColor('#E7EEF4'),strokeColor=GRID))
        d.add(String(x+10,y+h-17,title,fontName=bold,fontSize=10,fillColor=BLUE))
        for i,f in enumerate(fields):
            d.add(String(x+10,y+h-43-i*14,f,fontName=regular,fontSize=9,fillColor=colors.black))
    box(0,146,'journal_headers',['PK  id','tanggal, nomor referensi UNIQUE','deskripsi, status_posting','reversal_of FK ke jurnal asal','created_by, created_at, checksum'])
    box(270,146,'chart_of_accounts',['PK  account_id','kode akun UNIQUE, nama akun','saldo normal D / C','klasifikasi laporan','is_cash'])
    box(135,0,'journal_lines',['PK  id','FK  header_id','FK  account_id','debit NUMERIC(18,2)','credit NUMERIC(18,2)'])
    for x,edge in [(117,135),(388,370)]:
        d.add(Line(x,146,x,61,strokeColor=BLUE,strokeWidth=1))
        d.add(Line(x,61,edge,61,strokeColor=BLUE,strokeWidth=1))
        d.add(String(x+5,132,'1',fontName=bold,fontSize=9))
        d.add(String(x-30 if x==117 else x+5,67,'0..N',fontName=bold,fontSize=9))
    renderSVG.drawToFile(d,str(DOCS/'erd.svg'))
    return d


def code_block(code,compact=False):
    # Hanya bungkus tampilan, skrip SQL asli tetap menjadi artefak eksekusi.
    result=[]
    for line in code.strip().splitlines():
        result.extend(textwrap.wrap(line,width=103,subsequent_indent='    ',
                      break_long_words=False,break_on_hyphens=False,replace_whitespace=False) or [''])
    style=CODE
    if compact: style=ParagraphStyle('CompactCode',parent=CODE,fontSize=7.5,leading=9.3)
    return Preformatted('\n'.join(result),style)


def table(rows):
    parsed=[[para(c.strip(),SMALL) for c in row.strip().strip('|').split('|')] for row in rows if not re.match(r'^\|\s*[-: ]+\|',row)]
    n=len(parsed[0]); widths=([WIDTH*.31,WIDTH*.69] if n==2 else [WIDTH/n]*n)
    t=Table(parsed,colWidths=widths,hAlign='LEFT',repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EEF4')),
       ('GRID',(0,0),(-1,-1),.5,GRID),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
       ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
       ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t


def footer(c,doc):
    c.saveState()
    c.setTitle('Jawaban UTS Pemrograman Akuntansi - Zidan Anargya Elian Mulyono')
    c.setAuthor(META['nama'])
    c.setFont(regular,8);c.setFillColor(MUTED)
    c.drawString(45,27,'Zidan Anargya Elian Mulyono | 12030124130141')
    c.drawRightString(W-45,27,str(doc.page))
    c.restoreState()


def build():
    lines=(DOCS/'jawaban.md').read_text(encoding='utf-8').splitlines()
    story=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1;continue
        if line=='<!-- PAGE -->': story.append(PageBreak());i+=1;continue
        if line=='[[LINK_FORM]]': story.append(LinkField());i+=1;continue
        if line=='[[ERD]]':story.extend([erd(),Spacer(1,12)]);i+=1;continue
        if line=='[[DDL_CORE]]':
            sql=(ROOT/'sql'/'001_schema.sql').read_text(encoding='utf-8')
            sql=sql[sql.index('CREATE TABLE chart_of_accounts'):sql.index('CREATE INDEX journal_lines_header_idx')]
            story.append(code_block(sql,compact=True));i+=1;continue
        if line=='[[TRIGGER]]':
            sql=(ROOT/'sql'/'002_business_logic.sql').read_text(encoding='utf-8')
            sql=sql[sql.index('CREATE FUNCTION trg_update_stock_and_journal'):sql.index('CREATE FUNCTION record_inventory')]
            story.append(code_block(sql,compact=True));i+=1;continue
        if line=='[[RESULTS]]':
            report=json.loads((DOCS/'hasil_uji.json').read_text(encoding='utf-8'))
            story.append(para(f"{report['tests']} pengujian dijalankan; {report['failures']} gagal; {report['errors']} error; {report['skipped']} dilewati.",H2))
            story.append(para('Waktu eksekusi UTC: '+report['run_at_utc'],SMALL));i+=1;continue
        if line.startswith('[[IMAGE:'):
            path=DOCS/line[8:-2]
            if path.exists():
                im=Image(str(path));scale=min(WIDTH/im.imageWidth,315/im.imageHeight)
                im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale
                im.hAlign='CENTER';story.extend([Spacer(1,6),im,Spacer(1,9)])
            i+=1;continue
        if line.startswith('```'):
            block=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
            story.append(code_block('\n'.join(block)));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i]);i+=1
            story.extend([table(rows),Spacer(1,10)]);continue
        if line.startswith('# '):story.append(para(line[2:],H1));i+=1;continue
        if line.startswith('## '):story.append(para(line[3:],H2));i+=1;continue
        parts=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','[[','<!--','|','```')):
            parts.append(lines[i].strip());i+=1
        story.append(para(' '.join(parts)))
    doc=SimpleDocTemplate(str(DEST),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=44,bottomMargin=47,
                          title='Jawaban UTS Pemrograman Akuntansi',author=META['nama'])
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(DEST)


if __name__=='__main__':build()
