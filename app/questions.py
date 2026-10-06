"""Owner-supplied collection fields; one question selected by server each turn."""
FIELDS = [
('sex','Dados iniciais','Qual é o sexo do paciente?'),
('age','Dados iniciais','Qual é a idade do paciente?'),
('complaint','Anamnese','Qual é a queixa oral principal do paciente?'),
('health','Anamnese','Qual é o histórico geral de saúde relevante?'),
('medications','Anamnese','Quais medicamentos sistêmicos estão em uso?'),
('allergies','Anamnese','Há alergias conhecidas?'),
('tobacco','Anamnese','Qual é o histórico de uso de tabaco?'),
('alcohol','Anamnese','Qual é o histórico de consumo de álcool?'),
('cancer_therapy','Anamnese','O paciente realizou ou realiza quimioterapia ou radioterapia?'),
('oral_habits','Anamnese','Há hábitos de mordiscar tecidos ou manipular objetos com a boca?'),
('diet','Anamnese','Há alimentos ou bebidas associados ao surgimento ou piora da alteração?'),
('extraoral','Exame extraoral','Quais foram os achados da inspeção da cabeça, pescoço, lábios e tecidos periorais?'),
('nodes','Exame extraoral','Quais foram os achados da palpação submandibular, cervical e supraclavicular?'),
('intraoral','Exame intraoral','Quais foram os achados da inspeção e palpação dos tecidos moles, incluindo língua, assoalho bucal e palato mole?'),
('location','Caracterização da lesão','Qual é a localização anatômica da alteração?'),
('duration','Caracterização da lesão','Há quanto tempo a alteração está presente?'),
('evolution','Caracterização da lesão','Como a alteração evoluiu desde o início?'),
('size','Caracterização da lesão','Qual é o tamanho da alteração, com a unidade de medida?'),
('shape','Caracterização da lesão','Qual é a forma da alteração?'),
('surface','Caracterização da lesão','Como é a superfície da alteração?'),
('texture','Caracterização da lesão','Como é a textura da alteração?'),
('consistency','Caracterização da lesão','Como é a consistência à palpação?'),
('borders','Caracterização da lesão','Como são os contornos e a delimitação das bordas?'),
('color','Caracterização da lesão','Qual é a coloração da alteração?'),
('scraping','Caracterização da lesão','Quando aplicável, a alteração é removível à raspagem?'),
('pain','Caracterização da lesão','Há dor espontânea ou ao toque?'),
('induration','Caracterização da lesão','Há endurecimento da alteração ou dos tecidos adjacentes?'),
('multiple','Caracterização da lesão','Há outras alterações em regiões da cavidade oral?'),
('ulceration','Caracterização da lesão','Há ulceração ou erosão?'),
('coating','Caracterização da lesão','Há película, pseudomembrana ou crosta?'),
('bleeding','Caracterização da lesão','Há sangramento ou secreção?'),
('odor','Caracterização da lesão','Há odor desagradável associado à alteração?'),
('trauma','Caracterização da lesão','Há fonte de trauma mecânico em contato com a região?'),
('irritant_timing','Caracterização da lesão','Se houver um fator irritativo, há quanto tempo atua na mesma região?'),
('photo_record','Documentação','Foi realizado registro fotográfico e das características clínicas para acompanhamento?'),
]
LABELS = ['Sexo','Idade','Queixa principal','Histórico de saúde','Medicamentos','Alergias','Tabagismo','Consumo de álcool','Quimioterapia ou radioterapia','Hábitos orais','Alimentação e fatores associados','Inspeção extraoral','Palpação de regiões linfonodais','Exame intraoral','Localização','Duração','Evolução','Tamanho','Forma','Superfície','Textura','Consistência','Bordas','Coloração','Removível à raspagem','Dor','Endurecimento','Outras alterações','Ulceração ou erosão','Película, pseudomembrana ou crosta','Sangramento ou secreção','Odor','Trauma mecânico','Tempo e localização do fator irritativo','Registro clínico e fotográfico']
EXTRA_FIELDS=[
('reticular_pattern','Contexto liquenoide','Foram observadas estrias brancas entrelaçadas ou um padrão em rede na alteração?'),
('distribution','Contexto liquenoide','Como é a distribuição da alteração: unilateral ou bilateral, simétrica ou assimétrica?'),
('medication_timing','Contexto liquenoide','Existe relação temporal entre o início da alteração e um medicamento ou produto com aromatizante, como canela?'),
('contact_relation','Contexto liquenoide','A alteração coincide com contato com restauração, material odontológico ou local de colocação de tabaco sem fumaça ou betel?'),
('clinical_suspicion','Avaliação profissional','Há alguma preocupação clínica, identificada por você no exame, que queira registrar para orientar o encaminhamento?'),
]
EXTRA_LABELS=['Padrão reticular','Distribuição e simetria','Relação temporal com medicamentos ou produtos','Relação de contato local','Suspeita clínica informada pelo profissional']
FIELDS=FIELDS[:-1]+EXTRA_FIELDS+[FIELDS[-1]]
LABELS=LABELS[:-1]+EXTRA_LABELS+[LABELS[-1]]
LICHENOID_KEYS={k for k,_,_ in EXTRA_FIELDS[:-1]}
CONTEXTUAL_KEYS={'cancer_therapy','coating','odor','clinical_suspicion'}
BY_KEY={k:{'label':LABELS[i],'question':q,'phase':p,'context':'lichenoid' if k in LICHENOID_KEYS else 'contextual' if k in CONTEXTUAL_KEYS else 'general'} for i,(k,p,q) in enumerate(FIELDS)}
GUIDANCE={
 'tobacco':('Registre tipo de tabaco, quantidade, frequência e duração quando conhecidos. Não estime dados que não foram informados.','history'),
 'alcohol':('Registre quantidade, frequência e duração quando conhecidas. A ausência desse hábito não exclui alteração relevante.','history'),
 'nodes':('Descreva região, tamanho, número, dor e mobilidade quando avaliados. Se não palpou, registre não avaliado.','examination'),
 'intraoral':('Descreva os achados observados na inspeção e palpação. Não avaliado e sem alterações são informações diferentes.','examination'),
 'size':('Informe a medida e a unidade, por exemplo 5 mm ou 5 × 10 mm. Não converta uma estimativa em medida exata.','description'),
 'duration':('Registre há quanto tempo a alteração existe. Se houve retirada de um irritante, informe separadamente quando ocorreu.','description'),
 'evolution':('Descreva estabilidade, crescimento, resolução, recorrência ou mudança focal em relação ao aspecto anterior, se conhecidos.','documentation'),
 'scraping':('Quando pertinente e avaliado, informe se o componente branco se remove à raspagem. Não avaliou e não removível são diferentes.','white_pattern'),
 'trauma':('Descreva o contato, a região e o tempo. A presença de trauma ou material em contato não estabelece a causa da alteração.','description'),
 'reticular_pattern':('Descreva se há linhas brancas entrelaçadas ou em rede. Uma placa branca isolada não estabelece esse padrão.','lichenoid_context'),
 'distribution':('Registre a distribuição da lesão principal e se há padrão semelhante do outro lado. Outras lesões continuam em triagens separadas.','lichenoid_context'),
 'medication_timing':('Informe a sequência temporal quando conhecida; não suspenda medicamento para responder ao ALIA.','lichenoid_context'),
 'contact_relation':('Registre a relação anatômica com o contato. Coincidência não prova causalidade e não justifica trocar restaurações por orientação do chatbot.','lichenoid_context'),
 'clinical_suspicion':('Registro opcional da apreciação do profissional. Não é necessário classificar a alteração para concluir a conversa. A ausência desse registro não significa ausência de suspeita; o modelo não deve preenchê-lo por inferência.','suspicious_referral'),
 'photo_record':('Informe apenas se o profissional realizou e guardou o registro. O modelo não recebe nem interpreta fotografias.','documentation'),
}
for key,(guide,rule) in GUIDANCE.items():BY_KEY[key].update({'guidance':guide,'rule_id':rule})
UNKNOWN='Não informado / desconhecido'
def active_keys(facts,contexts=()):
    return [k for k,_,_ in FIELDS if k in facts or BY_KEY[k]['context']=='general' or (BY_KEY[k]['context']=='lichenoid' and 'lichenoid' in contexts)]
def next_field(facts,contexts=()):
    return next((k for k in active_keys(facts,contexts) if k not in facts),None)
