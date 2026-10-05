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
    return [{**s,**EVIDENCE['references'][s['ref']]} for s in RULE_BY_ID[rule_id]['sources']]
def pattern_candidate(item,case):
    pattern=PATTERN_BY_ID.get(item.pattern_id)
    if not pattern:return None
    rule=RULE_BY_ID[pattern['rule']]
    if item.label!=pattern['label'] or item.basis_excerpt.strip()!=rule['text']:return None
    required=pattern['required']
    if not set(required).issubset(item.supporting_keys):return None
    if any(k not in case['facts'] or case['fact_meta'][k]['state'] not in states for k,states in required.items()):return None
    if any(k not in case['facts'] or case['fact_meta'][k]['state'] not in ('reported','absent') for k in item.supporting_keys):return None
    return {**item.model_dump(),'rule_id':rule['id'],'criteria':pattern['criteria'],'limits':pattern['limits'],'sources':source_links(rule['id'])}
