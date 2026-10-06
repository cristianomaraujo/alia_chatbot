import os,tempfile,json
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='alia-tests-')
os.environ['APP_ENV']='development'
from fastapi.testclient import TestClient
from app import main
from app.questions import FIELDS
import pytest

def install_model(monkeypatch,fake):
 async def wrapped(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data.get('task')=='verify':return {'valid_indices':list(range(len(data['possibilities']))),'valid_attention':[x['key'] for x in data['attention']],'narrative_supported':True}
  return await fake(messages,schema)
 monkeypatch.setattr(main,'model',wrapped)

def review(client,case):
 r=client.post('/api/cases/'+case['id']+'/review',json={'version':case['version'],'confirmed':True});assert r.status_code==200,r.text;return r.json()

def account(email):
 c=TestClient(main.app);data={'email':email,'password':'Long-Test-Password-2026','name':'Professional'}
 assert c.post('/api/register',json=data).status_code==200
 r=c.post('/api/login',json=data);assert r.status_code==200
 c.headers['X-CSRF-Token']=r.json()['csrf'];return c
@pytest.fixture(autouse=True)
def reset_attempts():
 with main.db() as c:c.execute('DELETE FROM attempts')

@pytest.fixture
def client():return account('test-'+os.urandom(4).hex()+'@example.org')
def new(client):
 r=client.post('/api/cases',json={'language':'pt'});assert r.status_code==200;return r.json()
def test_auth_required():
 c=TestClient(main.app);assert c.get('/api/cases').status_code==401
 assert c.post('/api/cases',json={'language':'pt'}).status_code==401
 assert c.get('/health').status_code==200
 assert 'frame-ancestors' in c.get('/').headers['content-security-policy']
def test_case_isolation_and_encryption(client):
 case=new(client);other=account('other-'+os.urandom(4).hex()+'@example.org')
 assert other.get('/api/cases/'+case['id']).status_code==404
 assert other.delete('/api/cases/'+case['id']).status_code==404
 assert other.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'50'}}).status_code==404
 with main.db() as c:r=c.execute('SELECT payload FROM cases WHERE id=?',(case['id'],)).fetchone()
 assert 'facts' not in r['payload'];assert main.dec(r['payload'])['id']==case['id']
 assert other.get('/api/cases').json()==[]
def test_csrf_and_origin(client):
 case=new(client)
 token=client.headers.pop('X-CSRF-Token')
 assert client.delete('/api/cases/'+case['id']).status_code==403
 client.headers['X-CSRF-Token']=token
 assert client.post('/api/cases',json={'language':'pt'},headers={'Origin':'https://evil.example'}).status_code==403
 assert client.get('/api/cases/'+case['id']).status_code==200

def test_correction_and_concurrency(client):
 case=new(client)
 r=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'sex':'Female','age':'52'}})
 assert r.status_code==200;assert r.json()['pending']=='complaint'
 assert client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'80'}}).status_code==409
 assert client.get('/api/cases/'+case['id']).json()['facts']['age']=='52'
 assert client.patch('/api/cases/'+case['id'],json={'version':2,'facts':{'diagnosis':'cancer'}}).status_code==422

def test_unknown_and_multi_facts(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):return {'updates':[{'key':'sex','value':'Desconhecido'},{'key':'age','value':'60'}],'explanation':''}
 install_model(monkeypatch,fake)
 r=client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Sexo desconhecido, 60 anos'})
 assert r.status_code==200;data=r.json();assert data['pending']=='complaint'
 assert data['facts']['sex']=='Desconhecido'
 assert data['history'][-1]['content'].endswith(main.BY_KEY['complaint']['question'])
 assert data['history'][-1]['content'].count('?')==1

def test_model_failure_is_atomic(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):raise main.HTTPException(502,'Test failure')
 install_model(monkeypatch,fake)
 assert client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Female'}).status_code==502
 assert client.get('/api/cases/'+case['id']).json()['version']==1
 assert client.get('/api/cases/'+case['id']).json()['facts']=={}

def test_invalid_model_field_not_saved(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):return {'updates':[{'key':'diagnosis','value':'Cancer'}],'explanation':''}
 install_model(monkeypatch,fake)
 assert client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Hello'}).status_code==502
 assert client.get('/api/cases/'+case['id']).json()['facts']=={}

def test_gallery_only_after_collection_and_not_in_facts(client):
 case=new(client)
 assert client.patch('/api/cases/'+case['id'],json={'version':1,'gallery':'F01'}).status_code==422
 r=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{k:'Não informado' for k,_,_ in FIELDS}})
 assert r.json()['pending'] is None
 r=client.patch('/api/cases/'+case['id'],json={'version':2,'gallery':'none'})
 assert r.status_code==200;assert r.json()['gallery']=='none'
 assert 'gallery' not in r.json()['facts']

def test_delete_logout(client):
 case=new(client);assert client.delete('/api/cases/'+case['id']).status_code==200
 assert client.get('/api/cases/'+case['id']).status_code==404
 assert client.post('/api/logout').status_code==200
 assert client.get('/api/cases').status_code==401

def test_catalog_provenance():
 data=TestClient(main.app).get('/api/catalog').json()
 assert len(data['gallery'])==16 and len(data['references'])==9
 assert all(x['ai_generated'] for x in data['gallery'])
 assert 'confirm the nature of an alteration' in main.RULES.lower()
 assert len(data['evidence']['references'])==9 and data['build']['clinical_rules_version']=='alia-evidence-2.0'
 assert len({k for k,_,_ in FIELDS})==len(FIELDS)

