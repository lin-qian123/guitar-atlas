#!/usr/bin/env python
"""Build resumable, ID-keyed ClassClef reference-title translations.

The source catalog is read-only. Machine drafts and review shards stay in work/;
only the per-record translation asset under metadata/translations/ is published.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://clients5.google.com/translate_a/t"
STATUSES = {"reviewed", "reference", "retained", "machine", "untranslated"}
POLICY = ("Chinese names are reference display/search data keyed by exact ClassClef record ID. "
          "Original titles and source identities are unchanged. reviewed denotes an established "
          "name supported by recorded evidence; reference denotes a checked reference rendering; "
          "machine denotes an unreviewed machine draft; retained records an intentional original-"
          "title retention with its reason; untranslated denotes an unresolved translation.")

# Reviewed as musical vocabulary, not as an identification of a work or edition.
# A formula is accepted only when every alphabetic token is consumed by these
# terms, an explicit key/catalog number, a Roman numeral, or a quoted arranger.
MUSIC_TERMS = {
    "andante sostenuto": "绵延的行板", "andante cantabile": "如歌的行板",
    "andante con moto": "流动的行板", "andante religioso": "虔诚的行板",
    "andante grave": "庄重的行板", "allegro moderato": "中庸的快板",
    "allegro maestoso": "庄严的快板", "allegro giusto": "适中的快板",
    "allegro brillante": "辉煌的快板", "allegro assai": "很快的快板",
    "allegro con brio": "有活力的快板", "allegro non troppo": "不过分的快板",
    "allegro vivace": "活泼的快板", "allegro solemne": "庄严的快板",
    "allegro alla francese": "法国风格的快板", "poco allegretto": "稍快板",
    "poco adagio": "稍慢的柔板", "molto allegro": "很快的快板",
    "meno mosso": "稍慢", "piu mosso": "稍快", "con moto": "流动地",
    "con brio": "有活力地", "con espressione": "富于表情地",
    "estudio de concierto": "音乐会练习曲", "etude de concert": "音乐会练习曲",
    "concert etude": "音乐会练习曲", "estudio del ligado": "连音练习曲",
    "estudio en arpegio": "琶音练习曲", "estudio para ambas manos": "双手练习曲",
    "estudio en imitaciones": "模仿练习曲", "estudio vals": "圆舞曲练习曲",
    "vals estudio": "圆舞曲练习曲", "pequeno estudio": "小练习曲",
    "sonata para guitarra": "吉他奏鸣曲", "metodo de guitarra": "吉他教程",
    "metodo primera": "初级教程", "moto perpetuo": "无穷动",
    "theme and variations": "主题与变奏", "tema con variazioni": "主题与变奏",
    "gavotte en rondeau": "回旋加沃特舞曲", "petite valse": "小圆舞曲",
    "little waltz": "小圆舞曲", "spanish dance": "西班牙舞曲",
    "danza espanola": "西班牙舞曲", "danza espanolas": "西班牙舞曲",
    "violin sonata": "小提琴奏鸣曲", "organ sonata": "管风琴奏鸣曲",
    "cello suite": "大提琴组曲", "lute suite": "鲁特琴组曲",
    "guitar sonata": "吉他奏鸣曲", "guitar duet": "吉他二重奏",
    "sarabande": "萨拉班德舞曲", "sarabanda": "萨拉班德舞曲", "zarabanda": "萨拉班德舞曲",
    "passacaille": "帕萨卡利亚舞曲", "passacaglia": "帕萨卡利亚舞曲", "pasacalle": "帕萨卡利亚舞曲",
    "allemande": "阿勒曼德舞曲", "allemand": "阿勒曼德舞曲", "almain": "阿勒曼德舞曲",
    "courante": "库朗特舞曲", "corrente": "库朗特舞曲", "coranto": "库朗特舞曲",
    "gigue": "吉格舞曲", "giga": "吉格舞曲", "jig": "吉格舞曲",
    "gavotte": "加沃特舞曲", "gavotta": "加沃特舞曲", "gavota": "加沃特舞曲",
    "bourree": "布列舞曲", "bourre": "布列舞曲", "bourrees": "布列舞曲", "bouree": "布列舞曲",
    "loure": "卢尔舞曲", "passepied": "帕斯皮耶舞曲", "rigaudon": "里戈东舞曲",
    "chaconne": "恰空舞曲", "ciaccona": "恰空舞曲", "chacona": "恰空舞曲",
    "spagnoletta": "斯帕尼奥莱塔舞曲", "espanoletta": "西班牙小舞曲", "espanoleta": "西班牙小舞曲",
    "sicilienne": "西西里舞曲", "siciliana": "西西里舞曲", "siciliano": "西西里舞曲",
    "galliard": "加利亚德舞曲", "gagliarda": "加利亚德舞曲", "gallarda": "加利亚德舞曲", "gallardas": "加利亚德舞曲",
    "canarios": "加那利舞曲", "villanos": "维利亚诺舞曲", "villano": "维利亚诺舞曲",
    "pavana": "帕凡舞曲", "pavane": "帕凡舞曲", "pavan": "帕凡舞曲", "pavanna": "帕凡舞曲",
    "polonaise": "波兰舞曲", "polacca": "波兰舞曲", "polonesa": "波兰舞曲", "polonoise": "波兰舞曲",
    "minuet": "小步舞曲", "menuet": "小步舞曲", "minueto": "小步舞曲", "minuetto": "小步舞曲",
    "prelude": "前奏曲", "preludio": "前奏曲", "preludios": "前奏曲", "preludes": "前奏曲", "preludium": "前奏曲",
    "etude": "练习曲", "etudes": "练习曲", "estudio": "练习曲", "estudios": "练习曲",
    "study": "练习曲", "studies": "练习曲", "exercise": "练习", "exercises": "练习", "ejercicio": "练习",
    "sonata": "奏鸣曲", "sonatina": "小奏鸣曲", "sonatine": "小奏鸣曲", "concerto": "协奏曲", "sonate": "奏鸣曲",
    "fantasia": "幻想曲", "fantasie": "幻想曲", "fantasy": "幻想曲", "phantasia": "幻想曲",
    "ricercare": "利切尔卡尔曲", "recercar": "利切尔卡尔曲", "toccata": "托卡塔", "toccatina": "小托卡塔",
    "fugue": "赋格", "fuga": "赋格", "fughetta": "小赋格",
    "rondo": "回旋曲", "rondeau": "回旋曲", "rondino": "小回旋曲",
    "scherzo": "谐谑曲", "scherzino": "小谐谑曲", "caprice": "随想曲", "capriccio": "随想曲",
    "ghiribizzo": "随想小品", "ghiribizzi": "随想小品", "bagatelle": "小品", "bagatela": "小品", "bagatelas": "小品",
    "divertimento": "嬉游曲", "divertissement": "嬉游曲", "humoresque": "幽默曲",
    "nocturne": "夜曲", "nocturno": "夜曲", "berceuse": "摇篮曲",
    "serenade": "小夜曲", "serenata": "小夜曲", "pastorale": "田园曲", "pastoral": "田园曲",
    "romance": "浪漫曲", "romanza": "浪漫曲", "romanzo": "浪漫曲", "romanze": "浪漫曲",
    "cavatina": "卡瓦蒂娜", "aria": "咏叹调", "arietta": "小咏叹调", "air": "曲调",
    "elegie": "挽歌", "elegy": "挽歌", "melodia": "旋律", "melody": "旋律", "song": "歌曲",
    "waltz": "圆舞曲", "waltzes": "圆舞曲", "valse": "圆舞曲", "valses": "圆舞曲", "vals": "圆舞曲",
    "mazurka": "玛祖卡舞曲", "polka": "波尔卡舞曲", "galop": "加洛普舞曲",
    "tango": "探戈", "tangos": "探戈", "milonga": "米隆加", "habanera": "哈巴涅拉舞曲",
    "maxixe": "马希谢舞曲", "choro": "肖罗曲", "choros": "肖罗曲", "samba": "桑巴",
    "fandango": "凡丹戈舞曲", "fandanguillo": "小凡丹戈舞曲", "bolero": "波莱罗舞曲",
    "granadina": "格拉纳迪纳曲", "granadinas": "格拉纳迪纳曲", "petenera": "佩特内拉曲", "peteneras": "佩特内拉曲",
    "sevillana": "塞维利亚纳舞曲", "sevillanas": "塞维利亚纳舞曲", "guajira": "瓜希拉曲", "guajiras": "瓜希拉曲",
    "bulerias": "布莱里亚斯曲", "farruca": "法鲁卡曲", "soleares": "索莱阿曲", "solea": "索莱阿曲",
    "tiento": "蒂恩托曲", "tientos": "蒂恩托曲", "alegrias": "阿莱格里亚斯曲", "rumba": "伦巴",
    "tarantella": "塔兰泰拉舞曲", "tarantelle": "塔兰泰拉舞曲", "tarentelle": "塔兰泰拉舞曲",
    "tyrolienne": "蒂罗尔舞曲", "saltarello": "萨尔塔雷洛舞曲", "branle": "布朗勒舞曲", "volte": "沃尔塔舞曲",
    "march": "进行曲", "marcha": "进行曲", "marche": "进行曲", "marcia": "进行曲",
    "dance": "舞曲", "danza": "舞曲", "danzas": "舞曲", "ballet": "芭蕾舞曲", "balletto": "芭蕾舞曲",
    "suite": "组曲", "partita": "帕蒂塔组曲", "partite": "帕蒂塔组曲",
    "theme": "主题", "tema": "主题", "variations": "变奏曲", "variazioni": "变奏曲", "variation": "变奏",
    "andante": "行板", "andantino": "小行板", "allegro": "快板", "allegretto": "小快板",
    "adagio": "柔板", "adagietto": "小柔板", "largo": "广板", "larghetto": "小广板",
    "lento": "慢板", "lentamente": "缓慢地", "moderato": "中板", "grave": "庄板",
    "presto": "急板", "prestissimo": "最急板", "vivace": "活板", "vivo": "活泼地",
    "maestoso": "庄严地", "cantabile": "如歌地", "sostenuto": "绵延地", "grazioso": "优雅地",
    "brillante": "辉煌地", "espressivo": "富于表情地", "dolce": "柔美地", "tranquillo": "宁静地",
    "triste": "忧伤地", "original": "原作", "originale": "原作", "reprise": "再现",
    "spirituoso": "精神饱满地", "posato": "沉着地", "musette": "风笛舞曲",
    "introduction": "引子", "introduzione": "引子", "finale": "终曲", "coda": "尾声",
    "duet": "二重奏", "duo": "二重奏", "trio": "三重奏", "quartet": "四重奏",
    "guitar": "吉他", "guitarra": "吉他", "guitare": "吉他", "lute": "鲁特琴",
    "violin": "小提琴", "cello": "大提琴", "flute": "长笛", "mandolin": "曼陀林",
    "arpeggio": "琶音", "arpeggios": "琶音", "tremolo": "震音", "tremelo": "震音",
    "scales": "音阶", "scale": "音阶", "escala": "音阶", "chords": "和弦",
    "piece": "小品", "pieces": "小品", "movement": "乐章", "version": "版本",
    "book": "册", "libro": "册", "lesson": "课", "leccion": "课",
    "and": "与", "e": "与", "et": "与", "y": "与", "for": "为", "para": "为",
}


def translate_formula(original):
    text = original
    protected = []
    def hold(value):
        protected.append(value)
        return "〚" + str(len(protected) - 1) + "〛"
    text = re.sub(r"\b(?:BWV|HWV|LS|MS|RV|WeissSW|Op\.?|Opus|Anh|[A-Z])\s*\.?\s*\d+(?:[./:-]\d+)*[a-z]?\b",
                  lambda m: hold(m.group()), text, flags=re.I)
    text = re.sub(r"\b(?:Arranged\s+by|Arr\.?\s*:?\s*(?:by\s+)?)\s*([^\W\d_][^\d()\[\]]*?)(?=[)\]]|$)",
                  lambda m: hold(m.group(1).strip() + " 改编"), text, flags=re.I)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    keys = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}
    def key(m):
        note = keys.get(m.group(1).lower(), m.group(1).upper())
        accidental = {"flat": "降", "b": "降", "sharp": "升", "#": "升", "": ""}[ (m.group(2) or "").lower()]
        mode = {"major": "大调", "majeur": "大调", "mayor": "大调", "minor": "小调", "mineur": "小调", "menor": "小调", "": "调"}[(m.group(3) or "").lower()]
        return hold(accidental + note + mode)
    text = re.sub(r"\b(?:in|en)\s+([A-G]|Do|Re|Mi|Fa|Sol|La|Si)(?:[- ]?(flat|sharp|b|#))?(?:\s+(major|minor|majeur|mineur|mayor|menor))?(?![A-Za-z0-9])", key, text, flags=re.I)
    text = re.sub(r"\b([A-G])(?:[- ]?(flat|sharp|b|#))?\s+(major|minor)\b", key, text, flags=re.I)
    text = re.sub(r"\b(?:in|en)\s+([A-G])(?:m|min)\b", lambda m: hold(m.group(1).upper() + "小调"), text, flags=re.I)
    text = re.sub(r"\b(?:No\.?|Number)\s*(\d+[a-z]?)\b", lambda m: "第" + m.group(1) + "首", text, flags=re.I)
    for word in sorted(MUSIC_TERMS, key=len, reverse=True):
        text = re.sub(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", MUSIC_TERMS[word], text, flags=re.I)
    text = re.sub(r"\b[IVXLCDM]+\b", lambda m: hold(m.group()), text)
    if re.search(r"[A-Za-z]", text):
        return None
    for i, value in enumerate(protected):
        text = text.replace("〚" + str(i) + "〛", value)
    if not re.search(r"[\u3400-\u9fff]", text):
        if re.fullmatch(r"(?:\s*\b(?:BWV|HWV|K|L|LS|H|MS|RV|D|Op\.?|Opus|Anh)\s*\.?\s*\d+(?:[./:-]\d+)*[a-z]?[,; ]*)+", original, re.I):
            text = "作品编号 " + original
        else:
            return None
    text = re.sub(r"\s+", " ", text).strip()
    if set(re.findall(r"\d+", original)) - set(re.findall(r"\d+", text)):
        raise ValueError("formula translation lost a numeric token")
    return text


def formulas(root, workspace):
    entries = {}
    for work in read_works(root):
        translated = translate_formula(work["title_en"])
        if translated:
            entries[work["id"]] = {"original": work["title_en"], "zh": "《" + translated + "》", "status": "reference",
                "basis": "Complete-token musical-terminology formula v2 in scripts/build_classclef_translations.py; no unmatched alphabetic words permitted.",
                "reason": "按音乐体裁、速度术语、明确调性与原题编号逐项构成参考译名；未给出的大小调不补推，原题人名/改编署名和作品编号原样保留。", "aliases_zh": []}
    write_json(workspace / "corrections-formulas.json", {"entries": entries})
    return {"reference_formula_records": len(entries)}


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    part.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_works(root):
    works = read_json(root / "sources/classclef/catalog.json", {})["works"]
    if len({w["id"] for w in works}) != len(works):
        raise ValueError("duplicate source record IDs")
    return works


class Translator:
    def __init__(self, interval):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.stop = threading.Event()

    def batch(self, values):
        query = urllib.parse.urlencode({"client": "dict-chrome-ex", "sl": "auto", "tl": "zh-CN", "q": values}, doseq=True)
        request = urllib.request.Request(ENDPOINT + "?" + query, headers={
            "User-Agent": "GuitarAtlas/0.2 (reference title translation)", "Accept": "application/json"})
        error = "translation request not attempted"
        for attempt in range(3):
            if self.stop.is_set():
                return {"results": [""] * len(values), "error": "translation service access limit; stopped"}
            with self.lock:
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + self.interval
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = json.load(response)
                if not isinstance(payload, list) or len(payload) != len(values):
                    raise ValueError("translation response batch size mismatch")
                results = []
                for item in payload:
                    value = item[0] if isinstance(item, list) and item else item
                    if not isinstance(value, str):
                        raise ValueError("invalid translation result")
                    results.append(re.sub(r"[\x00-\x1f]+", " ", value).strip())
                return {"results": results, "error": ""}
            except urllib.error.HTTPError as exc:
                error = f"HTTP {exc.code} from translation service"
                if exc.code in {401, 403, 429}:
                    self.stop.set()
                    break
            except Exception as exc:
                error = str(exc)
            time.sleep(1 + attempt)
        return {"results": [""] * len(values), "error": error}


def make_batches(values, size=20):
    batch = []
    for value in values:
        if batch and (len(batch) >= size or len(urllib.parse.urlencode({"q": batch + [value]}, doseq=True)) > 6500):
            yield batch
            batch = []
        batch.append(value)
    if batch:
        yield batch


def draft(root, workspace, workers, interval, limit):
    titles = sorted({w["title_en"] for w in read_works(root)}, key=str.casefold)
    path = workspace / "machine-cache.json"
    cache = read_json(path, {"schema_version": 1, "service": ENDPOINT, "entries": {}})
    missing = [t for t in titles if not cache["entries"].get(t, {}).get("translation")]
    if limit:
        missing = missing[:limit]
    batches = list(make_batches(missing))
    client = Translator(interval)
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(client.batch, batch): batch for batch in batches}
        for future in as_completed(pending):
            batch = pending[future]
            result = future.result()
            for title, translation in zip(batch, result["results"]):
                cache["entries"][title] = {"translation": translation, "attempted_at": now(), "error": result["error"]}
            cache["updated_at"] = now()
            write_json(path, cache)
            completed += len(batch)
            print(f"drafts {completed}/{len(missing)}; cached={sum(bool(e.get('translation')) for e in cache['entries'].values())}", flush=True)
    return {"requested": len(missing), "cached": sum(bool(e.get("translation")) for e in cache["entries"].values()),
            "missing": sum(not cache["entries"].get(t, {}).get("translation") for t in titles)}


def shards(root, workspace, count):
    cache = read_json(workspace / "machine-cache.json", {"entries": {}})["entries"]
    works = sorted(read_works(root), key=lambda w: (w["title_en"].casefold(), w["composer_en"].casefold(), w["id"]))
    step = (len(works) + count - 1) // count
    for i in range(count):
        rows = [{"id": w["id"], "original": w["title_en"], "composer_en": w["composer_en"],
                 "source_url": w["source_url"], "draft_zh": cache.get(w["title_en"], {}).get("translation", "")}
                for w in works[i * step:(i + 1) * step]]
        write_json(workspace / f"review-shard-{i + 1}.json", {"schema_version": 1, "rows": rows})
    return {"shards": count, "records": len(works), "workspace": str(workspace)}


def unwrap(value):
    return str(value).strip().removeprefix("《").removesuffix("》").strip()


def display_catalog_labels(value):
    value = re.sub(r"\bOpus\s*(?=\d)", "作品", value, flags=re.I)
    return value


def flags(original, translated):
    issues = []
    if not re.search(r"[\u3400-\u9fff]", translated):
        issues.append("no_chinese")
    source_numbers = {str(int(n)) for n in re.findall(r"\d+", original)}
    translated_numbers = {str(int(n)) for n in re.findall(r"\d+", translated)}
    digits = dict(zip("零〇一二两三四五六七八九", [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
    units = {"十": 10, "百": 100, "千": 1000}
    for number in re.findall(r"[零〇一二两三四五六七八九十百千]+", translated):
        if any(c in units for c in number):
            total, digit = 0, 0
            for char in number:
                if char in units:
                    total += (digit or 1) * units[char]
                    digit = 0
                else:
                    digit = digits[char]
            translated_numbers.add(str(total + digit))
        else:
            translated_numbers.update(str(digits[c]) for c in number)
    if re.search(r"单层(?:或双层)?键盘", translated):
        translated_numbers.add("1")
    if re.search(r"双(?:层键盘|吉他|曼陀林)", translated):
        translated_numbers.add("2")
    if source_numbers - translated_numbers:
        issues.append("numeric_tokens_changed")
    if re.search(r"\b(?:BWV|Op\.?|Opus|RV|K\.?|D\.?)\s*\d", original, re.I):
        identifiers = re.findall(r"\b(?:BWV|Op\.?|Opus|RV|K\.?|D\.?)\s*\d+(?:[./:-]\d+)*", original, re.I)
        def normalized_identifier(value):
            value = re.sub(r"(?:\bOpus|\bOp\.|作品)\s*(?=\d)", "op", value, flags=re.I)
            value = value.casefold().replace(" ", "")
            return re.sub(r"\b(bwv|rv|k|d)\.(?=\d)", r"\1", value)
        if any(normalized_identifier(identifier) not in normalized_identifier(translated) for identifier in identifiers):
            issues.append("catalog_identifier_needs_review")
    return issues


def assemble(root, workspace):
    works = read_works(root)
    asset_path = root / "metadata/translations/classclef_titles_zh.json"
    existing = read_json(asset_path, {"entries": {}})["entries"]
    cache = read_json(workspace / "machine-cache.json", {"entries": {}})["entries"]
    formulas = read_json(workspace / "corrections-formulas.json", {"entries": {}})["entries"]
    corrections = {}
    for path in sorted(workspace.glob("corrections-*.json")):
        if path.name == "corrections-formulas.json":
            continue
        payload = read_json(path, {})
        entries = payload.get("entries", payload)
        for ident, value in entries.items():
            if ident in corrections and corrections[ident] != value:
                raise ValueError(f"conflicting independent corrections: {ident}")
            corrections[ident] = value
    ids = {w["id"] for w in works}
    if set(existing) - ids:
        raise ValueError("existing translation asset refers to IDs absent from the source snapshot; explicit migration review needed")
    if set(corrections) - ids:
        raise ValueError("correction refers to an unknown ClassClef ID")
    entries, issues = {}, []
    for work in works:
        ident, original = work["id"], work["title_en"]
        old = existing.get(ident, {})
        if old and old.get("original") != original:
            raise ValueError(f"source title changed; explicit review needed: {ident}")
        machine = cache.get(original, {}).get("translation", "")
        machine_has_chinese = bool(re.search(r"[\u3400-\u9fff]", machine))
        entry = {"original": original, "zh": f"《{unwrap(machine)}》" if machine_has_chinese else "",
                 "status": "machine" if machine_has_chinese else "untranslated",
                 "basis": "Google Translate public web endpoint" if machine else "no_translation_available",
                 "reason": "Unreviewed machine draft; source title remains authoritative." if machine_has_chinese else "No successful Chinese translation result yet; any unchanged draft requires explicit review.",
                 "aliases_zh": []}
        if old.get("status") in {"reviewed", "reference", "retained"}:
            entry = old
        if ident in formulas and (old.get("status") not in {"reviewed", "reference", "retained"} or str(old.get("basis", "")).startswith("Complete-token musical-terminology formula")):
            if formulas[ident].get("original") != original:
                raise ValueError(f"formula title mismatch: {ident}")
            entry = formulas[ident]
        if ident in corrections:
            reviewed = corrections[ident]
            if reviewed.get("original") != original:
                raise ValueError(f"correction title mismatch: {ident}")
            entry = reviewed
        if entry.get("status") not in STATUSES or not entry.get("basis") or not entry.get("reason"):
            raise ValueError(f"invalid translation status/evidence: {ident}")
        if entry['status'] in {'reviewed', 'reference', 'machine'} and not re.search(r"[\u3400-\u9fff]", entry['zh']):
            raise ValueError(f"Chinese translation status without Chinese text: {ident}")
        if entry['status'] == 'untranslated' and entry['zh']:
            raise ValueError(f"untranslated entry must have an empty Chinese field: {ident}")
        if not isinstance(entry.get("aliases_zh"), list) or any(not isinstance(a, str) or not a.strip() for a in entry["aliases_zh"]):
            raise ValueError(f"invalid aliases: {ident}")
        if entry["zh"]:
            entry = {**entry, "zh": f"《{display_catalog_labels(unwrap(entry['zh']))}》"}
        issue = flags(original, entry["zh"])
        if issue:
            issues.append({"id": ident, "original": original, "zh": entry["zh"], "status": entry["status"], "flags": issue})
        entries[ident] = entry
    counts = dict(Counter(e["status"] for e in entries.values()))
    asset = {"schema_version": 1, "source_id": "classclef", "updated_at": now()[:10], "policy": POLICY,
             "summary": {"records": len(entries), "status_counts": counts}, "entries": entries}
    write_json(asset_path, asset)
    write_json(workspace / "translation-audit.json", {"created_at": now(), "records": len(entries), "status_counts": counts,
               "flag_counts": dict(Counter(f for row in issues for f in row["flags"])), "issues": issues})
    return {"records": len(entries), "status_counts": counts, "flagged": len(issues)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["draft", "shards", "formulas", "assemble"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--shards", type=int, default=4)
    args = parser.parse_args()
    root = args.root.resolve()
    workspace = root / "work/classclef-translation-review"
    if args.workers < 1 or args.interval < 0.5 or args.shards < 1:
        parser.error("workers/shards must be positive; request interval must be at least 0.5 seconds")
    if args.command == "draft":
        result = draft(root, workspace, args.workers, args.interval, args.limit)
    elif args.command == "shards":
        result = shards(root, workspace, args.shards)
    elif args.command == "formulas":
        result = formulas(root, workspace)
    else:
        result = assemble(root, workspace)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
