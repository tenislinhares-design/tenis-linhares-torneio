# Tênis Linhares — Torneios com Supabase

App teste separado para validar o módulo de torneios antes de integrar no site oficial.

## Funções

- Criar torneio
- Criar categorias
- Cadastrar atletas
- Mesmo atleta em mais de uma categoria
- Marcar atleta de Linhares ou de fora
- Chave por sorteio automático
- Chave manual
- Programação automática
- 3 quadras por horário
- Jogos de 1h30
- Segunda a quinta: 16:00, 17:30, 19:00, 20:30
- Sexta: 15:30, 17:00, 18:30, 20:00, 21:30
- Lançar resultado
- Vencedor avança automaticamente
- Área pública com programação e chave

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Antes de rodar

1. Rode `supabase_schema.sql` no SQL Editor do Supabase.
2. Configure as variáveis do app:

```env
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_SERVICE_ROLE_KEY=SUA_CHAVE_SERVICE_ROLE
ADMIN_PASSWORD=sua_senha
```

O app também aceita `NEXT_PUBLIC_SUPABASE_URL` e `ADMIN_TOKEN` se você quiser reaproveitar nomes antigos.