def test_translation_failure_not_partial(client,monkeypatch):
 async def fake(messages,schema):return {'welcome':''}
 install_model(monkeypatch,fake)
 assert client.post('/api/localize',json={'language':'de'}).status_code==502

def test_invitation_required(client,monkeypatch):
 monkeypatch.setattr(main,'PRODUCTION',True)
 monkeypatch.delenv('REGISTRATION_CODE',raising=False)
 assert client.post('/api/register',json={'email':'blocked@example.org','password':'Long-Test-Password-2026'}).status_code==403
def test_referral_identity_not_in_case(client,monkeypatch):
 case=new(client)
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 async def fake(messages,schema):return {'updates':[],'explanation':'','action':'summarize'}
 install_model(monkeypatch,fake)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Preparar encaminhamento'}).json()
 async def no(messages,schema):return {'updates':[],'explanation':'','action':'no'}
 install_model(monkeypatch,no)
 case=conversation(client,case,'Não quero localizar serviços')
 async def yes(messages,schema):return {'updates':[],'explanation':'','action':'yes'}
 install_model(monkeypatch,yes)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Sim'}).json()
 case=review(client,case)
 r=client.post('/api/cases/'+case['id']+'/referral-data',json={})
 assert r.status_code==200;assert r.json()=={'facts':{},'version':case['version']}
 assert set(client.get('/api/cases/'+case['id']).json())==set(case)

def test_rate_limit():
 request=type('Req',(),{'client':type('Client',(),{'host':'rate-test'})()})()
 for _ in range(10):main.limit(request,'test',10)
 with pytest.raises(main.HTTPException) as error:main.limit(request,'test',10)
 assert error.value.status_code==429

def test_notice_only_in_opening(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):return {'updates':[{'key':'sex','value':'Feminino'},{'key':'age','value':'52'},{'key':'complaint','value':'Alteração branca'}],'explanation':''}
 install_model(monkeypatch,fake)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Mulher, 52 anos, alteração branca'}).json()
 assert main.NOTICE in case['history'][0]['content']
 assert main.NOTICE not in case['history'][-1]['content']
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{k:'Não informado' for k,_,_ in FIELDS}}).json()
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'gallery':'none'}).json()
 assert main.NOTICE not in case['history'][-1]['content']

def demo_client():
 c=TestClient(main.app);r=c.post('/api/demo/start',json={'scenario':'white-patch'})
 assert r.status_code==200;c.headers['X-CSRF-Token']=r.json()['csrf'];return c

def test_demo_is_temporary_and_isolated(client):
 protected=new(client);demo=demo_client();case=new(demo)
 assert case['demo'] and case['example']['id']=='white-patch'
 assert demo.get('/api/cases/'+protected['id']).status_code==404
 assert client.get('/api/cases/'+case['id']).status_code==404
 with main.db() as c:assert c.execute('SELECT count(*) FROM cases WHERE id=?',(case['id'],)).fetchone()[0]==0
 assert demo.get('/api/cases').json()==[]
 assert demo.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'52'}}).json()['version']==2
 assert demo.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'61'}}).status_code==409
 assert new(demo)['demo']
 assert demo.post('/api/cases',json={'language':'pt'}).status_code==429
 assert demo.post('/api/logout').status_code==200
 assert demo.get('/api/cases/'+case['id']).status_code==401

def test_demo_expiry_csrf_and_budget(monkeypatch):
 c=demo_client();case=new(c);token=main.hashed(c.cookies.get('alia_session'));session=main.DEMO_SESSIONS[token]
 csrf=c.headers.pop('X-CSRF-Token')
 assert c.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'52'}}).status_code==403
 c.headers['X-CSRF-Token']=csrf;session['calls']=45
 async def forbidden(*args):raise AssertionError('Over-budget call must not reach model')
 monkeypatch.setattr(main,'model',forbidden)
 assert c.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Feminino'}).status_code==429
 session['expires']=0
 assert c.get('/api/me').status_code==401

def test_demo_same_model_and_scope(monkeypatch):
 c=demo_client();case=new(c)
 async def fake(messages,schema):
  assert main.RULES in messages[0]['content']
  assert 'No repeated notices' in messages[0]['content']
  return {'updates':[{'key':'sex','value':'Feminino'}],'explanation':''}
 install_model(monkeypatch,fake)
 case=c.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Feminino'}).json()
 assert case['pending']=='age'
 assert c.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409

@pytest.mark.parametrize('choice',['none','skip'])
def test_optional_gallery_and_chat_continuation(client,monkeypatch,choice):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{k:'Não informado' for k,_,_ in FIELDS}}).json()
 original=dict(case['facts'])
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'gallery':choice}).json()
 assert case['gallery']==choice and case['facts']==original
 assert main.NOTICE not in case['history'][-1]['content']
 assert 'continuar a conversa' in case['history'][-1]['content']
 async def fake(messages,schema):return {'updates':[{'key':'pain','value':'Sem dor relatada'}],'explanation':''}
 install_model(monkeypatch,fake)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Corrijo: não relata dor'}).json()
 assert case['facts']['pain']=='Sem dor relatada'
 assert case['assessment']['status']=='insufficient'
 assert case['flow']['stage']=='done'

