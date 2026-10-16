# Deagle 3D

Uma Desert Eagle Mark XIX .50 AE com cano de 6" (a mesma arma da Desert Eagle do CS2), feita por código no
Blender, do mesmo jeito que o `revolver-3d`. Mede uns 27 cm de comprimento e 15 cm de altura e tem uns 39 mil
triângulos.

As peças ficam separadas:

- **Cano e corpo:** o bloco do cano, comprido e afunilado embaixo, com o painel rebaixado dos lados, as fendas do
  trilho por baixo, a alma .50 raiada e a massa de mira. Atrás dele fica o capuz da câmara.
- **Ferrolho:** curto, com a serrilha inclinada, a janela de ejeção à direita, a trava de segurança dos dois lados
  e a alça de mira.
- **Armação e cabo:** a armação de inox com o rabo de andorinha comprido, o guarda-mato de frente reta e estriada e
  as placas de borracha pontilhada no cabo.
- **Peças pequenas:** o cão com furo, o gatilho, a trava do ferrolho e o botão do pente.
- **Pente e munição:** o pente de 7 com a base grande e o cartucho de cima, e o estojo que voa no tiro.

O acabamento é aço inox claro e acetinado, com as peças pequenas e a base do pente em aço escuro. Não tem logo
nem escrita da marca.

## Animações

São cinco:

| Nome | Duração | O que faz |
|---|---|---|
| `tiro` | 0,47 s | Gatilho, o cão cai, clarão, o ferrolho recua empurrando o cão, o estojo sai girando pela janela, o ferrolho volta e a arma dá o coice. |
| `tiro_ultimo` | 0,47 s | O mesmo, mas o ferrolho fica aberto e a trava sobe para segurar. |
| `seco` | 0,33 s | Com o ferrolho aberto, só o gatilho vai e volta. |
| `recarregar` | 2,5 s | A arma deita, o botão é apertado, o pente velho cai, o novo sobe pelo cabo e entra com um tranco. |
| `recarregar_vazia` | 2,9 s | A mesma troca começando aberta. No fim a trava desce, o ferrolho bate para a frente e o cão fica armado. |

No `deagle.blend` elas ficam em sequência na linha do tempo, com marcadores (tiro no quadro 1, tiro_ultimo no 20,
seco no 40, recarregar no 60, recarregar_vazia no 145). No `deagle.glb` cada uma vira uma animação com nome. O
`.obj` sai parado e carregado.

## Onde estão os arquivos

| Arquivo | Para quê |
|---|---|
| `modelo/deagle.blend` | Abrir no Blender e mexer. Um objeto por peça. |
| `modelo/deagle.glb` | Visualizadores de web, Unity, Godot, Windows 3D Viewer. Em metros, com as animações. |
| `modelo/deagle.obj` (+ `.mtl` e `borracha.png`) | GameMaker e a maioria dos programas 3D. 1 unidade = 1 mm. |
| `render/*.png` | Imagens do modo leve: lado direito, três quartos e três quadros das animações (`anim-*`). |
| `modelo/relatorio.txt` | Medidas e contagem de triângulos de cada peça, e a conferência das animações. |

## Como gerar de novo

Dois cliques no `gerar.bat` (precisa do Blender 5.2 em `C:\Program Files\Blender Foundation`). Faz todas as
imagens em qualidade cheia, leva alguns minutos e ocupa o processador inteiro. Com o PC ocupado, use
`gerar.bat --leve` (duas imagens pequenas em prioridade mínima). Com `gerar.bat --sem-render`, leva segundos.

## Como mudar uma coisa

Tudo está no `gerar.py`, em milímetros, dentro de `construir()`:

- **Comprimento do cano:** troque `X_BOCA = 155.0` no começo do arquivo.
- **Inclinação do cabo:** troque `ANG_CABO = math.radians(12)`.
- **Quanto o ferrolho recua no tiro:** troque `CURSO = 32.0`.
- **Cor do inox:** em `construir()`, procure `material("aco_inox", (0.40, 0.41, 0.43)` e mude os três números
  (vermelho, verde e azul, de 0 a 1).

O mod de Minecraft (`revolver-minecraft`) usa este modelo. Mudou alguma coisa aqui, rode também o exportador de lá.
