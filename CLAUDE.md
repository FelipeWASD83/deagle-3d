# CLAUDE.md: deagle-3d

Modelo 3D de uma Desert Eagle Mark XIX .50 AE com cano de 6", gerado por código no Blender, com as animações de
tiro e de recarga. Criado em 16/10/2026 a pedido do Felipe ("faz uma deagle [...] faz que nem fizemos o revolver"),
com plano aprovado. A arma vai para o mod `revolver-minecraft` com 1,5 vez o dano do revólver. Repositório
público (escolha dele). O `CLAUDE.md` da raiz vale aqui também, e o `README.md` explica o projeto para ele.

## Como gerar e conferir

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python gerar.py -- --leve
```

O `gerar.bat` faz o mesmo. As opções depois de `--` são as do `revolver-3d`:

- `--sem-render` pula as imagens;
- `--rapido` faz as imagens em meia resolução;
- `--leve` faz duas vistas, com 4 núcleos e prioridade mínima;
- `--vistas a,b` escolhe as imagens do modo leve. Os nomes estão no fim de `renderizar`, inclusive os `anim-*`.

**Ele joga no mesmo PC: sem ele pedir render cheio, conferir sempre com `--leve`.**

Conferir no `modelo/relatorio.txt`:

- todas as peças têm que sair `fechada`;
- não pode haver linha `ATENÇÃO` (contorno que se cruza ao arredondar a borda);
- a conferência das animações tem que dizer "nada novo" em todos os momentos, menos o botão do pente e a trava do
  ferrolho, que entram na armação de propósito ao serem apertados e encostam nela.

## Decisões que não se desfazem sem motivo

- **A referência é a Desert Eagle do CS2, que é a Mark XIX real** (pedido dele no meio da primeira versão: "isso
  aí tá uma mistura de glock com deagle, use a do cs2 como exemplo"). As proporções saíram de uma foto de lado da
  arma real (Wikimedia Commons, `Desert-Eagle-p1030134.jpg`, 2,67 px por mm) e da imagem de inventário do CS2:
  - o bloco do cano tem ~155 mm (mais da metade da arma), com o topo 3 mm abaixo do ferrolho, um painel rebaixado
    comprido dos lados e as fendas do trilho **por baixo** (como no CS2, não em cima);
  - o ferrolho é curto (90 mm), com a trava de segurança atrás e a serrilha inclinada na frente;
  - o guarda-mato tem a frente reta e fica à frente da emenda;
  - o cabo é fundo (~70 mm), inclinado 12°, com placas de borracha dos lados e a armação de metal à mostra na frente
    e atrás;
  - a base do pente é grande e reta;
  - o rabo de andorinha é comprido, sob o cão.

  **A primeira versão** (ferrolho comprido em bloco, cabo de borracha envolvendo tudo, guarda-mato redondo,
  trilho em cima) **foi o que ele chamou de Glock: não voltar a ela.**
- **Os utilitários de geometria são cópia dos do `revolver-3d`** (`almofada`, `tornear`, `cabo_solido`, `varrer`,
  `booleano`, `acabar`, `Faixa`...): os dois projetos são independentes. Diferenças:
  - `_juntar` recebe o material, não o índice, porque o booleano deixa espaços vazios na lista de materiais. Com o
    índice, o lado juntado ficava sem material e saía branco;
  - `acabar` aplica normais com peso pela área, porque a face lisa grande do ferrolho fazia uma faixa diagonal no
    render.
- **Eixos e unidade:** 1 unidade = 1 mm, boca em +X, o lado direito de quem atira (janela de ejeção) em -Y, Z para
  cima, eixo do cano em Z = 0, X = 0 na emenda entre ferrolho e cano.
- **Metal claro e acetinado** (inox 0,40, rugosidade 0,30) e peças pequenas em aço escuro, como no revólver. O inox
  a 0,60 estourou de branco no estúdio.
- **Semiautomática:** em repouso o cão fica armado (-30°), como depois de cada tiro. No tiro o cão cai, o
  ferrolho recua 32 mm e empurra o cão até -80° (deitado na fenda do rabo de andorinha e no canal por baixo do
  ferrolho). O cão só volta a -30° quando o ferrolho já passou por cima dele.
- **Pente:**
  - o corpo segue o ângulo do cabo, e a origem é o centro do fundo (`BASE_PENTE`);
  - a base grande é reta (horizontal), juntada depois;
  - o cartucho de cima é filho do pente e usa a mesma malha do estojo que voa no tiro, porque o mod desenha os
    dois com o mesmo modelo;
  - na recarga o pente só gira depois de sair inteiro do poço, e o novo se alinha com o cabo antes de entrar.
    Sem isso ele atravessava a armação.
- **Faixas de NLA:** `repouso` (HOLD), `tiro`, `tiro_ultimo`, `seco`, `recarregar` e `recarregar_vazia`, em
  sequência na linha do tempo, com marcadores. O primeiro quadro da `recarregar_vazia` é a arma aberta: o mod usa
  ele como a pose parada com o ferrolho aberto.
- **Sem logo nem escrita da marca** no modelo.

## Quem depende deste modelo

O `revolver-minecraft` lê o `modelo/deagle.blend` pelo `ferramentas/exportar_deagle.py` de lá. Ele depende de três
coisas daqui:

- os nomes das peças;
- o empty `deagle`;
- os quadros das faixas (o início e o comprimento de cada uma estão em `ANIMACOES`, no exportador).

Os eventos (disparo, troca do pente, ferrolho) também estão no exportador e no `TemposDeagle.java` de lá.
Renomear peça ou mudar quadro aqui quebra o mod. Depois de mexer, rodar o exportador de lá e o `gradlew build`:
os testes avisam se os quadros não batem.

## O que não tem (de propósito, não foi pedido)

Sem vídeo das animações, sem fumaça, sem LOD e sem render cheio no commit (só os do `--leve`).