def complete_case(client):
 case=new(client)
 return client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{k:'Não informado' for k,_,_ in FIELDS}}).json()
def conversation(client,case,message):
 r=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':message})
 assert r.status_code==200,r.text
 return r.json()
def mock_reply(monkeypatch,**fields):
 async def fake(messages,schema):return {'updates':[],'explanation':'',**fields}
 install_model(monkeypatch,fake)

def test_final_actions_are_available_without_consent_questions(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Sintetize')
 assert case['flow']=={'stage':'done','referral_ready':True,'actions_ready':True}
 assert 'Deseja' not in case['history'][-1]['content']
 assert 'localizar' not in case['history'][-1]['content']
 assert client.post('/api/cases/'+case['id']+'/referral-data').status_code==409
 case=review(client,case)
 assert client.post('/api/cases/'+case['id']+'/referral-data').status_code==200

def test_no_match_keeps_both_actions_available(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='no_match')
 case=conversation(client,case,'Revisar')
 assert case['flow']['actions_ready'] and case['flow']['referral_ready']
 assert 'não exclui' in case['assessment']['text']
 mock_reply(monkeypatch,action='no')
 case=conversation(client,case,'Não quero localizar serviços')
 assert case['flow']['stage']=='done' and case['flow']['referral_ready']
 assert '?' not in case['history'][-1]['content']

def test_synthesis_does_not_collect_location_in_conversation(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Revisar')
 mock_reply(monkeypatch,location='Curitiba')
 case=conversation(client,case,'Curitiba')
 assert case['flow']['stage']=='done' and 'city' not in case['flow']
 assert 'city' not in case['facts']

def test_compatibility_requires_source_and_stated_support(client,monkeypatch):
 case=complete_case(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca','scraping':'Não removível à raspagem'}}).json()
 candidate={'pattern_id':'white_nonremovable','label':main.PATTERN_BY_ID['white_nonremovable']['label'],'reason':'Coloração branca não removível informada.','supporting_keys':['color','scraping'],'basis_excerpt':main.RULE_BY_ID['white_pattern']['text']}
 mock_reply(monkeypatch,assessment_status='compatible',possibilities=[candidate])
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['status']=='compatible' and 'padrões descritivos' in case['assessment']['text']
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Não informado'}}).json()
 assert not case['assessment'] and not case['flow']['referral_ready']
 case=conversation(client,case,'Revisar')
 assert case['assessment']['status']=='validation_failed' and not case['assessment']['possibilities']

def test_unsupported_compatibility_and_early_summary(client,monkeypatch):
 case=new(client)
 candidate={'label':'Invented lesion','reason':'Invented match','supporting_keys':['sex'],'basis_excerpt':'Invented criterion'}
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[candidate],explanation='Invented lesion is compatible.')
 case=conversation(client,case,'Quero encaminhar sem completar')
 assert case['pending']=='sex' and case['assessment']['status']=='validation_failed'
 assert 'Invented lesion' not in case['history'][-1]['content']
 assert case['flow']['stage']=='done'

def test_collection_question_answer_and_strict_schema(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):
  assert set(schema['required'])==set(schema['properties'])
  assert set(schema['$defs']['Compatibility']['required'])==set(schema['$defs']['Compatibility']['properties'])
  return {'updates':[],'explanation':'Registre apenas o que foi observado na avaliação clínica.'}
 install_model(monkeypatch,fake)
 case=conversation(client,case,'Como registrar essa informação?')
 assert case['pending']=='sex'
 assert 'Registre apenas' in case['history'][-1]['content']
 assert case['history'][-1]['content'].count('?')==1


def test_collection_suppresses_interpretation_and_duplicate_question(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'sex','value':'Feminino'}],explanation='Esses achados sugerem uma lesão suspeita. Qual a idade da paciente?')
 case=conversation(client,case,'Feminino')
 assert case['pending']=='age'
 assert case['history'][-1]['content']==main.BY_KEY['age']['question']
 assert not case.get('assessment')

def test_misunderstanding_never_records_unknown_or_advances(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'sex','value':'Não informado'}],explanation='Claro. Informe o sexo registrado na avaliação. '+main.BY_KEY['sex']['question'])
 case=conversation(client,case,'Não entendi a pergunta')
 assert case['pending']=='sex' and case['facts']=={}
 assert 'Claro.' in case['history'][-1]['content']
 assert case['history'][-1]['content'].count('?')==1

def test_model_classified_clarification_preserves_current_step(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,needs_clarification=True,updates=[{'key':'sex','value':'Não informado'}],explanation='Posso explicar essa informação em palavras mais simples.')
 case=conversation(client,case,'Explique melhor essa informação')
 assert case['pending']=='sex' and not case['facts']

def test_professional_attribution_and_field_provenance(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'complaint','value':'Paciente relata dor durante a alimentação.','state':'reported','origin':'patient','source_excerpt':'dor para comer'}])
 case=conversation(client,case,'dor para comer')
 assert case['facts']['complaint']=='Profissional informa dor durante a alimentação.'
 meta=case['fact_meta']['complaint']
 assert meta['origin']=='professional' and meta['original']=='dor para comer' and meta['source_excerpt']=='dor para comer'
 assert case['audit'][-1]['value']==case['facts']['complaint']


def test_explicit_patient_report_is_preserved(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'pain','value':'Paciente relata dor ao comer.','state':'reported','origin':'patient','source_excerpt':'paciente relata dor'}])
 case=conversation(client,case,'O paciente relata dor ao comer')
 assert case['fact_meta']['pain']['origin']=='patient'
 assert case['facts']['pain'].startswith('Paciente relata')


