#!/usr/bin/env python
"""Write a source-attributed integration receipt; counts have explicit units."""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from acquire_source_assets import atomic_json
from catalog_sources import load_registry


def report(root: Path):
    catalog=json.loads((root/'public_site/data/catalog.json').read_text())
    registry=load_registry(root)
    new_sources=[source for source in registry if source['id'] not in {'imslp','classclef'}]
    sources=[]
    for source in new_sources:
        raw=json.loads((root/source['catalog']).read_text())
        works=[work for work in catalog['works'] if work['source_id']==source['id']]
        assets=[asset for work in raw['works'] for asset in work.get('assets',[]) if asset.get('format')=='PDF']
        members=[member for asset in assets for member in (asset.get('members',[]) if asset.get('container')=='ZIP' else [asset])]
        verified=[asset for asset in members if asset.get('status')=='verified']
        object_paths={asset['local_path'] for asset in verified}
        inodes=set();size=0
        for relative in object_paths:
            path=root/relative
            if path.is_file():
                stat=path.stat();key=(stat.st_dev,stat.st_ino)
                if key not in inodes:size+=stat.st_size
                inodes.add(key)
        sources.append({'source_id':source['id'],'name':source['name'],'homepage':source['homepage'],
            'source_record_count':len(works),'score_records':sum(work.get('resource_type')=='score' for work in works),
            'reference_records':sum(work.get('resource_type')=='reference' for work in works),
            'category_count':len(raw['categories']),'membership_count':sum(len(work['category_ids']) for work in raw['works']),
            'snapshot':raw.get('snapshot',{}),'pdf_asset_statuses':dict(Counter(asset.get('status','unspecified') for asset in assets)),
            'verified_pdf_member_records':len(verified),'distinct_verified_pdf_sha256':len({asset.get('sha256') for asset in verified}),
            'source_object_paths':len(object_paths),'source_object_inodes':len(inodes),'physical_bytes_for_source':size,
            'missing_source_composer_records':sum(not work['composer_en'] for work in works),
            'format_unknown_records':sum(not work['formats'] for work in works),
            'instrumentation_status':dict(Counter(work.get('instrumentation_status','unspecified') for work in works)),
            'translation':catalog['translation_summary'].get(source['id'],{}),
            'chinese_title_records':sum(bool(re.search(r'[\u3400-\u9fff]',work['title_zh'])) for work in works),
            'chinese_composer_records':sum(bool(re.search(r'[\u3400-\u9fff]',work['composer_zh'])) for work in works)})
    offline_path=root/'work/source-expansion/2026-10-01/offline-verification.json'
    offline=json.loads(offline_path.read_text()) if offline_path.exists() else None
    audit_path=root/'work/source-expansion/2026-10-01/translation-audit.json'
    audit=json.loads(audit_path.read_text()) if audit_path.exists() else None
    parity_path=root/'work/source-expansion/2026-10-01/catalog-parity.json'
    parity=json.loads(parity_path.read_text()) if parity_path.exists() else None
    pool=root/'sources/objects/sha256';objects=list(pool.rglob('*.pdf'))
    pool_inodes={(path.stat().st_dev,path.stat().st_ino) for path in objects}
    policies=json.loads((root/'config/source_acquisition_policies.json').read_text())
    dedup_path=root/'sources/objects/deduplication_report.json'
    dedup_runs=json.loads(dedup_path.read_text()).get('runs',[]) if dedup_path.exists() else []
    applied=[run for run in dedup_runs if run.get('mode')=='apply' and run.get('status')=='finished']
    dedup_summary={'apply_counts':applied[-1]['counts'] if applied else {},
                   'final_counts':dedup_runs[-1]['counts'] if dedup_runs else {}}
    legacy_path=root/'work/cross-source-deduplication.json'
    legacy_runs=json.loads(legacy_path.read_text()).get('runs',[]) if legacy_path.exists() else []
    legacy_summary=legacy_runs[-1]['counts'] if legacy_runs else {}
    checks={}
    for key,filename,pattern in [('python_tests','python-tests.log',r'(\d+) passed'),
                                 ('node_tests','node-tests.log',r'# pass (\d+)')]:
        logfile=root/'work/source-expansion/2026-10-01'/filename
        matches=re.findall(pattern,logfile.read_text(errors='replace')) if logfile.exists() else []
        if matches:checks[key]=int(matches[-1])
    result={'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),'registry_version':json.loads((root/'config/sources.json').read_text())['version'],
        'scope':'Frozen approved source scopes; record counts are source-scoped entries, not cross-site unique compositions.',
        'summary':catalog['summary'],'new_source_count':len(new_sources),'new_source_record_count':sum(source['source_record_count'] for source in sources),
        'relationship_types':dict(Counter(edge['type'] for edge in catalog.get('relationships',[]))),
        'new_object_pool':{'paths':len(objects),'inodes':len(pool_inodes),'bytes':sum(path.stat().st_size for path in objects),
                           'scope':'Shared immutable pool for newly acquired PDFs. Not a claim of complete IMSLP/ClassClef physical deduplication.'},
        'sources':sources,'candidate_policies':policies,'offline_verification':offline,
        'new_to_imslp_deduplication':dedup_summary,'classclef_to_imslp_dry_check':legacy_summary,
        'validation':checks,'catalog_parity':parity,
        'browser_evidence':'work/source-expansion/2026-10-01/ui-qa.md',
        'translation_audit':({'ready':audit['ready'],'pending_fields':len(audit['pending']),'retained_fields':len(audit['retained']),'coverage':audit['coverage']} if audit else None),
        'publication':{'github_push':False,'pages_deployment':False,'reason':'Local integration; machine translation drafts remain a publication review gate.'}}
    path=root/'work/source-expansion/2026-10-01/integration-report.json';atomic_json(path,result)
    lines=['# 六弦漫行（Guitar Atlas）多来源接入日志：2026-10-01','',f'记录生成：{result["created_at"]}；注册范围版本：`{result["registry_version"]}`。',
        '',f'新增 **{len(new_sources)} 个来源**，合计 **{result["new_source_record_count"]:,} 条来源记录**。全库 **{len(registry)} 个来源、{catalog["summary"]["unique_work_count"]:,} 条记录、{catalog["summary"]["category_count"]:,} 个原站分类、{catalog["summary"]["category_record_count"]:,} 条分类关系**。作品身份、版本和合集保持来源证据，不把这些数字表述成跨站唯一乐曲数。',
        '', '共同入口按编制与用途组织；所有来源参加同一搜索，原分类可展开查看。搜索覆盖原题、中文参考名、音乐家、编曲/编辑、作品号、格式与版本资料；精确筛选、中文别名及拼写恢复共用规则。',
        '', '## 冻结来源与取得范围','', '| 来源 | 纳入记录（乐谱 / 参考） | 原分类 / 分类成员关系 | PDF 资产状态 | 中文曲名参考 / 草稿 / 保留 |', '| --- | ---: | ---: | --- | ---: |']
    for source in sources:
        statuses='；'.join(f'{key} {value:,}' for key,value in source['pdf_asset_statuses'].items()) or '未批准文件获取'
        titles=source['translation'].get('title',{})
        lines.append(f'| [{source["name"]}]({source["homepage"]}) | {source["source_record_count"]:,}（{source["score_records"]:,} / {source["reference_records"]}） | {source["category_count"]:,} / {source["membership_count"]:,} | {statuses} | {titles.get("reference",0)+titles.get("reviewed",0):,} / {titles.get("machine",0):,} / {titles.get("retained",0):,} |')
    lines+=['','PDF 资产状态是来源链接/容器的取得清单单位；ZIP 中每份 PDF、同一内容的重复清单关系、真实文件路径和 inode 另计，不能混用。',
        '', '本轮获准取得的有效PDF清单关系合计 '+str(sum(source['verified_pdf_member_records'] for source in sources))+' 条；其中Mutopia包含ZIP分谱，各来源重复清单仍保留。Guitar School1个HTTP500、Delcamp3个HTTP404在复试后仍未取得，原链接与失败原因不变。',
        '', '## 各来源范围与信息边界','']
    for source in sources:
        snap=source['snapshot']
        lines += [f'- **{source["name"]}**：{snap.get("scope","见私有冻结快照")}。发现完整：`{snap.get("discovery_complete",False)}`；源署名缺失 {source["missing_source_composer_records"]:,} 条、格式未知 {source["format_unknown_records"]:,} 条；编制状态 `{json.dumps(source["instrumentation_status"],ensure_ascii=False)}`。']
    lines += ['', 'Mutopia 完整目录发现395条，3条明确声乐/替代编制排除，8条 Lute/Vihuela/Guitar 声明保持待核且不下载；官方 Git 树固定到 `2144afd6f52d56c5b6995b8b589ef1268b3139f0`。Guitar School 全部370详情及有效分类页已取得，255条明确免费 CC BY-NC 文件候选，115条付费仅导航；Theory目录404回退已验证All页。',
        '', 'Boije完整字母目录保留1154原生馆藏号及逐题组件；文件URN robots禁止批取、对象主机robots检查403，因此只纳入目录。DGA采用官方legacy API五种吉他关键词并集9453条原始记录，排除1972条明确不符编制后纳入7481条；新Omeka系统只核入口，未混同新旧ID。RISM冻结1189关键词结果，全部详情分别用215份JSON-LD和974份官方SRU MARCXML取得，排除517条明确不符编制后纳入672条；人物/机构权威ID、馆藏及母子合集关系保留，无机构谱文件获取。',
        '', 'CGLIB全CMS17574篇/176页冻结，排除1030条明确声乐或非谱编辑记录，纳入16544条；元数据CC BY-SA与谱文件版权分开。Delcamp限定官方53目录的2911个版本/合集，保留不同目录关系及明确个人非商业使用限制，源文件不公开。Cantorion仅可访问首页20条；574条搜索总量的分页被robots阻止，范围不完整。Werner8个503、Downunder1个500详情保留失败及来源目录回退，未伪称全详情完整。',
        '', '## 文件验证与去重','',f'本轮共享 SHA-256 对象池：**{len(objects):,} 个路径、{len(pool_inodes):,} 个 inode、{result["new_object_pool"]["bytes"]:,} 字节**。来源对象路径以硬链接复用，原始来源关系全部保留。对象池只覆盖本轮新增文件；既有 IMSLP 重复实体尚未全部物理去重。',
        '', '每份文件检查PDF头、传输/已知预期字节数、适用的上游摘要、内部SHA-256与可解析性。没有上游摘要的来源明确记 `not_supplied`；ZIP检查安全成员路径、展开限制与每份分谱，挑战/认证/429会停止该来源并保留未尝试条目。']
    if applied:
        counts=dedup_summary['apply_counts']
        lines += ['',f'新增来源与IMSLP实核复用：**{counts.get("linked",0)}组内容、{counts.get("completed_path_replacements",0)}条对象/来源路径原子替换、回收{counts.get("saved_bytes",0):,}字节**。最终dry检查already_shared={dedup_summary["final_counts"].get("already_shared",0)}、would_link={dedup_summary["final_counts"].get("would_link",0)}；所有记录和文件路径继续保留。',
                  '',f'原ClassClef工具最终dry检查：既有共享{legacy_summary.get("already_shared",0)}组，拒绝{legacy_summary.get("rejected",0)}个IMSLP锚点核验不符候选，继续保留ClassClef原件；这类安全拒绝不作为已完成去重。']
    if offline:
        lines += ['',f'最终全量离线重建：PDF清单 **{offline["pdf_records"]:,}**、有效关系 **{offline["downloaded"]:,}**、未就绪 **{offline["unavailable"]:,}**、不同内容SHA-256 **{offline.get("unique_pdf_contents",0):,}**。这是本次完整哈希/解析与归属检查，未就绪及既有6条排除继续保留；不是全库编制纯度证明。']
    if parity:
        lines += ['',f'公开版与离线版共享目录字段及搜索别名逐字段一致；离线专有的分类本地入口和总谱/分谱链接单独检查。**{parity["local_pdf_paths"]:,} 条不同PDF路径、{parity["legacy_category_page_paths"]:,} 条旧分类页入口、{parity["linked_pdf_inodes"]:,} 个被链接PDF inode**均存在且非空，失效链接0；6条精确排除及受影响旧页入口继续隔离。这里的路径/stat检查与上段全量PDF哈希解析分别记录。']
    terminology_count=len(json.loads((root/'metadata/translations/expansion_terminology_zh.json').read_text())['entries'])
    lines += ['', 'IMSLP原有495条work-level目标吉他候选及33条其他分段候选仍待逐文件编制核明；本轮文件完整性验证不能替代该项审查。',
        '', '## 中文字段与关联证据','', f'新增{terminology_count}条人工参考词典；标题资产按完整ID、音乐家与分类按来源保存，并以精确原文防漂移。已有相同原题或全名对应只复用显示翻译；术语规则有独立参考依据。自动译文标 `machine`、尚待逐条语义复核；无法确认的署名或专名保持原文并记录原因，来源缺失署名记 `not_applicable`。',
        '',f'有证据的关联按类型计数：`{json.dumps(result["relationship_types"],ensure_ascii=False)}`。来源明确引用同一文件、实际PDF内容一致、机构+馆藏号对应、来源合集/子条目关系分别呈现；任何同名或模糊名字都不会触发记录合并。']
    if audit:
        lines += ['',f'译名审计：`ready={str(audit["ready"]).lower()}`，待复核/漏译字段 **{len(audit["pending"]):,}**，明确保留原文字段 **{len(audit["retained"]):,}**。自动草稿使发布审校门槛未通过，本轮没有推送GitHub或部署Pages。中文覆盖率与来源缺失按完整报告逐站列出，不把有中文等同于权威定名。']
        coverage=audit['coverage']
        lines += ['', '| 来源 | 中文曲名 / 记录 | 中文署名 / 有源署名记录 | 中文分类 / 原分类 |', '| --- | ---: | ---: | ---: |']
        for source in registry:
            fields=coverage[source['id']]
            lines.append(f'| {source["name"]} | {fields["chinese_titles"]:,} / {fields["records"]:,} | {fields["chinese_attributions"]:,} / {fields["attributed_records"]:,} | {fields["chinese_categories"]:,} / {fields["categories"]:,} |')
        lines += ['', '中文字段覆盖按记录/分类统计，包含待复核机器草稿；音乐家按被署名记录计，并非不同音乐家人数。无源署名不伪造中文姓名；拉丁题名、字母目录、机构码或无法可靠确定的名称可保持原文，并单独保留理由。']
    lines += ['', '## 验收记录','',f'最终Python测试通过{checks.get("python_tests","尚未写入")}项，Node搜索测试通过{checks.get("node_tests","尚未写入")}项。公开目录隐私/身份/分类/翻译状态校验单独运行；中文语义发布审校仍未通过，二者不混为同一验收。',
              '', '浏览器检查涵盖16来源/17共同分类、索尔/巴赫/塔瑞加跨来源搜索、同一分类成员筛选、ISBN与合集、Boije/DGA馆藏关系及Mutopia/IMSLP相同PDF关系、390px手机布局。离线Rialto Ripples保留A4/Letter各四份总谱与分谱，实际点击本地总谱并在Chrome显示7页；School1039及Delcamp三条404均显示未就绪且无缺失文件链接。公共和离线浏览器error/warn为空。范围内来源计数与网站编纂者/版本编辑署名问题已修正。私有具体操作证据在 `work/source-expansion/2026-10-01/ui-qa.md`。',
              '', '版本审校线索：Mutopia1200目录署名/编制原文为G. Gershwin / Guitar；实际总谱另印George Gershwin and Will Donaldson、arranged for 3 guitars by jeff covey。保留目录原文与文件证据的区别，后续增加文件级署名/编制复核，不从一个样本推断全目录。',
              '', '完整测试输出、公开验证、译名审计、文件重建与去重输出位于 `work/source-expansion/2026-10-01/`；逐站请求、失败、续传和冻结证据位于 `sources/<source>/`。']
    lines += ['', '## 未接入的候选','', '34候选的政策台账见 [`config/source_acquisition_policies.json`](../../config/source_acquisition_policies.json)。未注册来源分别记录自动访问限制、需许可、入口不可用或采集范围未确定；不把所有阻塞都写成版权问题。Free-scores、MuseScore和Musicnotes明示限制自动访问；付费订阅、登录、购买及第三方文件复用未执行。',
        '', '## 目录与复现','', '```text', 'config/                     来源注册、范围与政策', 'scripts/source_adapters/    各站发现与规范化', 'scripts/catalog_*.py        共同目录、翻译和关联', 'sources/<source>/           私有快照、规范目录、续传状态、日志与来源对象', 'sources/objects/sha256/     本轮共享不可变PDF对象', 'metadata/translations/      持久参考对应、原文guard和草稿状态', 'public_site/                共用网页与无谱文件公共投影', 'index.html                  已验证本地链接的离线入口', 'work/source-expansion/      本次机器验收、统计与测试日志', '```',
        '', '```bash', 'python scripts/discover_open_sources.py --help', 'python scripts/discover_archive_sources.py --help', 'python scripts/discover_additional_sources.py --help', 'python scripts/acquire_source_assets.py --source mutopia --source guitarschool --source delcamp --retry-failed', 'python scripts/review_source_translations.py --machine-drafts --workers 2', 'python scripts/deduplicate_added_pdfs.py --root .', '# dry日志无异常时可用 --apply，然后重跑dry', 'python scripts/deduplicate_source_pdfs.py --root .', 'python scripts/export_public_site.py', 'python scripts/validate_public_site.py', 'python scripts/audit_translations.py --output work/source-expansion/2026-10-01/translation-audit.json', 'python scripts/render_master_index.py .', 'python -m pytest -q', 'node --test tests/search.test.cjs tests/unified_search.test.cjs', 'python scripts/report_source_expansion.py', '```',
        '', '原始页面、谱文件、哈希对象、采集日志及机器报告均在Git忽略区；本文记录来源范围、统计单位和验收边界。原有未暂存改动保留，本轮未创建提交。']
    destination=root/'docs/research/2026-10-01-integration-log.md'
    destination.write_text('\n'.join(lines)+'\n')
    print(json.dumps({'report':str(destination),'sources':len(registry),'records':catalog['summary']['unique_work_count'],'new_pool_objects':len(objects)},ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    report(parser.parse_args().root.resolve())
