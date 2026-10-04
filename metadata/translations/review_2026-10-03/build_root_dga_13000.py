"""Exact frozen-ID readings of 404 archival primary titles, not fuzzy matching."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
rows = json.loads((ROOT/'work/title-review/2026-10-03/archive-review/root-dga-13000-14999-unresolved.json').read_text())
readings = {}
for line in (HERE/'root_dga_13000_readings.tsv').read_text().splitlines():
    ident, value = line.split('|', 1)
    if 'dga:'+ident in readings:
        raise ValueError('duplicate '+ident)
    readings['dga:'+ident] = value
if set(readings) != {row['id'] for row in rows}:
    raise ValueError('exact frozen ID coverage drift')

retentions = {
    '14887': 'Sacro-monte在这份书目中是带连字符的地名式题名；不据字面“圣山”猜测其地理对应或另造中文专名，保留原题及作品55第5号。',
    '14527': 'Segovia是原作的人名式题名，不改造成某种乐曲体裁；保留原名和作品29。',
    '13186': 'Muances既可能含旧音乐技术术语又可能是作品命名；来源未说明具体语境，不用“变化”替代题名，保留原文及作品52。',
    '14896': 'Mari-gloria是连字符连接的专名式题名；无法确认其中文专名，保留来源拼写及吉他改编信息。',
    '14538': '来源写作Sonãndo而非确定的Soñando或Sonando；不同拼写会改变词义，不能猜补损坏字母，保留原题。',
    '14537': '来源题名Cantço del lladre含转录损伤；不能仅凭近似曲名改写成另一规范加泰罗尼亚拼写，保留原词和民间曲调信息。',
    '14277': 'Alpujarreña是地域式专名题名；来源未确定其指人物还是地域风格，不推断作者命名对象，保留原文。',
    '14072': '原题Espa{228)na含明显编码或转录损伤；没有相应原页字形依据，不猜补标题字符，保留现存原题与舞曲标记。',
    '13734': 'Giulianate是人名衍生的合集名；不把它硬造为中文音译，保留原文和作品148。',
    '13485': 'Abreuana是人名式衍生标题；原题未解释命名意图，不创造生硬音译，采用来源原文。',
}
common_refs = {
    '14207': ['https://www.ricordi.com/en-US/Critical-Editions/Verdi-Giuseppe-Critical-Editions/Verdi-Giuseppe-WGV/Verdi-Nabucodonosor.aspx', 'https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/17-18.pdf'],
    '14208': ['https://www.chncpa.org/subsite/chn2016/index.html'],
    '14204': ['https://www.chncpa.org/subsite/chn2016/index.html'],
    '13276': ['https://www.chncpa.org/subsite/chn2016/index.html'],
    '14210': ['https://www.lcsd.gov.hk/CE/CulturalService/Programme/pdf/program_note2_1836_1.pdf'],
    '14196': ['https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/18-19.pdf'],
    '14190': ['https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/17-18.pdf'],
    '14767': ['https://fr.wikisource.org/wiki/Que_ne_suis-je_la_foug%C3%A8re'],
    '14004': ['https://m.chncpa.org/gywm0118_6878/jynb/202201/P020220302556627039800.pdf'],
}
entries = []
for row in rows:
    ident = row['id'].split(':')[1]
    retained = ident in retentions
    value = readings[row['id']]
    entries.append({
        'id': row['id'], 'original': row['original'], 'original_composer': row['composer'],
        'display_original': row['display_original'],
        'zh': '《'+(row['original'] if retained else value)+'》',
        'display_zh': '《'+(row['display_original'] if retained else value)+'》',
        'status': 'retained' if retained else 'reference',
        'basis': 'exact_archive_original_retention_2026_10_03' if retained else 'exact_primary_title_semantic_reading_2026_10_03',
        'reason': retentions[ident] if retained else '逐项审读主标题、体裁、乐器关系、作品号与册次；引用曲名无法确认中文专名时保留原词，出版、献辞及责任说明保存在完整来源原文。参考题名不据此认证谱面编制或改写来源署名。',
        'source_refs': [row['source_url']]+common_refs.get(ident, []),
        'review_method': 'exact_original_retention' if retained else 'exact_primary_title_reading',
        'reviewer': 'Codex 2026-10-03',
    })
(HERE/'root_dga_13000_supplement.json').write_text(json.dumps({'schema_version': 1, 'entries': entries},ensure_ascii=False,indent=2)+'\n')
print(len(entries), dict(Counter(row['status'] for row in entries)))