def test_states_are_distinct_and_preserved_in_review(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'nodes':'Não avaliado','pain':'Sem dor','allergies':'Desconhecido','scraping':'Não aplicável'},'metadata':{'nodes':{'state':'not_assessed','origin':'professional'},'pain':{'state':'absent','origin':'patient'},'allergies':{'state':'unknown','origin':'professional'},'scraping':{'state':'not_applicable','origin':'professional'}}}).json()
 assert {k:x['state'] for k,x in case['fact_meta'].items()}=={'nodes':'not_assessed','pain':'absent','allergies':'unknown','scraping':'not_applicable'}
 mock_reply(monkeypatch,action='summarize');case=conversation(client,case,'Sintetize')
 mock_reply(monkeypatch,action='no');case=conversation(client,case,'Não')
 mock_reply(monkeypatch,action='yes');case=conversation(client,case,'Sim')
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 case=review(client,case)
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==200
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'nodes':'Sem alterações palpáveis'},'metadata':{'nodes':{'state':'absent','origin':'examination'}}}).json()
 assert case['review'] is None and not case['assessment']
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409


def test_contradiction_does_not_silently_overwrite_and_can_be_resolved(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'size':'5 mm'}}).json()
 mock_reply(monkeypatch,updates=[{'key':'size','value':'5 cm','state':'reported','source_excerpt':'5 cm'}])
 case=conversation(client,case,'5 cm')
 assert case['facts']['size']=='5 mm' and case['conflicts']['size']['proposed']=='5 cm'
 assert case['assessment'] is None
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'resolve':{'size':'proposed'}}).json()
 assert case['facts']['size']=='5 cm' and not case['conflicts']
 mock_reply(monkeypatch,updates=[{'key':'size','value':'6 mm','state':'reported','source_excerpt':'6 mm'}],correction=True)
 case=conversation(client,case,'Corrijo para 6 mm')
 assert case['facts']['size']=='6 mm' and not case['conflicts']
 assert case['audit'][-1]['previous']=='5 cm'


def test_fabricated_source_excerpt_is_rejected_atomically(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'pain','value':'Dor intensa','state':'reported','source_excerpt':'dor intensa'}])
 r=client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'dor leve'})
 assert r.status_code==502
 assert client.get('/api/cases/'+case['id']).json()['facts']=={}


def test_free_question_after_synthesis_is_answered_without_restarting(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Sintetize')
 mock_reply(monkeypatch,is_question=True,explanation='A ausência de uma correspondência não exclui uma alteração que precise de investigação.')
 case=conversation(client,case,'Isso exclui doença?')
 assert 'não exclui' in case['history'][-1]['content']
 assert case['flow']['stage']=='done'


def test_pipeline_separates_collection_and_synthesis_and_rejects_unverified_claim(client,monkeypatch):
 case=complete_case(client)
 calls=[]
 async def fake(messages,schema):
  context=json.loads(messages[-1]['content']);calls.append(context['task'])
  if context['task']=='collect':return {'updates':[],'explanation':'','action':'summarize'}
  if context['task']=='synthesis':return {'updates':[],'explanation':'Unsupported conclusion','assessment_status':'compatible','possibilities':[{'label':'lesões brancas','reason':'Unsupported cause','supporting_keys':['color'],'basis_excerpt':'Dê atenção especial a lesões brancas, vermelhas ou vermelho-brancas'}]}
  return {'valid_indices':[],'valid_attention':[],'narrative_supported':False}
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca'}}).json()
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert calls==['collect','synthesis','verify']
 assert case['assessment']['status']=='validation_failed'
 assert 'Unsupported' not in case['assessment']['text']
 assert case['executions'][-1]['build']['source_sha256']==main.BUILD['source_sha256']


def test_attention_requires_source_and_actual_positive_support(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'ulceration','value':'Não avaliado','state':'not_assessed'}],attention=[{'key':'ulceration','excerpt':'ulceração persistente','supporting_keys':['ulceration'],'reason':'Não pode ser assumido'}])
 case=conversation(client,case,'Não avaliado')
 assert not case['safety_flags']
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'ulceration':'Ulceração presente','duration':'3 meses'}}).json()
 mock_reply(monkeypatch,attention=[{'key':'ulceration','excerpt':'ulceração persistente','supporting_keys':['ulceration','duration'],'reason':'Ulceração persistente informada pelo profissional.'}])
 case=conversation(client,case,'Complemento a ficha')
 assert case['safety_flags'][0]['excerpt'] in main.ORIGINAL_SOURCE


def test_research_export_is_owner_scoped_and_contains_versioned_record(client):
 case=new(client)
 r=client.post('/api/cases/'+case['id']+'/research-export',json={'version':1,'confirmed':True})
 assert r.status_code==200 and r.json()['case']['build']['pipeline']==main.PIPELINE_VERSION
 other=account('export-'+os.urandom(4).hex()+'@example.org')
 assert other.post('/api/cases/'+case['id']+'/research-export',json={'version':1,'confirmed':True}).status_code==404
 assert client.post('/api/cases/'+case['id']+'/research-export',json={'version':2,'confirmed':True}).status_code==409


