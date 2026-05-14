# Tênis Linhares — Torneios V7 Fluxo Oficial

Versão de teste separada do app oficial.

## Fluxo oficial da V7

### Chaves
As chaves continuam separadas por categoria, como deve ser em torneio:

- 1ª Classe Masculina
- 2ª Classe Masculina
- 3ª Classe Masculina
- Feminino
- Iniciantes
- Duplas

Agora existem duas formas:

1. Gerar/importar chave por categoria.
2. Sortear chaves de TODAS as categorias de uma vez.

Cada categoria fica com sua chave própria.

### Programação
A programação é sempre geral do torneio inteiro.

O app gera:

- todas as categorias juntas;
- todas as fases: oitavas, quartas, semifinais e finais;
- semana inteira organizada por dia;
- máximo de 3 jogos por horário;
- 3 quadras;
- 1h30 por rodada;
- sem atleta em duas categorias no mesmo horário;
- sem ultrapassar uma partida por quadra no mesmo horário.

### Visual das chaves
A área pública mostra as chaves em desenho visual por categoria.
A tabela detalhada fica recolhida em um botão, para não parecer lista.

### Mantido das versões anteriores
- Importação inteligente de listas.
- Importação de chave por PDF/TXT/CSV/imagem.
- Exportar chave em PDF.
- Exportar programação em PDF.
- Validação de conflitos.
- Motor rápido de programação.

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
