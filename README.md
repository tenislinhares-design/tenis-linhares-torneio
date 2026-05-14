# Tênis Linhares — Torneios V3: Importação Inteligente

Versão de teste separada do app oficial.

## Novidades da V3

### Lista única com categorias misturadas
Agora você pode colar ou subir uma lista única com tudo misturado, e o app tenta separar sozinho:

```text
3ª Classe Masculina
João Silva
Pedro Santos

4ª Classe Masculina
Carlos Oliveira
Marcos Lima

2ª Classe Feminina: Maria Souza, Ana Paula
```

Também aceita:

```text
João Silva - 3ª Classe Masculina
Pedro Santos - 3ª Classe Masculina
Maria Souza - 2ª Classe Feminina
```

### Importar chave pronta por PDF/TXT/CSV
Na área de Chaves, você pode subir um PDF, TXT ou CSV.

Se o arquivo tiver confrontos:

```text
João Silva x Pedro Santos
Carlos Oliveira x BYE
```

O app gera a chave real.

Se o arquivo tiver só nomes em ordem, o app reorganiza:

```text
João Silva
Pedro Santos
Carlos Oliveira
Marcos Lima
```

E transforma em:

```text
João Silva x Pedro Santos
Carlos Oliveira x Marcos Lima
```

Depois disso a programação automática já consegue usar os jogos.

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
