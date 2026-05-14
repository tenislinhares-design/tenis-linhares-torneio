# Tênis Linhares — Torneios V9 Revisão Final

Versão revisada ponto a ponto após a V8.

## Correções da V9

- Corrigido risco de erro na área pública quando a programação estava sem colunas de resultado.
- A área pública continua sem mostrar inscritos, quantidade de inscritos ou WhatsApp.
- Programação pública usa a data de São Paulo/Brasil para destacar o dia correto.
- A programação pública mostra somente: horário, quadra, categoria, fase, jogo e confronto.
- Resultados só aparecem na chave se você publicar resultados.
- Chaves públicas só aparecem quando publicadas.
- Programação pública só aparece quando publicada.
- Ao apagar programação, ela é ocultada automaticamente.
- Chave visual segue em SVG com conectores reais e PDF em formato de chave.

## Mantido

- Programação geral da semana inteira.
- Todas as categorias juntas.
- Validação de conflito de quadra e atleta.
- Importação inteligente de listas.
- Importação de chave por PDF/TXT/CSV/imagem.
- Download de chave e programação em PDF.

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

## Supabase

Use o `supabase_schema.sql` desta versão e rode no SQL Editor se ainda não rodou a V8.