def test_manual_metadata_validation_and_same_value_edit(client):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'age':'60'}}).json()
 r=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'age':'60'},'metadata':{'age':{'state':'imaginary'}}})
 assert r.status_code==422
 r=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'age':'60'},'metadata':{'age':{'state':'reported','origin':'professional'}}})
 assert r.status_code==200 and r.json()['audit'][-1]['method']=='manual_edit'

def test_unassessed_source_cannot_be_rewritten_as_negative(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'nodes','value':'Sem alterações à palpação','state':'absent','origin':'examination','source_excerpt':'Não avaliei a palpação'}])
 case=conversation(client,case,'Não avaliei a palpação')
 assert case['fact_meta']['nodes']['state']=='not_assessed'
 assert case['facts']['nodes']=='Não avaliei a palpação'
 assert case['fact_meta']['nodes']['origin']=='professional'


def test_measurement_rewrite_cannot_change_mm_to_cm(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,updates=[{'key':'size','value':'5 cm','source_excerpt':'5 mm'}])
 assert client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'5 mm'}).status_code==502
 assert client.get('/api/cases/'+case['id']).json()['facts']=={}
 mock_reply(monkeypatch,updates=[{'key':'size','value':'0,5 cm','source_excerpt':'5 mm'}])
 case=conversation(client,case,'5 mm')
 assert case['facts']['size']=='0,5 cm'
 mock_reply(monkeypatch,updates=[{'key':'size','value':'5 mm × 10 mm','source_excerpt':'5 × 10 mm'}],correction=True)
 case=conversation(client,case,'Corrijo para 5 × 10 mm')
 assert case['facts']['size']=='5 mm × 10 mm'

def test_attention_verification_is_reused_only_for_unchanged_evidence(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':1,'facts':{'ulceration':'Ulceração presente','duration':'3 meses'}}).json()
 calls=[]
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content']);calls.append(data['task'])
  if data['task']=='verify':return {'valid_indices':[],'valid_attention':['ulceration'],'narrative_supported':True}
  return {'updates':[],'explanation':'','attention':[{'key':'ulceration','excerpt':'ulceração persistente','supporting_keys':['ulceration','duration'],'reason':'Ulceração persistente informada.'}]}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Complemento')
 case=conversation(client,case,'Continuar')
 assert calls==['collect','verify','collect']
 assert case['safety_flags']


def test_conditional_fields_and_guidance(client):
 case=client.get('/api/cases/'+new(client)['id']).json()
 assert 'clinical_suspicion' not in case['active_fields']
 assert 'reticular_pattern' not in case['active_fields']
 assert 'cancer_therapy' not in case['active_fields']
 assert main.BY_KEY['size']['guidance']
 assert 'distribution' in main.active_keys({},['lichenoid'])

def test_registry_rejects_missing_prerequisites():
 pattern=main.PATTERN_BY_ID['white_nonremovable']
 item=main.Compatibility(pattern_id=pattern['id'],label=pattern['label'],reason='white',supporting_keys=['color'],basis_excerpt=main.RULE_BY_ID[pattern['rule']]['text'])
 case={'facts':{'color':'white'},'fact_meta':{'color':{'state':'reported'}}}
 assert main.pattern_candidate(item,case) is None
 item.pattern_id='invented'
 assert main.pattern_candidate(item,case) is None

def test_old_evidence_blocks_referral(client):
 case=new(client)
 case['assessment']={'text':'Old synthesis','build':{}}
 case['flow']={'referral_ready':True,'stage':'done'}
 main.save_case(case,_case_owner(case['id']),case['version'])
 read=client.get('/api/cases/'+case['id']).json()
 assert read['assessment_stale']
 assert client.post('/api/cases/'+case['id']+'/review',json={'version':read['version'],'confirmed':True}).status_code==409
 assert client.post('/api/cases/'+case['id']+'/referral-data').status_code==409

def _case_owner(case_id):
 with main.db() as c:return c.execute('SELECT user_id FROM cases WHERE id=?',(case_id,)).fetchone()['user_id']

def test_lichenoid_context_requires_recorded_update(client,monkeypatch):
 case=new(client)
 mock_reply(monkeypatch,lichenoid_context=True)
 case=conversation(client,case,'Não entendi')
 assert 'lichenoid' not in case['contexts']
 mock_reply(monkeypatch,lichenoid_context=True,updates=[{'key':'reticular_pattern','value':'Estrias brancas entrelaçadas','source_excerpt':'Estrias brancas entrelaçadas'}])
 case=conversation(client,case,'Estrias brancas entrelaçadas')
 assert 'lichenoid' in case['contexts'] and 'contact_relation' in case['active_fields']

def test_referral_is_independent_of_matching_pattern(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'clinical_suspicion':'Considero clinicamente suspeita'}}).json()
 async def fake(messages,schema):
  task=json.loads(messages[-1]['content'])['task']
  if task=='verify':return {'referral_supported':True,'narrative_supported':False}
  return {'updates':[],'explanation':'','action':'summarize','assessment_status':'no_match','referral_rule':'suspicious_referral'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['status']=='no_match'
 assert case['assessment']['referral_rule']['rule_id']=='suspicious_referral'
 assert 'encaminhamento imediato' in case['assessment']['text']
 assert case['assessment']['referral_rule']['sources']

def test_unassessed_suspicion_cannot_support_referral(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'clinical_suspicion':'Não avaliado'},'metadata':{'clinical_suspicion':{'state':'not_assessed'}}}).json()
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data['task']=='verify':
   assert data['referral_rule']=='none'
   return {'referral_supported':True}
  return {'updates':[],'explanation':'','action':'summarize','assessment_status':'insufficient','referral_rule':'suspicious_referral'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['referral_rule'] is None

def test_semantic_verifier_can_reject_structural_match(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca','scraping':'Removível à raspagem'}}).json()
 pattern=main.PATTERN_BY_ID['white_nonremovable']
 candidate={'pattern_id':pattern['id'],'label':pattern['label'],'basis_excerpt':main.RULE_BY_ID[pattern['rule']]['text'],'supporting_keys':['color','scraping'],'reason':'Unsupported non-removability'}
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data['task']=='verify':return {'valid_indices':[]}
  return {'updates':[],'explanation':'','action':'summarize','assessment_status':'compatible','possibilities':[candidate]}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['status']=='validation_failed' and not case['assessment']['possibilities']


def test_direct_negative_trauma_preserves_negation_and_advances(client,monkeypatch):
 case=new(client)
 keys=main.active_keys({})
 preceding={k:'Não informado' for k in keys[:keys.index('trauma')]}
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':preceding}).json()
 assert case['pending']=='trauma'
 async def fail(messages,schema):raise AssertionError('No model call needed for a direct negative')
 monkeypatch.setattr(main,'model',fail)
 case=conversation(client,case,'Não há nenhuma fonte de trauma')
 assert case['facts']['trauma']=='Não há nenhuma fonte de trauma'
 assert case['fact_meta']['trauma']['state']=='absent'
 assert case['pending']=='irritant_timing'
 assert case['fact_meta']['trauma']['source_excerpt']=='Não há nenhuma fonte de trauma'

def test_direct_answer_does_not_infer_from_complex_or_uncertain_trauma():
 case={'pending':'trauma','flow':{'stage':'collect'}}
 assert main.direct_answer(case,'Não sei se há trauma') is None
 assert main.direct_answer(case,'Não há trauma, mas há irritação química') is None
 assert main.direct_answer(case,'Não há trauma?') is None

def test_empty_extraction_explains_non_advancement(client,monkeypatch):
 case=new(client);mock_reply(monkeypatch)
 case=conversation(client,case,'Texto que não foi capturado')
 assert 'Não consegui registrar' in case['history'][-1]['content']
 assert case['pending']=='sex'


def test_internal_matching_reason_is_not_the_final_conclusion(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Vermelha','duration':'Seis meses'}}).json()
 pattern=main.PATTERN_BY_ID['red_persistent']
 candidate={'pattern_id':pattern['id'],'label':pattern['label'],'basis_excerpt':main.RULE_BY_ID[pattern['rule']]['text'],'supporting_keys':['color','duration'],'reason':'Preenchendo os critérios registrados para o padrão descritivo.'}
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[candidate])
 case=conversation(client,case,'Sintetize')
 text=case['history'][-1]['content']
 assert 'Preenchendo os critérios' not in text
 assert 'padrões descritivos' in case['assessment']['text']
 assert 'avaliação por um estomatologista' in text
 assert 'podem ser compatíveis com as seguintes possibilidades' not in text

def test_none_medications_is_recorded_and_advances_without_model(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'sex':'Feminino','age':'50','complaint':'Dor','health':'Não informado'}}).json()
 assert case['pending']=='medications'
 async def fail(messages,schema):raise AssertionError('Direct negative must not depend on model extraction')
 monkeypatch.setattr(main,'model',fail)
 case=conversation(client,case,'Nenhum')
 assert case['pending']=='allergies'
 assert case['fact_meta']['medications']['state']=='absent'
 assert case['fact_meta']['medications']['source_excerpt']=='Nenhum'
 assert 'ausência de medicamentos' in case['facts']['medications']
 assert case['history'][-1]['content']==main.BY_KEY['allergies']['question']

