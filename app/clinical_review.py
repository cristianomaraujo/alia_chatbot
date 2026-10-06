"""Source-linked reflections, kept separate from the referral document.

These gates check record provenance; semantic verification still follows.
No additional clinical rule, treatment or diagnostic score is introduced.
"""
from .questions import BY_KEY
from .evidence import RULE_BY_ID, source_links

REVIEW_RULES={'history','examination','description','documentation',
              'lichenoid_context','histopathology','adjuncts'}

def review_candidates(items,case):
    result=[]
    for item in items:
        keys=list(dict.fromkeys(item.supporting_keys))
        if item.rule_id not in REVIEW_RULES or not keys:continue
        if any(k not in BY_KEY or k not in case['facts'] or k not in case['fact_meta'] for k in keys):continue
        if item.kind=='inconsistency' and (len(keys)<2 or any(case['fact_meta'][k]['state'] not in ('reported','absent') for k in keys)):continue
        result.append({**item.model_dump(),'supporting_keys':keys,
                       'basis_excerpt':RULE_BY_ID[item.rule_id]['text'],
                       'limits':RULE_BY_ID[item.rule_id]['limits'],
                       'sources':source_links(item.rule_id)})
    return result

def record_limitations(case):
    """No inference: a missing or unassessed finding never becomes absent."""
    return [{'key':key,'state':case.get('fact_meta',{}).get(key,{}).get('state','pending')}
            for key in case.get('active_fields',[]) if key not in case['facts'] or
            case.get('fact_meta',{}).get(key,{}).get('state') in ('unknown','not_assessed')]
