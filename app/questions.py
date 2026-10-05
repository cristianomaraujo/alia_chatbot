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
BY_KEY={k:{'label':LABELS[i],'question':q,'phase':p} for i,(k,p,q) in enumerate(FIELDS)}
UNKNOWN='Não informado / desconhecido'
def next_field(facts):
    return next((k for k,_,_ in FIELDS if k not in facts),None)
