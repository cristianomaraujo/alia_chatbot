"""Record structure and provenance; no new clinical criteria."""
import copy,hashlib,json,re,time
from .questions import BY_KEY
STATES=('reported','absent','unknown','not_assessed','not_applicable')
ORIGINS=('professional','examination','patient','unspecified')
def infer_state(value):
    if re.search(r'(?i)(não (foi )?(avaliad|avaliei|examinei|examinad)|not (examined|assessed)|no evaluad)',value):return 'not_assessed'
    if re.search(r'(?i)(não (se )?aplica|not applicable|no aplica)',value):return 'not_applicable'
    if re.search(r'(?i)(não informado|não sei|não tenho (essa )?informação|desconhecid|not (known|provided|reported)|unknown|no informado|desconocid)',value):return 'unknown'
    return 'reported'
def ensure_record(case):
    case.setdefault('fact_meta',{});case.setdefault('audit',[]);case.setdefault('conflicts',{})
    case.setdefault('build',{'pipeline':'legacy-unrecorded','source_sha256':None});case.setdefault('review',None);case.setdefault('safety_flags',[])
    for k,v in case['facts'].items():
        case['fact_meta'].setdefault(k,{'state':infer_state(v),'origin':'unspecified','original':None,'source_excerpt':None,'legacy':True,'confirmed':False})
    return case

def fingerprint(case):
    content={'facts':case['facts'],'meta':case.get('fact_meta',{}),'assessment':case.get('assessment'),'conflicts':case.get('conflicts',{})}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def review_valid(case):return bool(case.get('review') and case['review'].get('fingerprint')==fingerprint(case))

def patient_attributed(message):
    return bool(re.search(r'(?i)(paciente (relat|refer|refier|inform|diz|cont|nega|niega|dice|manifiest)|segundo (o|a) paciente|patient (reports|says|states|denies|told)|according to (the )?patient)',message))

def professional_wording(value,message):
    if not patient_attributed(message):
        value=re.sub(r'(?i)^(?:o |a )?paciente (relata|refere|informa|apresenta)\s+', 'Profissional informa ',value)
        value=re.sub(r'(?i)^(?:o |a )?paciente nega\s+', 'Profissional informa ausência de ',value)
        value=re.sub(r'(?i)^(?:the )?patient denies\s+', 'The professional reports absence of ',value)
        value=re.sub(r'(?i)^(?:el |la )?paciente niega\s+', 'El profesional informa ausencia de ',value)
        value=re.sub(r'(?i)^(?:the )?patient (?:reports|states|presents with|has)\s+', 'The professional reports ',value)
        value=re.sub(r'(?i)^(?:el |la )?paciente (?:refiere|informa|presenta|manifiesta)\s+', 'El profesional informa ',value)
    return value

def record_fact(case,key,value,state,origin,message,excerpt,correction=False):
    ensure_record(case);previous=case['facts'].get(key);old=case['fact_meta'].get(key)
    inferred=infer_state(value)
    state=inferred if inferred!='reported' else state if state in STATES else inferred
    origin=origin if origin in ORIGINS else 'professional'
    if origin=='patient' and not patient_attributed(message):origin='professional'
    if state=='not_assessed' and origin=='examination':origin='professional'
    value=professional_wording(value,message)
    meta={'state':state,'origin':origin,'original':message,'source_excerpt':excerpt,'legacy':False,'confirmed':False,'updated_at':time.time()}
    changed=previous is not None and (value.strip().casefold()!=previous.strip().casefold() or state!=old['state'])
    if changed and old['state'] in ('reported','absent') and not correction:
        case['conflicts'][key]={'previous':previous,'proposed':value,'meta':meta};case['review']=None
        return False
    case['facts'][key]=value;case['fact_meta'][key]=meta;case['conflicts'].pop(key,None)
    if changed or previous is None or correction:
        case['audit'].append({'key':key,'previous':previous,'value':value,'metadata':copy.deepcopy(meta),'method':'correction' if correction else 'conversation','at':time.time()})
        case['review']=None
    return True

# Every description below is a literal excerpt of the supplied owner rules.
ALERTS={
 'ulceration':'ulceração persistente',
 'induration':'endurecimento ou infiltração',
 'bleeding':'sangramento sem causa evidente',
 'color':'alterações brancas, vermelhas ou vermelho-brancas persistentes',
 'evolution':'crescimento progressivo',
 'borders':'limites pouco definidos',
 'nodes':'alterações cervicais associadas',
}


def measurements(text):
    values=set()
    # A shared unit after dimensions/ranges applies to each stated number.
    for sequence,unit in re.findall(r'(?i)(\d+(?:[.,]\d+)?(?:\s*(?:x|×|por|a|–|-)\s*\d+(?:[.,]\d+)?){1,2})\s*(mm|cm)\b',text):
        for number in re.findall(r'\d+(?:[.,]\d+)?',sequence):values.add(round(float(number.replace(',','.'))*(10 if unit.lower()=='cm' else 1),8))
    for number,unit in re.findall(r'(?i)(?<!\d)([+−-]?\d+(?:[.,]\d+)?)\s*(mm|cm)\b',text):
        values.add(round(float(number.replace(',','.').replace('−','-'))*(10 if unit.lower()=='cm' else 1),8))
    return values
