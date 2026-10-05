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
 assert 'neoplasias da cavidade oral.' in main.RULES
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
 assert case['flow']['stage']=='services_offer'

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

def test_services_before_referral(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Sintetize')
 assert case['flow']['stage']=='services_offer' and not case['flow']['referral_ready']
 assert 'localizar' in case['history'][-1]['content']
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 mock_reply(monkeypatch,action='yes');case=conversation(client,case,'Sim')
 assert case['flow']['stage']=='city'
 mock_reply(monkeypatch,location='Curitiba');case=conversation(client,case,'Curitiba')
 assert case['flow']['stage']=='country'
 mock_reply(monkeypatch,location='Brasil');case=conversation(client,case,'Brasil')
 assert case['flow']['maps_ready'] and case['flow']['stage']=='referral_offer'
 assert not case['flow']['referral_ready'] and 'encaminhamento' in case['history'][-1]['content']
 mock_reply(monkeypatch,action='yes');case=conversation(client,case,'Quero preparar o encaminhamento')
 assert case['flow']['referral_ready'] and case['flow']['stage']=='done'
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 case=review(client,case)
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==200
 assert 'city' not in case['facts'] and 'country' not in case['facts']

def test_declined_services_still_offers_referral(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='no_match')
 case=conversation(client,case,'Revisar')
 mock_reply(monkeypatch,action='no');case=conversation(client,case,'Não quero localizar serviços')
 assert case['flow']['stage']=='referral_offer' and not case['flow'].get('maps_ready')
 case=conversation(client,case,'Não quero encaminhamento')
 assert case['flow']['stage']=='done' and not case['flow']['referral_ready']

def test_cancel_location_still_offers_referral(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Revisar');mock_reply(monkeypatch,action='yes');case=conversation(client,case,'Sim')
 mock_reply(monkeypatch,action='no');case=conversation(client,case,'Não quero informar cidade')
 assert case['flow']['stage']=='referral_offer' and not case['flow'].get('city')

def test_compatibility_requires_source_and_stated_support(client,monkeypatch):
 case=complete_case(client)
 case=client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{'color':'Branca'}}).json()
 candidate={'label':'lesões brancas','reason':'Coloração branca informada; demais dados limitados.','supporting_keys':['color'],'basis_excerpt':'Dê atenção especial a lesões brancas, vermelhas ou vermelho-brancas'}
 mock_reply(monkeypatch,assessment_status='compatible',possibilities=[candidate])
 case=conversation(client,case,'Sintetize')
 assert case['assessment']['status']=='compatible' and 'podem ser compatíveis' in case['assessment']['text']
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
 assert case['flow']['stage']=='services_offer'

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
 assert case['flow']['stage']=='services_offer'


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
