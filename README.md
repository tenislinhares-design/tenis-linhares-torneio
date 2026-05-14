# Tênis Linhares — Torneios com Supabase

App teste separado para validar o módulo de torneios antes de integrar no site oficial.

## Funções

- Criar torneio
- Criar categorias
- Cadastrar atletas
- Permitir mesmo atleta em mais de uma categoria
- Marcar atleta de Linhares ou de fora
- Gerar chave por sorteio automático
- Montar chave manual
- Gerar programação automática
- 3 quadras por horário
- Jogos de 1h30
- Segunda a quinta: 16:00, 17:30, 19:00, 20:30
- Sexta: 15:30, 17:00, 18:30, 20:00, 21:30
- Lançar resultado
- Vencedor avança automaticamente
- Área pública com programação, chaves e inscritos

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

## Variáveis no Render

```env
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_SERVICE_ROLE_KEY=SUA_SERVICE_ROLE_KEY
ADMIN_PASSWORD=sua_senha
```

## Supabase

Antes de rodar o app, execute o arquivo:

```text
supabase_schema.sql
```

no SQL Editor do Supabase.