@pytest.mark.parametrize('key',sorted(main.NEGATIVE_ANSWER_FIELDS))
@pytest.mark.parametrize('answer',['Nenhum','Não','None','Ninguno'])
def test_short_negatives_are_contextual(key,answer):
 result=main.direct_answer({'pending':key,'flow':{'stage':'collect'}},answer)
 assert result['updates'][0]['key']==key
 assert result['updates'][0]['state']=='absent'
 assert result['updates'][0]['source_excerpt']==answer

@pytest.mark.parametrize('key',['sex','age','location','size','duration','shape','surface','color','evolution','distribution'])
def test_short_negatives_do_not_fill_descriptive_fields(key):
 assert main.direct_answer({'pending':key},'Nenhum') is None

@pytest.mark.parametrize('answer',['Não sei se usa medicamentos','Nenhum?','Nenhum atualmente, mas usava antes','Nenhum, exceto losartana'])
def test_uncertain_or_complex_medication_answer_requires_extraction(answer):
 assert main.direct_answer({'pending':'medications'},answer) is None

def test_unknown_and_not_assessed_remain_different_from_none():
 for answer,state in [('Nenhum','absent'),('Não informado','unknown'),('Não avaliado','not_assessed')]:
  assert main.direct_answer({'pending':'medications'},answer)['updates'][0]['state']==state

