"""Versioned, owner-authorized paraphrases and conservative pattern gates.

No paper PDFs or unsupported differential catalog are shipped. The language
model must still verify semantic criteria; structural gates are not diagnosis.
"""
import json
from pathlib import Path
EVIDENCE=json.loads((Path(__file__).resolve().parents[1]/'knowledge/clinical_rules.json').read_text())
RULE_BY_ID={r['id']:r for r in EVIDENCE['rules']}
PATTERN_BY_ID={p['id']:p for p in EVIDENCE['patterns']}
def source_links(rule_id):
    return [{**s,**EVIDENCE['references'][s['ref']],'pdf_pages':s['pdf_pages'] if isinstance(s['pdf_pages'],list) else [s['pdf_pages']]} for s in RULE_BY_ID[rule_id]['sources']]
def pattern_candidate(item,case):
    pattern=PATTERN_BY_ID.get(item.pattern_id)
    if not pattern:return None
    rule=RULE_BY_ID[pattern['rule']]
    # Resolve authoritative display text and source by identifier, not a fragile
    # model-generated quotation or translated label. Semantic support is checked next.
    required=pattern['required']
    if not set(required).issubset(item.supporting_keys):return None
    if any(k not in case['facts'] or case['fact_meta'][k]['state'] not in states for k,states in required.items()):return None
    if any(k not in case['facts'] or case['fact_meta'][k]['state'] not in ('reported','absent') for k in item.supporting_keys):return None
    if any(not any(k in item.supporting_keys and case['fact_meta'].get(k,{}).get('state')=='reported' for k in group) for group in pattern.get('required_any',[])):return None
    if pattern['id']=='squamous_carcinoma' and not any(k in item.supporting_keys and case['fact_meta'].get(k,{}).get('state')=='reported' for k in ('induration','ulceration')):return None
    return {**item.model_dump(),'label':pattern['label'],'basis_excerpt':rule['text'],'kind':pattern.get('kind','descriptive'),'rule_id':rule['id'],'criteria':pattern['criteria'],'limits':pattern['limits'],'sources':source_links(rule['id'])}
