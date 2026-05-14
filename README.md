# Tênis Linhares — Torneios V4 Estável

Correção da versão V3 para reduzir erro `httpx.ReadError: Recursos temporariamente indisponíveis`.

## O que mudou

- Adiciona repetição automática de chamadas ao Supabase.
- Reduz chamadas repetidas na tela de categorias.
- Mostra erro amigável se o Render/Supabase oscilar.
- Mantém a importação inteligente de listas.
- Mantém importação de chave por PDF/TXT/CSV.
- Mantém programação automática e avanço de vencedores.

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

Depois de atualizar no GitHub:

```text
Manual Deploy > Clear build cache & deploy
```
