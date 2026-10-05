import os,tempfile,json
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='alia-tests-')
os.environ['APP_ENV']='development'
from fastapi.testclient import TestClient
from app import main
from app.questions import FIELDS
import pytest

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
 monkeypatch.setattr(main,'model',fake)
 r=client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Sexo desconhecido, 60 anos'})
 assert r.status_code==200;data=r.json();assert data['pending']=='complaint'
 assert data['facts']['sex']=='Desconhecido'
 assert data['history'][-1]['content'].endswith(main.BY_KEY['complaint']['question'])
 assert data['history'][-1]['content'].count('?')==1

def test_model_failure_is_atomic(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):raise main.HTTPException(502,'Test failure')
 monkeypatch.setattr(main,'model',fake)
 assert client.post('/api/cases/'+case['id']+'/chat',json={'version':1,'message':'Female'}).status_code==502
 assert client.get('/api/cases/'+case['id']).json()['version']==1
 assert client.get('/api/cases/'+case['id']).json()['facts']=={}

def test_invalid_model_field_not_saved(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):return {'updates':[{'key':'diagnosis','value':'Cancer'}],'explanation':''}
 monkeypatch.setattr(main,'model',fake)
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
 assert 'never establish or confirm' in main.RULES.lower()
 assert 'neoplasias da cavidade oral.' in main.RULES
 assert len({k for k,_,_ in FIELDS})==len(FIELDS)

def test_translation_failure_not_partial(client,monkeypatch):
 async def fake(messages,schema):return {'welcome':''}
 monkeypatch.setattr(main,'model',fake)
 assert client.post('/api/localize',json={'language':'de'}).status_code==502

def test_invitation_required(client,monkeypatch):
 monkeypatch.setattr(main,'PRODUCTION',True)
 monkeypatch.delenv('REGISTRATION_CODE',raising=False)
 assert client.post('/api/register',json={'email':'blocked@example.org','password':'Long-Test-Password-2026'}).status_code==403
def test_referral_identity_not_in_case(client,monkeypatch):
 case=new(client)
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 async def fake(messages,schema):return {'updates':[],'explanation':'','action':'summarize'}
 monkeypatch.setattr(main,'model',fake)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Preparar encaminhamento'}).json()
 async def yes(messages,schema):return {'updates':[],'explanation':'','action':'yes'}
 monkeypatch.setattr(main,'model',yes)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Sim'}).json()
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
 monkeypatch.setattr(main,'model',fake)
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
  assert 'Never repeat that disclaimer' in messages[0]['content']
  return {'updates':[{'key':'sex','value':'Feminino'}],'explanation':''}
 monkeypatch.setattr(main,'model',fake)
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
 monkeypatch.setattr(main,'model',fake)
 case=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':'Corrijo: não relata dor'}).json()
 assert case['facts']['pain']=='Sem dor relatada'
 assert case['assessment']['status']=='insufficient'
 assert case['flow']['stage']=='referral_offer'

def complete_case(client):
 case=new(client)
 return client.patch('/api/cases/'+case['id'],json={'version':case['version'],'facts':{k:'Não informado' for k,_,_ in FIELDS}}).json()
def conversation(client,case,message):
 r=client.post('/api/cases/'+case['id']+'/chat',json={'version':case['version'],'message':message})
 assert r.status_code==200,r.text
 return r.json()
def mock_reply(monkeypatch,**fields):
 async def fake(messages,schema):return {'updates':[],'explanation':'',**fields}
 monkeypatch.setattr(main,'model',fake)

def test_summary_referral_then_maps_consent(client,monkeypatch):
 case=complete_case(client)
 mock_reply(monkeypatch,assessment_status='insufficient')
 case=conversation(client,case,'Pode sintetizar os achados?')
 assert case['assessment']['status']=='insufficient'
 assert 'insuficientes' in case['history'][-1]['content']
 assert case['flow']=={'stage':'referral_offer','referral_ready':False}
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==409
 mock_reply(monkeypatch,explanation='Podemos rever a ficha.')
 case=conversation(client,case,'Tenho uma dúvida sobre a ficha')
 assert case['flow']['stage']=='referral_offer' and not case['flow']['referral_ready']
 mock_reply(monkeypatch,action='yes')
 case=conversation(client,case,'Sim, quero o documento')
 assert case['flow']['referral_ready'] and case['flow']['stage']=='services_offer'
 assert client.post('/api/cases/'+case['id']+'/referral-data',json={}).status_code==200
 case=conversation(client,case,'Sim, quero buscar um serviço')
 assert case['flow']['stage']=='city' and 'cidade' in case['history'][-1]['content']
 assert 'country' not in case['flow']
 mock_reply(monkeypatch,location='Curitiba')
 case=conversation(client,case,'Curitiba')
 assert case['flow']['stage']=='country' and 'país' in case['history'][-1]['content']
 mock_reply(monkeypatch,location='Brasil')
 case=conversation(client,case,'Brasil')
 assert case['flow']['maps_ready'] and case['flow']['city']=='Curitiba' and case['flow']['country']=='Brasil'
 assert 'city' not in case['facts'] and 'country' not in case['facts']
 assert 'google.com' not in json.dumps(case['facts'])

def test_declined_offers_do_not_enable_buttons(client,monkeypatch):
 case=complete_case(client);mock_reply(monkeypatch,assessment_status='no_match')
 case=conversation(client,case,'Revisar')
 assert 'Isso não exclui' in case['history'][-1]['content']
 mock_reply(monkeypatch,action='no');case=conversation(client,case,'Não quero encaminhamento')
 assert not case['flow']['referral_ready'] and case['flow']['stage']=='services_offer'
 case=conversation(client,case,'Não quero localizar serviços')
 assert case['flow']['stage']=='done' and not case['flow'].get('maps_ready')

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
 assert case['assessment']['status']=='no_match' and not case['assessment']['possibilities']

def test_unsupported_compatibility_and_early_summary(client,monkeypatch):
 case=new(client)
 candidate={'label':'Invented lesion','reason':'Invented match','supporting_keys':['sex'],'basis_excerpt':'Invented criterion'}
 mock_reply(monkeypatch,action='summarize',assessment_status='compatible',possibilities=[candidate],explanation='Invented lesion is compatible.')
 case=conversation(client,case,'Quero encaminhar sem completar')
 assert case['pending']=='sex' and case['assessment']['status']=='no_match'
 assert 'Invented lesion' not in case['history'][-1]['content']
 assert case['flow']['stage']=='referral_offer'

def test_collection_question_answer_and_strict_schema(client,monkeypatch):
 case=new(client)
 async def fake(messages,schema):
  assert set(schema['required'])==set(schema['properties'])
  assert set(schema['$defs']['Compatibility']['required'])==set(schema['$defs']['Compatibility']['properties'])
  return {'updates':[],'explanation':'Registre apenas o que foi observado na avaliação clínica.'}
 monkeypatch.setattr(main,'model',fake)
 case=conversation(client,case,'Como registrar essa informação?')
 assert case['pending']=='sex'
 assert 'Registre apenas' in case['history'][-1]['content']
 assert case['history'][-1]['content'].count('?')==1