def test_guest_access_needs_no_example_and_does_not_save_history():
 c=TestClient(main.app)
 response=c.post('/api/demo/start',json={})
 assert response.status_code==200
 c.headers['X-CSRF-Token']=response.json()['csrf']
 case=new(c)
 assert case['demo'] and case['example'] is None
 assert case['facts']=={} and case['pending']=='sex'
 assert c.get('/api/cases').json()==[]
 with main.db() as db:
  assert db.execute('SELECT count(*) FROM cases WHERE id=?',(case['id'],)).fetchone()[0]==0
 c.post('/api/logout')
 assert c.get('/api/cases/'+case['id']).status_code==401


def named_candidate(id,keys,reason):
 return {'pattern_id':id,'label':'','basis_excerpt':'','supporting_keys':keys,'reason':reason}

def test_lichen_planus_named_with_unknown_contact_and_medication_context(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'reticular_pattern':'Estrias brancas entrelaçadas em rede','distribution':'Bilateral e simétrica em mucosa jugal','medication_timing':'Não informado','contact_relation':'Não avaliado'}}).json()
 assert 'lichenoid' in case['contexts']
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('oral_lichen_planus',['reticular_pattern','distribution'],'Estrias brancas em rede com distribuição bilateral e simétrica favorecem essa possibilidade; o contexto de medicamentos e contato ainda precisa ser esclarecido.')])
 case=conversation(client,case,'Sintetize')
 assert [x['label'] for x in case['assessment']['possibilities']]==['Líquen plano oral']
 assert 'Possibilidades a avaliar: Líquen plano oral.' in case['history'][-1]['content']
 assert 'estomatologista' in case['history'][-1]['content']
 assert 'não uma confirmação' in case['assessment']['text']
 assert 'Possibilidade a avaliar: Líquen plano oral:' in case['assessment']['text']
 assert 'não significa que ela esteja presente' in case['assessment']['text']
 assert 'nem estimar sua probabilidade' in case['assessment']['text']
 assert 'Deseja' not in case['history'][-1]['content']
 assert case['assessment']['possibilities'][0]['sources'][0]['pdf_pages']==['4–9, 15–21']

def test_two_supported_lichenoid_possibilities_are_presented(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'reticular_pattern':'Estrias reticulares brancas','distribution':'Unilateral em mucosa jugal direita','contact_relation':'Correspondem ao contato direto com restauração de amálgama'}}).json()
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('oral_lichen_planus',['reticular_pattern'],'O padrão reticular permite considerar essa hipótese, embora a distribuição unilateral exija comparação com outras alterações.'),named_candidate('lichenoid_contact',['reticular_pattern','contact_relation'],'A correspondência com o contato local permite considerar reação liquenoide, sem confirmar causa.')])
 case=conversation(client,case,'Sintetize')
 assert len(case['assessment']['possibilities'])==2
 assert 'Líquen plano oral:' in case['assessment']['text'] and 'Reação liquenoide de contato:' in case['assessment']['text']

def test_unknown_context_does_not_prove_specific_contact_or_drug_reaction(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'reticular_pattern':'Estrias brancas em rede','contact_relation':'Não informado','medication_timing':'Não avaliado'}}).json()
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('lichenoid_contact',['reticular_pattern','contact_relation'],'Contact'),named_candidate('lichenoid_drug',['reticular_pattern','medication_timing'],'Drug')])
 case=conversation(client,case,'Sintetize')
 assert not case['assessment']['possibilities']

def test_lichen_cannot_be_suggested_from_white_color_alone(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca','reticular_pattern':'Não informado'}}).json()
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('oral_lichen_planus',['color','reticular_pattern'],'White')])
 case=conversation(client,case,'Sintetize')
 assert not case['assessment']['possibilities']

def test_neoplasia_candidate_requires_more_than_color_and_duration(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Vermelha','duration':'Três meses'}}).json()
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('squamous_carcinoma',['color','duration'],'Red')])
 case=conversation(client,case,'Sintetize')
 assert not case['assessment']['possibilities']

def test_named_hypothesis_semantic_rejection_remains_effective(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'reticular_pattern':'Ausência de estrias reticulares'}}).json()
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data['task']=='verify':return {'valid_indices':[]}
  return {'updates':[],'explanation':'','action':'summarize','assessment_status':'compatible','possibilities':[named_candidate('oral_lichen_planus',['reticular_pattern'],'Unsupported')]}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert not case['assessment']['possibilities'] and 'Líquen plano oral' not in case['history'][-1]['content']

def test_named_hypothesis_replaces_redundant_generic_pattern(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'reticular_pattern':'Estrias brancas reticulares','color':'Branca','scraping':'Não removível'}}).json()
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('oral_lichen_planus',['reticular_pattern'],'Estrias em rede.'),named_candidate('white_nonremovable',['color','scraping'],'Branca.')])
 case=conversation(client,case,'Sintetize')
 assert [x['pattern_id'] for x in case['assessment']['possibilities']]==['oral_lichen_planus']

def test_corrections_invalidate_final_buttons_and_review(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Sintetize');case=review(client,case)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca'}}).json()
 assert not case['assessment'] and not case['flow']['referral_ready'] and case['review'] is None
 assert client.post('/api/cases/'+case['id']+'/referral-data').status_code==409


def test_lichen_morphology_can_be_recorded_in_intraoral_exam(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'intraoral':'Estrias brancas entrelaçadas em rede, bilateralmente na mucosa jugal'}}).json()
 assert 'lichenoid' in case['contexts'] and 'reticular_pattern' in case['active_fields']
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[named_candidate('oral_lichen_planus',['intraoral'],'O padrão de estrias descrito no exame permite considerar essa possibilidade.')])
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['possibilities'][0]['label']=='Líquen plano oral'


def test_final_prose_cannot_reintroduce_action_questions(client,monkeypatch):
 case=complete_case(client)
 mock_reply(monkeypatch,assessment_status='insufficient',explanation='Os dados ainda são limitados. Deseja gerar um relatório? Deseja procurar profissionais?')
 case=conversation(client,case,'Sintetize')
 assert 'Os dados ainda são limitados.' in case['assessment']['text']
 assert '?' not in case['history'][-1]['content'] and 'Deseja' not in case['history'][-1]['content']


def test_optional_professional_concern_does_not_block_or_become_negative(client):
 case=new(client)
 facts={k:'Não informado' for k in main.active_keys({}) if k!='photo_record'}
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':facts}).json()
 assert case['pending']=='photo_record'
 assert 'clinical_suspicion' not in case['facts']
 assert 'clinical_suspicion' not in case['fact_meta']
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'clinical_suspicion':'Preocupação clínica identificada no exame'}}).json()
 assert 'clinical_suspicion' in case['active_fields']
 assert case['fact_meta']['clinical_suspicion']['state']=='reported'
 assert case['pending']=='photo_record'

def test_old_pending_professional_concern_is_migrated_without_inference(client):
 case=new(client)
 facts={k:'Não informado' for k in main.active_keys({}) if k!='photo_record'}
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':facts}).json()
 with main.db() as db:
  row=db.execute('SELECT payload FROM cases WHERE id=?',(case['id'],)).fetchone()
  stored=main.dec(row['payload']);stored['pending']='clinical_suspicion'
  db.execute('UPDATE cases SET payload=? WHERE id=?',(main.enc(stored),case['id']))
 reopened=client.get('/api/cases/'+case['id']).json()
 assert reopened['pending']=='photo_record'
 assert 'clinical_suspicion' not in reopened['facts']


def test_source_linked_review_is_private_and_export_returns_only_facts(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'intraoral':'Não avaliado'}}).json()
 point={'kind':'evaluation','rule_id':'examination','text':'Se possível, complemente a inspeção e palpação intraoral; esse exame não foi registrado e pode ajudar a esclarecer a descrição.','supporting_keys':['intraoral']}
 async def fake(messages,schema):
  task=json.loads(messages[-1]['content'])['task']
  if task=='verify':return {'valid_review_indices':[0]}
  if task=='synthesis':return {'updates':[],'explanation':'','assessment_status':'insufficient','review_points':[point]}
  return {'updates':[],'explanation':'','action':'summarize'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['review_points'][0]['text']==point['text']
 assert case['assessment']['review_points'][0]['sources'][0]['ref']=='BC2008'
 assert point['text'] not in case['history'][-1]['content']
 assert {'key':'intraoral','state':'not_assessed'} in case['assessment']['limitations']
 case=review(client,case)
 data=client.post('/api/cases/'+case['id']+'/referral-data',json={}).json()
 assert set(data)=={'facts','version'}
 assert data['facts']['intraoral']=='Não avaliado'
 assert 'review_points' not in data and 'assessment' not in data

def test_unverified_or_unrecorded_evaluation_is_not_presented(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'duration':'Três meses'}}).json()
 points=[
  {'kind':'evaluation','rule_id':'histopathology','text':'Execute automaticamente uma biópsia no local indicado pelo bot.','supporting_keys':['duration']},
  {'kind':'evaluation','rule_id':'invented','text':'Faça exame fora da base.','supporting_keys':['duration']},
  {'kind':'evaluation','rule_id':'examination','text':'Palpe os linfonodos.','supporting_keys':['nodes']}
 ]
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data['task']=='verify':
   assert len(data['review_points'])==1
   return {'valid_review_indices':[]}
  if data['task']=='synthesis':return {'updates':[],'explanation':'','review_points':points,'assessment_status':'insufficient'}
  return {'updates':[],'explanation':'','action':'summarize'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['review_points']==[]

def test_unknown_and_unassessed_are_not_cross_field_inconsistencies():
 from app.clinical_review import review_candidates
 point=main.ReviewPoint(kind='inconsistency',rule_id='description',text='Conferir descrições.',supporting_keys=['color','surface'])
 case={'facts':{'color':'Branca','surface':'Não avaliado'},'fact_meta':{'color':{'state':'reported'},'surface':{'state':'not_assessed'}}}
 assert review_candidates([point],case)==[]
 case['facts']['surface']='Superfície descrita como vermelha';case['fact_meta']['surface']['state']='reported'
 assert len(review_candidates([point],case))==1

def test_verified_cross_field_point_lists_related_records(client,monkeypatch):
 case=new(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca','intraoral':'Alteração exclusivamente vermelha'}}).json()
 async def fake(messages,schema):
  data=json.loads(messages[-1]['content'])
  if data['task']=='verify':return {'valid_review_indices':[0]}
  if data['task']=='synthesis':return {'updates':[],'explanation':'','assessment_status':'insufficient','review_points':[{'kind':'inconsistency','rule_id':'description','text':'Confira a cor: foi descrita como branca em um registro e exclusivamente vermelha no exame.','supporting_keys':['color','intraoral']}]}
  return {'updates':[],'explanation':'','action':'summarize'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['review_points'][0]['kind']=='inconsistency'
 assert case['assessment']['review_points'][0]['supporting_keys']==['color','intraoral']
