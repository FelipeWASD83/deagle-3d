"""Gera o modelo 3D de uma Desert Eagle Mark XIX .50 AE com cano de 6", com as animações de tiro e de recarga.

Roda dentro do Blender (o mesmo caminho do revolver-3d):

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup --python gerar.py

Opções depois de `--`: `--sem-render` pula as imagens; `--rapido` faz as imagens em meia resolução e poucas
amostras; `--leve` é o rápido com só 2 vistas, 4 núcleos e prioridade mínima do Windows (dá para rodar com o PC
ocupado); `--vistas a,b` escolhe as imagens do modo leve.

Tudo em milímetros, 1 unidade do Blender = 1 mm. Eixos: X para a frente (a boca do cano aponta para +X), Y
largura (o lado direito de quem atira é -Y, onde fica a janela de ejeção), Z para cima. O eixo do cano é Z = 0 e
X = 0 é a emenda entre o ferrolho e o bloco do cano.

As peças de perfil (armação, ferrolho, cão, gatilho, alavancas) são "almofadas": o perfil visto de lado, com os
cantos arredondados, extrudado em Y com a borda arredondada. O bloco do cano e o trilho são o mesmo tipo de peça
deitada (a seção vista de frente, extrudada em X). O cabo de borracha é um sólido de fatias ovais, e o pente e o
poço dele seguem o ângulo do cabo.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "modelo"
RENDER = PASTA / "render"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

X_BOCA = 155.0                     # a boca do cano (cano de 6")
R_ALMA = 6.4                       # calibre .50
MEIA_ARMACAO = 12.5
ANG_CABO = math.radians(12)        # o cabo (e o pente) inclinados para trás
SOBE = Vector((math.sin(ANG_CABO), 0, math.cos(ANG_CABO)))     # subindo pelo cabo
BASE_PENTE = Vector((-73.0, 0, -115))                           # centro do fundo do pente, no cabo
CURSO = 32.0                       # quanto o ferrolho recua
AVISOS = []

# ---------------------------------------------------------------- perfis 2D (x, z)

def _area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def _sem_repetidos(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append((p[0], p[1]))
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def arredondar(pts, raio_padrao, raio_min=0.0, passo_ang=math.radians(10)):
    """Arredonda cada canto do polígono fechado. Ponto pode ser (x, z) ou (x, z, raio)."""
    P = [(p[0], p[1], max(p[2] if len(p) > 2 else raio_padrao, raio_min)) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        x, z, r = P[i]
        ax, az = P[i - 1][:2]
        bx, bz = P[(i + 1) % n][:2]
        ux, uz = ax - x, az - z
        vx, vz = bx - x, bz - z
        la, lb = math.hypot(ux, uz), math.hypot(vx, vz)
        if la < 1e-6 or lb < 1e-6:
            continue
        ux, uz, vx, vz = ux / la, uz / la, vx / lb, vz / lb
        ang = math.acos(max(-1.0, min(1.0, ux * vx + uz * vz)))
        if r <= 0 or ang > math.radians(165):
            out.append((x, z))
            continue
        t = min(r / math.tan(ang / 2), 0.48 * la, 0.48 * lb)
        re = t * math.tan(ang / 2)
        bxv, bzv = ux + vx, uz + vz
        lbv = math.hypot(bxv, bzv)
        bxv, bzv = bxv / lbv, bzv / lbv
        d = re / math.sin(ang / 2)
        cx, cz = x + bxv * d, z + bzv * d
        sx, sz, ex, ez = x + ux * t, z + uz * t, x + vx * t, z + vz * t
        a0 = math.atan2(sz - cz, sx - cx)
        a1 = math.atan2(ez - cz, ex - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        m = max(2, math.ceil(abs(da) / passo_ang))
        for k in range(m + 1):
            a = a0 + da * k / m
            out.append((cx + re * math.cos(a), cz + re * math.sin(a)))
    return _sem_repetidos(out)


def recuar(pts, o):
    """Desloca o polígono para dentro em `o` (miter limitado)."""
    if o <= 0:
        return list(pts)
    n = len(pts)
    s = 1.0 if _area(pts) > 0 else -1.0
    out = []
    for i in range(n):
        px, pz = pts[i - 1]
        x, z = pts[i]
        qx, qz = pts[(i + 1) % n]
        d1x, d1z, d2x, d2z = x - px, z - pz, qx - x, qz - z
        l1, l2 = math.hypot(d1x, d1z), math.hypot(d2x, d2z)
        n1 = (-d1z * s / l1, d1x * s / l1)
        n2 = (-d2z * s / l2, d2x * s / l2)
        mx, mz = n1[0] + n2[0], n1[1] + n2[1]
        lm = math.hypot(mx, mz)
        if lm < 1e-9:
            mx, mz = n1
        else:
            mx, mz = mx / lm, mz / lm
        c = max(mx * n1[0] + mz * n1[1], 0.35)
        out.append((x + mx * o / c, z + mz * o / c))
    return out


def _cruza(pts):
    """True se o polígono fechado se cruza (O(n²), só para conferência)."""
    n = len(pts)

    def lado(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if lado(a, b, c) * lado(a, b, d) < 0 and lado(c, d, a) * lado(c, d, b) < 0:
                return True
    return False


def bez3(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def _suave(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def chaikin(pts, vezes=2):
    """Suaviza um caminho aberto mantendo as pontas."""
    for _ in range(vezes):
        novo = [pts[0]]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            novo += [(0.75 * ax + 0.25 * bx, 0.75 * az + 0.25 * bz), (0.25 * ax + 0.75 * bx, 0.25 * az + 0.75 * bz)]
        novo.append(pts[-1])
        pts = novo
    return pts


def _normais(caminho, lado):
    ns = []
    n = len(caminho)
    for i in range(n):
        ax, az = caminho[max(i - 1, 0)]
        bx, bz = caminho[min(i + 1, n - 1)]
        dx, dz = bx - ax, bz - az
        c = math.hypot(dx, dz)
        ns.append((lado * dz / c, -lado * dx / c))
    return ns


def _solido_de_aneis(nome, aneis, mat):
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in anel] for anel in aneis]
    m = len(aneis[0])
    bm.faces.new(vs[0])
    bm.faces.new(vs[-1])
    for a, b in zip(vs, vs[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new([a[k], a[k2], b[k2], b[k]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def varrer(nome, caminho, lado, meia_y, meia_n, mat, desloc=0.0, expoente=2.6, m=28):
    """Haste de seção oval arredondada correndo ao longo de um caminho (x, z).
    meia_y / meia_n: meia largura (em Y) e meia espessura (na normal), número ou função de t (0 a 1)."""
    fy = meia_y if callable(meia_y) else (lambda t: meia_y)
    fn = meia_n if callable(meia_n) else (lambda t: meia_n)
    ns = _normais(caminho, lado)
    aneis = []
    for i, ((x, z), (nx, nz)) in enumerate(zip(caminho, ns)):
        t = i / (len(caminho) - 1)
        wy, wn = fy(t), fn(t)
        cx, cz = x + nx * desloc, z + nz * desloc
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            dy = wy * _sgnpow(math.cos(a), 2 / expoente)
            dn = wn * _sgnpow(math.sin(a), 2 / expoente)
            anel.append((cx + nx * dn, dy, cz + nz * dn))
        aneis.append(anel)
    return _solido_de_aneis(nome, aneis, mat)


def _tampa_redonda(anel, f, b, centro_vizinho, w, raio, n):
    """Fatias extras que encolhem e se afastam da peça, arredondando uma ponta do cabo."""
    meio = (f + b) / 2
    eixo = (b - f).normalized()
    fora = Vector((eixo.y, -eixo.x))
    if fora.dot(meio - centro_vizinho) < 0:
        fora = -fora
    meio_l = (b - f).length / 2
    extras = []
    for k in range(1, n + 1):
        th = (math.pi / 2) * k / n
        enc, anda = raio * (1 - math.cos(th)), raio * math.sin(th)
        su, sy = max(1 - enc / meio_l, 0.05), max(1 - enc / w, 0.05)
        novo = []
        for (x, y, z) in anel:
            du = (Vector((x, z)) - meio).dot(eixo)
            pt = meio + eixo * du * su + fora * anda
            novo.append((pt.x, y * sy, pt.y))
        extras.append(novo)
    return extras


def cabo_solido(nome, frente, costas, largura, mat, m=64, expoente=2.0, raio_fundo=5.0, raio_topo=3.0,
                aneis_tampa=6, sulcos=None, alcance=0.42):
    """Cabo de madeira como sólido de fatias: cada fatia vai da linha da frente (lisa) à de trás e tem
    seção oval, com o volume puxado para trás (onde a palma encosta). `sulcos` (um valor por fatia,
    negativo = para dentro) afunda só a parte da frente da fatia, até `alcance` dela, para os sulcos
    dos dedos não ondularem os lados nem as costas. As duas pontas são arredondadas."""
    aneis = []
    for i, (f, b) in enumerate(zip(frente, costas)):
        t = i / (len(frente) - 1)
        w = largura(t)
        eixo = Vector((b[0] - f[0], b[1] - f[1])).normalized()
        sulco = sulcos[i] if sulcos else 0.0
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            u = 0.5 - 0.5 * _sgnpow(math.cos(a), 2 / expoente)
            u = u ** 0.86
            y = w * _sgnpow(math.sin(a), 2 / expoente)
            x, z = f[0] + (b[0] - f[0]) * u, f[1] + (b[1] - f[1]) * u
            if sulco and u < alcance:
                peso = (1 - u / alcance) ** 2
                x, z = x - eixo.x * sulco * peso, z - eixo.y * sulco * peso
            anel.append((x, y, z))
        aneis.append(anel)
    c = lambda i: (Vector(frente[i]) + Vector(costas[i])) / 2
    fundo = _tampa_redonda(aneis[-1], Vector(frente[-1]), Vector(costas[-1]), c(-2), largura(1.0),
                           raio_fundo, aneis_tampa)
    topo = _tampa_redonda(aneis[0], Vector(frente[0]), Vector(costas[0]), c(1), largura(0.0),
                          raio_topo, aneis_tampa)
    return _solido_de_aneis(nome, topo[::-1] + aneis + fundo, mat)


# ---------------------------------------------------------------- malhas

def objeto(nome, bm, mat=None):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def almofada(nome, pts, meia, r, mat, raio_canto=None, aneis=6):
    """Perfil (x, z) extrudado de -meia a +meia em Y com a borda arredondada de raio r."""
    base = arredondar(pts, raio_canto if raio_canto is not None else r * 1.3, raio_min=r * 1.15)
    niveis = []
    for k in range(aneis, -1, -1):
        th = (math.pi / 2) * k / aneis
        niveis.append((-(meia - r + r * math.sin(th)), r * (1 - math.cos(th))))
    for k in range(aneis + 1):
        th = (math.pi / 2) * k / aneis
        niveis.append((meia - r + r * math.sin(th), r * (1 - math.cos(th))))
    if _cruza(recuar(base, r)):
        AVISOS.append(f"{nome}: o contorno se cruza depois de recuar {r} mm (raio da borda grande demais)")
    bm = bmesh.new()
    aneis_v = []
    for y, o in niveis:
        aneis_v.append([bm.verts.new((x, y, z)) for x, z in recuar(base, o)])
    n = len(base)
    bm.faces.new(aneis_v[0])
    bm.faces.new(aneis_v[-1])
    for a, b in zip(aneis_v, aneis_v[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def tornear(nome, pts, mat, pos=(0, 0, 0), eixo='x', seg=64, fechado=False):
    """Sólido de revolução: pts = [(posição no eixo, raio)]; raio 0 vira ponta.
    `fechado` liga o último anel ao primeiro (tubos ocos)."""
    bm = bmesh.new()
    aneis = []
    for t, r in pts:
        if r < 1e-9:
            aneis.append([bm.verts.new((t, 0, 0))])
        else:
            aneis.append([bm.verts.new((t, r * math.cos(2 * math.pi * k / seg),
                                        r * math.sin(2 * math.pi * k / seg))) for k in range(seg)])
    pares = list(zip(aneis, aneis[1:]))
    if fechado:
        pares.append((aneis[-1], aneis[0]))
    for a, b in pares:
        for k in range(seg):
            k2 = (k + 1) % seg
            vs = []
            for v in (a[k % len(a)], a[k2 % len(a)], b[k2 % len(b)], b[k % len(b)]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if eixo == 'y':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    elif eixo == 'z':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=pos)
    return objeto(nome, bm, mat)


def caixa(nome, x0, x1, y0, y1, z0, z1, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = ((x1 if v.co.x > 0 else x0), (y1 if v.co.y > 0 else y0), (z1 if v.co.z > 0 else z0))
    return objeto(nome, bm, mat)


def aplicar(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    novo = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    velho = ob.data
    nome = velho.name
    ob.modifiers.clear()
    ob.data = novo
    bpy.data.meshes.remove(velho)
    novo.name = nome


def booleano(base, ferramentas, op='DIFFERENCE'):
    if not ferramentas:
        return base
    col = bpy.data.collections.new("_ferramentas")
    bpy.context.scene.collection.children.link(col)
    for f in ferramentas:
        for c in list(f.users_collection):
            c.objects.unlink(f)
        col.objects.link(f)
    mod = base.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.solver = 'MANIFOLD'
    mod.operand_type = 'COLLECTION'
    mod.collection = col
    aplicar(base)
    for f in list(col.objects):
        malha = f.data
        bpy.data.objects.remove(f)
        bpy.data.meshes.remove(malha)
    bpy.data.collections.remove(col)
    return base


def acabar(ob, bisel=0.0, segmentos=3, angulo=36):
    """Chanfro opcional nas quinas vivas e sombreamento liso só onde a curva é suave."""
    if bisel > 0:
        m = ob.modifiers.new("bisel", 'BEVEL')
        m.width = bisel
        m.segments = segmentos
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(50)
        aplicar(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(angulo)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    m = ob.modifiers.new("normais", 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.keep_sharp = True
    aplicar(ob)
    return ob


def girar(ob, rot, loc):
    ob.rotation_euler = rot
    ob.location = loc
    return ob



# ---------------------------------------------------------------- materiais e texturas

def material(nome, cor, metal=0.0, rug=0.5, imagem=None, verniz=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    if verniz:
        b.inputs["Coat Weight"].default_value = verniz
        b.inputs["Coat Roughness"].default_value = 0.12
    if imagem:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = imagem
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def ruido(linhas, colunas, celulas_y, celulas_x, rng):
    g = rng.random((celulas_y + 2, celulas_x + 2))
    ty = np.linspace(0, celulas_y, linhas, endpoint=False)
    tx = np.linspace(0, celulas_x, colunas, endpoint=False)
    iy, ix = ty.astype(int), tx.astype(int)
    fy, fx = ty - iy, tx - ix
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    iy, fy, ix, fx = iy[:, None], fy[:, None], ix[None, :], fx[None, :]
    v00, v10 = g[iy, ix], g[iy, ix + 1]
    v01, v11 = g[iy + 1, ix], g[iy + 1, ix + 1]
    return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy


def _normalizar(t):
    return (t - t.min()) / (t.max() - t.min())


def _salvar_imagem(nome, rgb):
    n = rgb.shape[0]
    px = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new(nome, n, n)
    img.pixels.foreach_set(px.ravel())
    SAIDA.mkdir(exist_ok=True)
    img.filepath_raw = str(SAIDA / f"{nome}.png")
    img.file_format = 'PNG'
    img.save()
    return img


def uv_caixa(ob, escala=1 / 200.0):
    """Projeção de caixa (cada face pelo eixo dominante da normal), para a têmpera."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        eixo = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            u, v = ((c.y, c.z), (c.x, c.z), (c.x, c.y))[eixo]
            l[uv].uv = (u * escala + 0.5, v * escala + 0.5)
    bm.to_mesh(ob.data)
    bm.free()


def _juntar(base, extra, mat):
    """Põe a malha de `extra` dentro de `base`, com o material dado, e apaga `extra`. O índice é procurado pelo
    material: o booleano deixa espaços vazios na lista de materiais da peça."""
    nomes = [m.name if m else None for m in base.data.materials]
    if mat.name not in nomes:
        base.data.materials.append(mat)
        nomes.append(mat.name)
    indice_material = nomes.index(mat.name)
    bm = bmesh.new()
    bm.from_mesh(extra.data)
    for f in bm.faces:
        f.material_index = indice_material
    tmp = bpy.data.meshes.new("_tmp")
    bm.to_mesh(tmp)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.from_mesh(tmp)
    bm.to_mesh(base.data)
    bm.free()
    malha = extra.data
    bpy.data.objects.remove(extra)
    bpy.data.meshes.remove(malha)
    bpy.data.meshes.remove(tmp)


def _pivo(ob, ponto):
    """Muda a origem da peça para o ponto em que ela gira, sem mexer na forma (peça sem transformação)."""
    p = Vector(ponto)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p


def _prender(filho, pai):
    mw = filho.matrix_world.copy()
    filho.parent = pai
    filho.matrix_world = mw


class Faixa:
    """Uma animação com nome (vira uma faixa de NLA e uma animação no GLB). As chaves de cada peça vão
    de 1 a `fim`, para todas começarem e acabarem juntas."""

    def __init__(self, nome, inicio, fim, extrapolacao='NOTHING'):
        self.nome, self.inicio, self.fim, self.extrapolacao = nome, inicio, fim, extrapolacao
        self.chaves = {}

    def k(self, ob, prop, quadro, valor, interp='BEZIER'):
        self.chaves.setdefault(ob, []).append((quadro, prop, tuple(valor), interp))

    def gravar(self, repouso):
        from bpy_extras import anim_utils
        for ob, lista in self.chaves.items():
            por_prop = {}
            for c in lista:
                por_prop.setdefault(c[1], []).append(c)
            ob.animation_data_create()
            ob.animation_data.action = None
            interps = {}
            for prop, cs in por_prop.items():
                cs.sort(key=lambda c: c[0])
                if cs[0][0] > 1:
                    cs.insert(0, (1, prop, cs[0][2], 'CONSTANT'))
                if cs[-1][0] < self.fim:
                    cs.append((self.fim, prop, cs[-1][2], 'CONSTANT'))
                for quadro, _, valor, interp in cs:
                    setattr(ob, prop, valor)
                    ob.keyframe_insert(prop, frame=quadro)
                    interps[(prop, quadro)] = interp
            acao = ob.animation_data.action
            # o keyframe_insert ignora a interpolação pedida: grava chave por chave na curva
            canais = anim_utils.action_get_channelbag_for_slot(acao, ob.animation_data.action_slot)
            for fc in canais.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = interps.get((fc.data_path, round(kp.co.x)), 'BEZIER')
            acao.name = f"{self.nome}|{ob.name}"
            trilha = ob.animation_data.nla_tracks.new()
            trilha.name = self.nome
            faixa = trilha.strips.new(self.nome, self.inicio, acao)
            faixa.extrapolation = self.extrapolacao
            ob.animation_data.action = None
            for prop, valor in repouso[ob].items():
                setattr(ob, prop, valor)


def luz_de_estudio(nome, pos, alvo, tam, forca):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co = (v.co.x * tam[0] * 2, v.co.y * tam[1] * 2, 0)
    ob = objeto(nome, bm)
    d = Vector(alvo) - Vector(pos)
    ob.rotation_euler = d.to_track_quat('Z', 'Y' if abs(d.normalized().z) < 0.9 else 'X').to_euler()
    ob.location = pos
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = forca
    saida = nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(em.outputs["Emission"], saida.inputs["Surface"])
    ob.data.materials.append(m)
    ob.visible_camera = False
    ob.visible_shadow = False
    return ob


# ---------------------------------------------------------------- a deagle


def textura_borracha():
    """Borracha pontilhada do cabo: grão fino e pontos, quase preta."""
    n = 1024
    rng = np.random.default_rng(1983)
    pontos = ruido(n, n, 220, 220, rng)
    grao = rng.random((n, n))
    manchas = ruido(n, n, 6, 6, rng)
    t = _normalizar(0.55 * pontos + 0.3 * grao + 0.15 * manchas)
    v = 0.022 + 0.035 * t
    return _salvar_imagem("borracha", v[..., None] * np.array([1.0, 1.0, 1.04]))


def prisma_x(nome, pts_yz, x0, x1, r, mat):
    """Seção vista de frente (y, z), cantos arredondados, extrudada em X de x0 a x1 com a borda de raio r."""
    ob = almofada(nome, pts_yz, (x1 - x0) / 2, r, mat)
    ob.data.transform(Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    return ob


def no_cabo(ob):
    """Leva a peça feita nas coordenadas do pente (u para a frente do cabo, s subindo por ele, origem no centro do
    fundo do pente) para o lugar dela, inclinada com o cabo."""
    ob.data.transform(Matrix.Translation(BASE_PENTE) @ Matrix.Rotation(ANG_CABO, 4, 'Y'))
    return ob


def deslocar(ob, v):
    ob.data.transform(Matrix.Translation(v))
    return ob


def pino(nome, x, z, raio, meia, mat):
    perfil = [(-meia, 0), (-meia, raio * 0.8), (-meia + 0.5, raio), (meia - 0.5, raio), (meia, raio * 0.8), (meia, 0)]
    return acabar(tornear(nome, perfil, mat, pos=(x, 0, z), eixo='y', seg=32))


def construir():
    """Proporções de uma Mark XIX de 6" (a mesma arma da Desert Eagle do CS2), medidas numa foto de lado: o bloco do
    cano é mais da metade da arma e mais baixo que o ferrolho; o ferrolho é curto, com a trava de segurança atrás e a
    serrilha na frente; o guarda-mato tem a frente reta e fica à frente da emenda; o cabo é fundo, com placas de
    borracha dos lados e a armação de metal à mostra na frente e atrás; a base do pente é grande."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inox = material("aco_inox", (0.40, 0.41, 0.43), metal=1.0, rug=0.30)
    escuro = material("aco_escuro", (0.025, 0.025, 0.028), metal=0.8, rug=0.55)
    borracha = material("borracha", (1, 1, 1), rug=0.85, imagem=textura_borracha())
    aco_pente = material("aco_pente", (0.20, 0.205, 0.22), metal=1.0, rug=0.40)
    P = {}

    # ---- bloco do cano: topo liso 3 mm abaixo do ferrolho, lados retos com um painel rebaixado comprido, a parte de
    # baixo (onde fica o cilindro de gás) afunilada e com as fendas do trilho por baixo; alma .50 e coroa na boca
    secao = [(14, 11, 3), (14, -6, 4), (9, -19, 3), (7, -22, 2), (-7, -22, 2), (-9, -19, 3), (-14, -6, 4), (-14, 11, 3)]
    cano = prisma_x("cano", secao, 0, X_BOCA, 1.4, inox)
    cortes = [tornear("_alma", [(70, 0), (70, R_ALMA), (X_BOCA + 5, R_ALMA), (X_BOCA + 5, 0)], None, seg=64),
              tornear("_coroa", [(X_BOCA - 2.2, 0), (X_BOCA - 2.2, R_ALMA), (X_BOCA + 0.6, R_ALMA + 2.8),
                                 (X_BOCA + 0.6, 0)], None, seg=64)]
    cortes += [girar(caixa(f"_raia{k}", 72, X_BOCA + 5, -0.9, 0.9, R_ALMA - 0.4, R_ALMA + 0.5),
                     (math.radians(30 + 60 * k), 0, 0), (0, 0, 0)) for k in range(6)]
    for lado in (-1, 1):
        cortes.append(deslocar(almofada(f"_painel{lado}", [(8, -3.5), (134, -3.5), (134, 7.5), (8, 7.5)], 0.8, 0.3,
                                        None, raio_canto=4), (0, lado * 14, 0)))
    cortes += [caixa(f"_trilho{k}", 40 + 9 * k, 44.5 + 9 * k, -12, 12, -24, -19.5) for k in range(12)]
    booleano(cano, cortes)
    P["cano"] = acabar(cano, 0.3, 2)
    P["massa_mira"] = acabar(almofada("massa_mira", [(140, 10), (152, 10), (151.6, 15), (149, 16.5), (143.5, 16.5),
                                                     (141, 13.5)], 1.6, 0.5, escuro))

    # ---- capuz da câmara (a traseira do cano, dentro do ferrolho): aparece pela janela e com o ferrolho aberto
    capuz = tornear("capuz", [(-36, 0), (-36, 8.4), (-35.2, 9.0), (0.5, 9.0), (0.5, 0)], inox, seg=64)
    booleano(capuz, [tornear("_camara", [(-38, 0), (-38, 7.3), (-26, 7.3), (-26, 0)], None, seg=48)])
    P["capuz"] = acabar(capuz)

    # ---- ferrolho curto: serrilha inclinada na frente, janela de ejeção à direita, trava de segurança atrás (dos
    # dois lados), alça de mira baixa, entalhe da trava do ferrolho embaixo à esquerda e canal do cão por baixo
    ferrolho = almofada("ferrolho", [(0, -17, 1.5), (0, 14, 1.5), (-84, 14, 5), (-90, 9, 3), (-90, -17, 1.5)], 14.5,
                        2.4, inox)
    cortes = []
    for lado, (x_ini, n_ranh) in ((1, (-50, 13)), (-1, (-56, 7))):
        for k in range(n_ranh):
            x0 = x_ini + 3.1 * k
            y0, y1 = (13.4, 20) if lado > 0 else (-20, -13.4)
            cortes.append(girar(caixa(f"_serrilha{k}_{lado}", -0.7, 0.7, y0, y1, -12, 11), (0, math.radians(-12), 0),
                                (x0, 0, 0)))
    cortes += [deslocar(almofada("_janela", [(-33, -6), (-5, -6), (-5, 9), (-33, 9)], 7, 1.0, None), (0, -13.5, 0)),
               caixa("_entalhe_trava", -16, 0.5, 11.5, 20, -18, -12.5),
               caixa("_canal_cao", -90.5, -55, -4.4, 4.4, -18, -12.5),
               tornear("_percussor", [(-92, 0), (-92, 1.7), (-86, 1.7), (-86, 0)], None, seg=24)]
    booleano(ferrolho, cortes)
    acabar(ferrolho, 0.3, 2)
    alca = almofada("alca", [(-71, 12.5), (-56, 12.5), (-56.5, 15.5), (-58, 17), (-69.5, 17), (-71, 15.5)], 8.5, 0.6,
                    escuro)
    booleano(alca, [caixa("_entalhe_alca", -74, -52, -1.6, 1.6, 15, 19)])
    acabar(alca, 0.2, 2)
    seguranca = tornear("_seguranca", [(-16.4, 0), (-16.4, 3.8), (-15.8, 4.5), (15.8, 4.5), (16.4, 3.8), (16.4, 0)],
                        escuro, pos=(-66, 0, 4), eixo='y', seg=32)
    booleano(seguranca, [deslocar(almofada(f"_alavanca{lado}", [(-69, 6.5), (-62, 9), (-45, 13), (-43, 10.5),
                                                               (-61, 1.5), (-69, 1.5)], 1.2, 0.45, None),
                                  (0, lado * 15.4, 0)) for lado in (-1, 1)], 'UNION')
    acabar(seguranca, 0.15, 2)
    _juntar(ferrolho, alca, escuro)
    _juntar(ferrolho, seguranca, escuro)
    P["ferrolho"] = ferrolho

    # ---- armação: rabo de andorinha comprido atrás (sob o cão), cabo fundo e inclinado 12°, poço do pente
    perfil = [(-90, -17, 1), (-93, -21, 2), (-112, -22, 4), (-119, -26, 3), (-111, -31, 5),
              (-92, -38, 12), (-109, -115, 5), (-37, -115, 5), (-22, -44, 8), (-17, -25, 2), (30, -25, 2.5),
              (30, -17, 2.5)]
    armacao = almofada("armacao", perfil, MEIA_ARMACAO, 2.2, inox)
    # a fenda do cão corre pelo rabo de andorinha: armado e empurrado pelo ferrolho, ele deita ali dentro
    booleano(armacao, [caixa("_fenda_cao", -127, -89, -4.0, 4.0, -31, -16),
                       caixa("_fenda_gatilho", -12, 4, -3.8, 3.8, -30, -22),
                       no_cabo(caixa("_poco", -24.6, 24.6, -11.1, 11.1, -20, 92))])
    P["armacao"] = acabar(armacao, 0.4, 2)

    # guarda-mato de frente reta, estriada, logo à frente da emenda
    linha = chaikin([(27, -23), (28, -38), (28, -49), (23, -55.5), (10, -56), (-8, -56), (-17, -53), (-23, -46),
                     (-26, -40)], 2)
    guarda = varrer("guarda_mato", linha, -1, 7.0, 3.2, inox, expoente=3.0)
    booleano(guarda, [caixa(f"_estria_guarda{k}", 30, 34, -10, 10, -48 + 3 * k, -46.8 + 3 * k) for k in range(6)])
    P["guarda_mato"] = acabar(guarda, angulo=40)

    # placas de borracha pontilhada dos dois lados do cabo, com o parafuso no meio
    contorno = [(-26, -21, 5), (-63, -21, 8), (-80, -38, 10), (-106, -111, 5), (-42, -111, 5)]
    punho = deslocar(almofada("empunhadura", contorno, 1.9, 1.2, borracha), (0, -14.3, 0))
    booleano(punho, [deslocar(almofada("_placa", contorno, 1.9, 1.2, borracha), (0, 14.3, 0))], 'UNION')
    acabar(punho, angulo=40)
    uv_caixa(punho, 1 / 60)
    P["empunhadura"] = punho
    P["parafuso_placa"] = pino("parafuso_placa", -66, -66, 2.8, 16.6, escuro)

    # ---- cão (desenhado abaixado; em repouso fica armado), gatilho, pinos e alavancas
    cao = almofada("cao", [(-91.2, -30), (-91.2, -2), (-92, 1.5, 1.5), (-95, 3.5, 1.5), (-100, 3, 2.5), (-103, 0, 2.5),
                           (-103, -5, 3), (-99, -16, 4), (-97, -30)], 3.4, 1.0, escuro)
    booleano(cao, [tornear("_furo_cao", [(-6, 0), (-6, 2.4), (6, 2.4), (6, 0)], None, pos=(-98.3, 0, -2.5), eixo='y',
                           seg=32)])
    P["cao"] = acabar(cao, 0.2, 2)
    P["gatilho"] = acabar(almofada("gatilho", [(0, -25), (-6, -25), (-6.5, -33), (-8.5, -42), (-10.5, -50),
                                               (-8.5, -53, 1.5), (-5, -49), (-2.5, -41), (-0.5, -32)], 3.0, 0.9,
                                   escuro))
    P["pino_cao"] = pino("pino_cao", PIVO_CAO[0], PIVO_CAO[2], 2.5, MEIA_ARMACAO + 0.6, escuro)
    P["pino_gatilho"] = pino("pino_gatilho", PIVO_GATILHO[0], PIVO_GATILHO[2], 1.8, MEIA_ARMACAO + 0.5, escuro)

    # trava do ferrolho (esquerda): gira no pino da frente, em cima do guarda-mato; a almofada de trás sobe no
    # entalhe do ferrolho quando ele fica aberto
    trava = deslocar(almofada("trava_ferrolho", [(26, -20), (26, -25.5), (20, -27), (-38, -22.6), (-45, -21),
                                                 (-46, -17.8), (-40, -17.6), (-34, -19.6), (18, -20)], 1.1, 0.45,
                              escuro), (0, 13.9, 0))
    booleano(trava, [tornear("_disco_trava", [(12.5, 0), (12.5, 3.6), (14.6, 3.6), (15.2, 3.0), (15.2, 0)], None,
                             pos=(PIVO_TRAVA[0], 0, PIVO_TRAVA[2]), eixo='y', seg=32)], 'UNION')
    P["trava_ferrolho"] = acabar(trava, 0.15, 2)
    P["botao_pente"] = acabar(tornear("botao_pente", [(11.6, 0), (11.6, 3.8), (14.0, 3.8), (14.9, 3.1), (14.9, 0)],
                                      escuro, pos=(-23.5, 0, -33), eixo='y', seg=32))

    # ---- pente de 7: corpo de aço com furos de conferência e seguidor escuro, inclinados com o cabo; a base grande
    # fica reta embaixo do cabo. A origem é o centro do fundo do pente.
    pente = almofada("pente", [(-24, -2), (24, -2), (24, 82, 4), (19, 86, 3), (-21, 86, 3), (-24, 84, 2)], 10.5, 1.8,
                     aco_pente)
    booleano(pente, [tornear(f"_furo{k}", [(-11.5, 0), (-11.5, 1.9), (11.5, 1.9), (11.5, 0)], None,
                             pos=(-14, 0, 18 + 14 * k), eixo='y', seg=24) for k in range(5)])
    acabar(pente, 0.2, 2)
    _juntar(pente, acabar(almofada("_seguidor", [(-22, 81), (18, 81), (18, 87.5), (-22, 87.5)], 9.6, 0.8, None)),
            escuro)
    no_cabo(pente)
    _juntar(pente, acabar(almofada("_base", [(-110, -114, 3), (-34, -114, 2), (-31, -118, 2), (-34, -133, 3),
                                             (-108, -130, 4)], 15.0, 2.4, None)), escuro)
    _pivo(pente, BASE_PENTE)
    P["pente"] = pente
    municao(P)
    clarao(P)
    return P


def municao(P):
    """Cartucho .50 AE: estojo de latão sem aro (com o canal do extrator) e espoleta, ponta encamisada de cobre.
    O mesmo estojo aparece duas vezes: o que sai pela janela no tiro (escondido em repouso, na câmara) e o de cima do
    pente, com a ponta, deitado no seguidor."""
    latao = material("latao", (0.80, 0.6, 0.34), metal=1.0, rug=0.3)
    espoleta = material("espoleta", (0.62, 0.6, 0.56), metal=1.0, rug=0.35)
    cobre = material("cobre", (0.72, 0.42, 0.26), metal=1.0, rug=0.32)
    estojo = tornear("estojo_ejetado", [(0, 0), (0, 6.6), (0.4, 7.0), (1.4, 7.0), (1.6, 5.7), (2.9, 5.7),
                                        (3.4, 6.95), (31.8, 6.95), (32.6, 6.75), (32.6, 0)], latao, seg=40)
    _juntar(estojo, tornear("_espoleta", [(-0.1, 0), (-0.1, 2.7), (0.2, 2.7), (0.2, 0)], None, seg=24), espoleta)
    acabar(estojo)
    estojo.location = (-34, 0, 0)
    bala = acabar(tornear("bala_topo", [(28, 0), (28, 6.35), (33, 6.35), (35.8, 5.6), (38.2, 3.9), (39.6, 1.8),
                                        (40, 0)], cobre, seg=40))
    topo = bpy.data.objects.new("estojo_topo", estojo.data)
    bpy.context.scene.collection.objects.link(topo)
    deitado = Matrix.Translation(BASE_PENTE) @ Matrix.Rotation(ANG_CABO, 4, 'Y') @ Matrix.Translation((-23, 0, 93))
    topo.matrix_world = deitado
    bala.matrix_world = deitado
    P["estojo_ejetado"], P["estojo_topo"], P["bala_topo"] = estojo, topo, bala


def clarao(P):
    """O clarão da boca: um cone de fogo e uma estrela de oito pontas, com a origem na boca do cano."""
    mat = material("clarao", (1.0, 0.78, 0.4))
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1)
    b.inputs["Emission Strength"].default_value = 40.0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=6.6, radius2=0.0, depth=38)
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(19.0, 0, 0))
    pontas = []
    for i in range(16):
        r = 22.0 if i % 2 == 0 else 5.0
        a = 2 * math.pi * i / 16
        pontas.append((r * math.cos(a), r * math.sin(a)))
    frente = [bm.verts.new((1.8, y, z)) for y, z in pontas]
    tras = [bm.verts.new((0.6, y, z)) for y, z in pontas]
    bm.faces.new(frente)
    bm.faces.new(tras)
    for i in range(16):
        j = (i + 1) % 16
        bm.faces.new([frente[i], frente[j], tras[j], tras[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    ob = objeto("clarao", bm, mat)
    ob.location = (X_BOCA + 0.4, 0, 0)
    P["clarao"] = ob


# ---------------------------------------------------------------- animações

# onde cada faixa começa na linha do tempo do .blend (30 qps) e quantos quadros ela tem
TIRO_INICIO, TIRO_FIM = 1, 14
ULTIMO_INICIO, ULTIMO_FIM = 20, 14
SECO_INICIO, SECO_FIM = 40, 10
REC_INICIO, REC_FIM = 60, 76
VAZIA_INICIO, VAZIA_FIM = 145, 86
RECUO = (-70.0, 0.0, -60.0)            # onde a mão segura: o coice gira a arma em volta daqui
PIVO_CAO = (-96.0, 0.0, -25.0)
PIVO_GATILHO = (-2.0, 0.0, -26.0)
PIVO_TRAVA = (22.0, 0.0, -23.0)       # a trava do ferrolho gira no pino da frente; a almofada dela sobe atrás
CAO_ARMADO, CAO_EMPURRADO = math.radians(-30), math.radians(-80)
GATILHO_PUXADO = math.radians(14)
TRAVA_ERGUIDA = math.radians(4)
INCLINADA = (math.radians(25), math.radians(-10), 0.0)   # a arma deitada para trocar o pente
VISTAS_ANIMACAO = {}


def animar(P):
    """Pivôs, hierarquia e as faixas: repouso, tiro, tiro_ultimo (o ferrolho fica aberto), seco (aberto, só o
    gatilho), recarregar (troca de pente com bala na câmara) e recarregar_vazia (troca e solta o ferrolho)."""
    cena = bpy.context.scene
    cena.render.fps = 30
    _pivo(P["cao"], PIVO_CAO)
    _pivo(P["gatilho"], PIVO_GATILHO)
    _pivo(P["trava_ferrolho"], PIVO_TRAVA)
    P["cao"].rotation_euler = (0, CAO_ARMADO, 0)          # semiautomática: depois de cada tiro o cão fica armado
    raiz = bpy.data.objects.new("deagle", None)
    raiz.empty_display_size = 30
    cena.collection.objects.link(raiz)
    raiz.location = RECUO
    bpy.context.view_layer.update()
    for nome, ob in P.items():
        if nome not in ("estojo_topo", "bala_topo"):
            _prender(ob, raiz)
    bpy.context.view_layer.update()
    for nome in ("estojo_topo", "bala_topo"):
        _prender(P[nome], P["pente"])
    bpy.context.view_layer.update()
    P["clarao"].scale = (0, 0, 0)
    P["estojo_ejetado"].scale = (0, 0, 0)

    fer, cao, gat, trava, botao, pente, flash, ejet = (P[n] for n in (
        "ferrolho", "cao", "gatilho", "trava_ferrolho", "botao_pente", "pente", "clarao", "estojo_ejetado"))
    animados = [raiz, fer, cao, gat, trava, botao, pente, flash, ejet]
    repouso = {ob: {"location": tuple(ob.location), "rotation_euler": tuple(ob.rotation_euler),
                    "scale": tuple(ob.scale)} for ob in animados}
    loc0 = {ob: Vector(repouso[ob]["location"]) for ob in animados}
    aberto = loc0[fer] + Vector((-CURSO, 0, 0))
    R = math.radians

    base = Faixa("repouso", 1, 2, 'HOLD')
    for ob in animados:
        for prop, valor in repouso[ob].items():
            base.k(ob, prop, 1, valor)
            base.k(ob, prop, 2, valor)
    base.gravar(repouso)

    def disparo(f, ultimo):
        """O dedo puxa o gatilho, o cão cai, clarão, o ferrolho recua (empurrando o cão), o estojo voa pela janela
        e o ferrolho volta; no último tiro ele fica aberto, preso pela trava."""
        for q, a in [(1, 0), (3, GATILHO_PUXADO), (7, GATILHO_PUXADO), (11, 0)]:
            f.k(gat, "rotation_euler", q, (0, a, 0))
        chaves_cao = [(1, CAO_ARMADO, 'BEZIER'), (3, CAO_ARMADO, 'LINEAR'), (4, 0, 'BEZIER'), (6, CAO_EMPURRADO, 'BEZIER')]
        if not ultimo:     # o cão só volta a armar quando o ferrolho já passou por cima dele
            chaves_cao += [(9, CAO_EMPURRADO, 'LINEAR'), (10, CAO_ARMADO, 'BEZIER')]
        for q, a, interp in chaves_cao:
            f.k(cao, "rotation_euler", q, (0, a, 0), interp)
        f.k(fer, "location", 4, loc0[fer])
        f.k(fer, "location", 6, aberto)
        if not ultimo:
            f.k(fer, "location", 7, aberto)
            f.k(fer, "location", 10, loc0[fer])
        else:
            f.k(trava, "rotation_euler", 5, (0, 0, 0))
            f.k(trava, "rotation_euler", 7, (0, TRAVA_ERGUIDA, 0))
        for q, esc, interp in [(3, 0, 'CONSTANT'), (4, 1.0, 'BEZIER'), (5, 1.3, 'BEZIER'), (6, 0.4, 'CONSTANT'),
                               (7, 0, 'CONSTANT')]:
            f.k(flash, "scale", q, (esc * 1.1 if esc else 0, esc, esc), interp)
        f.k(flash, "rotation_euler", 3, (0, 0, 0))
        f.k(flash, "rotation_euler", 7, (0.6, 0, 0))
        c = loc0[ejet]
        for q, esc in [(5, 0), (6, 1), (13, 1), (14, 0)]:
            f.k(ejet, "scale", q, (esc, esc, esc), 'CONSTANT')
        for q, d in [(6, (-2, -6, 3)), (8, (-6, -40, 22)), (11, (-14, -95, 30)), (13, (-20, -130, 14))]:
            f.k(ejet, "location", q, c + Vector(d))
        f.k(ejet, "rotation_euler", 6, (0, 0, 0), 'LINEAR')
        f.k(ejet, "rotation_euler", 13, (2.2, 0.6, 7.0), 'LINEAR')
        for q, giro, desl in [(4, 0, (0, 0, 0)), (6, -20, (-9, 0, 3)), (9, -8, (-3, 0, 1)), (14, 0, (0, 0, 0))]:
            f.k(raiz, "rotation_euler", q, (0, R(giro), 0))
            f.k(raiz, "location", q, loc0[raiz] + Vector(desl))

    t = Faixa("tiro", TIRO_INICIO, TIRO_FIM)
    disparo(t, False)
    t.gravar(repouso)
    u = Faixa("tiro_ultimo", ULTIMO_INICIO, ULTIMO_FIM)
    disparo(u, True)
    u.gravar(repouso)
    VISTAS_ANIMACAO["anim-tiro-ferrolho"] = TIRO_INICIO + 5

    def aberta(f, ate):
        """Ferrolho aberto, cão empurrado e trava erguida, do quadro 1 até `ate`."""
        for q in (1, ate):
            f.k(fer, "location", q, aberto)
            f.k(cao, "rotation_euler", q, (0, CAO_EMPURRADO, 0))
            f.k(trava, "rotation_euler", q, (0, TRAVA_ERGUIDA, 0))

    s = Faixa("seco", SECO_INICIO, SECO_FIM)
    aberta(s, SECO_FIM)
    for q, a in [(1, 0), (3, GATILHO_PUXADO), (6, GATILHO_PUXADO), (9, 0)]:
        s.k(gat, "rotation_euler", q, (0, a, 0))
    s.gravar(repouso)

    def trocar_pente(f, segura_ate, fim_raiz):
        """Deita a arma, aperta o botão, o pente velho cai, o novo sobe pelo cabo e entra com um tranco."""
        for q, rot, loc in [(1, (0, 0, 0), loc0[raiz]), (12, INCLINADA, loc0[raiz] + Vector((0, 0, 12))),
                            (segura_ate, INCLINADA, loc0[raiz] + Vector((0, 0, 12))), (fim_raiz, (0, 0, 0), loc0[raiz])]:
            f.k(raiz, "rotation_euler", q, rot)
            f.k(raiz, "location", q, loc)
        for q, d in [(14, 0), (16, -2.2), (22, -2.2), (25, 0)]:
            f.k(botao, "location", q, loc0[botao] + Vector((0, d, 0)))
        p0 = loc0[pente]
        # o pente só gira depois de sair inteiro do poço, e o novo se alinha com o cabo antes de entrar
        for q, pos, interp in [(16, p0, 'BEZIER'), (24, p0 - SOBE * 110, 'LINEAR'),
                               (31, p0 - SOBE * 190 + Vector((0, 0, -30)), 'CONSTANT'),
                               (37, p0 - SOBE * 150 + Vector((12, 0, 0)), 'BEZIER'), (45, p0 - SOBE * 105, 'BEZIER'),
                               (51, p0 - SOBE * 12, 'LINEAR'), (54, p0, 'BEZIER')]:
            f.k(pente, "location", q, pos, interp)
        for q, rot, interp in [(16, (0, 0, 0), 'BEZIER'), (24, (0, 0, 0), 'LINEAR'), (31, (0.3, 0.5, 0.2), 'CONSTANT'),
                               (37, (0, 0, 0), 'BEZIER')]:
            f.k(pente, "rotation_euler", q, rot, interp)
        for q, esc in [(31, 1), (32, 0), (36, 0), (37, 1)]:
            f.k(pente, "scale", q, (esc, esc, esc), 'CONSTANT')

    r = Faixa("recarregar", REC_INICIO, REC_FIM)
    trocar_pente(r, 58, 72)
    r.gravar(repouso)
    VISTAS_ANIMACAO["anim-recarga-pente"] = REC_INICIO + 24
    VISTAS_ANIMACAO["anim-recarga-entrando"] = REC_INICIO + 45

    v = Faixa("recarregar_vazia", VAZIA_INICIO, VAZIA_FIM)
    trocar_pente(v, 66, 80)
    for q, a in [(1, TRAVA_ERGUIDA), (62, TRAVA_ERGUIDA), (64, 0)]:
        v.k(trava, "rotation_euler", q, (0, a, 0))
    for q, pos, interp in [(1, aberto, 'CONSTANT'), (64, aberto, 'LINEAR'), (67, loc0[fer], 'BEZIER')]:
        v.k(fer, "location", q, pos, interp)
    for q, a, interp in [(1, CAO_EMPURRADO, 'CONSTANT'), (66, CAO_EMPURRADO, 'LINEAR'), (67, CAO_ARMADO, 'BEZIER')]:
        v.k(cao, "rotation_euler", q, (0, a, 0), interp)
    v.gravar(repouso)
    VISTAS_ANIMACAO["anim-aberta"] = VAZIA_INICIO

    cena.frame_start, cena.frame_end = 1, VAZIA_INICIO + VAZIA_FIM + 4
    for nome, quadro in [("tiro", TIRO_INICIO), ("tiro_ultimo", ULTIMO_INICIO), ("seco", SECO_INICIO),
                         ("recarregar", REC_INICIO), ("recarregar_vazia", VAZIA_INICIO)]:
        cena.timeline_markers.new(nome, frame=quadro)
    cena.frame_set(0)
    return raiz


def conferir_movimento(P):
    """Mede, em momentos das animações, quantos triângulos de cada par de peças se cruzam, comparado com o
    repouso: número que cresce muito é peça atravessando outra."""
    from mathutils.bvhtree import BVHTree
    cena = bpy.context.scene
    pares = [("ferrolho", "cao"), ("ferrolho", "armacao"), ("ferrolho", "cano"), ("ferrolho", "trava_ferrolho"),
             ("cao", "armacao"), ("cao", "empunhadura"), ("gatilho", "armacao"), ("gatilho", "guarda_mato"),
             ("pente", "armacao"), ("pente", "empunhadura"), ("botao_pente", "armacao"), ("trava_ferrolho", "armacao")]
    momentos = [("tiro, ferrolho atrás", TIRO_INICIO + 5), ("tiro, ferrolho voltando", TIRO_INICIO + 7),
                ("aberta (último tiro)", ULTIMO_INICIO + 13), ("recarga, pente saindo", REC_INICIO + 22),
                ("recarga, pente entrando", REC_INICIO + 50), ("vazia, ferrolho fechando", VAZIA_INICIO + 64)]

    def arvore(ob):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        t = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
        return t

    def contar():
        return {(a, b): len(arvore(P[a]).overlap(arvore(P[b]))) for a, b in pares}

    cena.frame_set(0)
    base = contar()
    linhas = ["", "Animações (30 qps): " + ", ".join(f"{n} {i} a {i + q - 1}" for n, i, q in [
        ("tiro", TIRO_INICIO, TIRO_FIM), ("tiro_ultimo", ULTIMO_INICIO, ULTIMO_FIM), ("seco", SECO_INICIO, SECO_FIM),
        ("recarregar", REC_INICIO, REC_FIM), ("recarregar_vazia", VAZIA_INICIO, VAZIA_FIM)]),
              "Cruzamentos entre peças (triângulos que se tocam; repouso -> no momento):"]
    for nome, quadro in momentos:
        cena.frame_set(quadro)
        agora = contar()
        mudou = [f"{a} x {b}: {base[(a, b)]} -> {agora[(a, b)]}" for a, b in pares
                 if agora[(a, b)] > base[(a, b)] + 10]
        linhas.append(f"  {nome} (quadro {quadro}): " + ("; ".join(mudou) if mudou else "nada novo"))
    cena.frame_set(0)
    linhas.append("No repouso: " + "; ".join(f"{a} x {b}: {n}" for (a, b), n in base.items() if n))
    return linhas


def relatorio(P, extra=()):
    linhas = ["DEAGLE 3D: relatório", ""]
    todos_x, todos_y, todos_z = [], [], []
    tris_total = 0
    abertas = []
    for nome, ob in P.items():
        if ob.matrix_world.to_scale().length < 1e-6:
            continue
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        x0, x1 = min(c.x for c in cs), max(c.x for c in cs)
        y0, y1 = min(c.y for c in cs), max(c.y for c in cs)
        z0, z1 = min(c.z for c in cs), max(c.z for c in cs)
        todos_x += [x0, x1]
        todos_y += [y0, y1]
        todos_z += [z0, z1]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        abertas_ob = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        tris_total += tris
        if abertas_ob:
            abertas.append(nome)
        linhas.append(f"{nome:<22} {x1 - x0:7.1f} x {y1 - y0:5.1f} x {z1 - z0:6.1f} mm  {tris:6d} triângulos"
                      f"  {'MALHA ABERTA: ' + str(abertas_ob) + ' arestas' if abertas_ob else 'fechada'}")
    linhas += ["", f"Total: {len(P)} peças, {tris_total} triângulos (sem contar as escondidas)",
               f"Comprimento {max(todos_x) - min(todos_x):.0f} mm (com o cão armado), altura "
               f"{max(todos_z) - min(todos_z):.0f} mm, largura {max(todos_y) - min(todos_y):.0f} mm",
               "Textura: borracha.png (pontilhado do cabo), gerada por código; o resto é cor lisa.",
               "As peças se sobrepõem de propósito nas junções: cada uma é um sólido fechado, não uma malha única."]
    linhas += list(extra)
    if abertas:
        linhas.append("ATENÇÃO, malha aberta em: " + ", ".join(abertas))
    for aviso in AVISOS:
        linhas.append("ATENÇÃO, " + aviso)
    texto = "\n".join(linhas)
    (SAIDA / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(texto)


# ---------------------------------------------------------------- imagens

def renderizar():
    leve = "--leve" in ARGS
    vistas_leves = ("lateral-direita", "tres-quartos")
    if "--vistas" in ARGS:
        vistas_leves = tuple(ARGS[ARGS.index("--vistas") + 1].split(","))
    rapido = "--rapido" in ARGS or leve
    cena = bpy.context.scene
    if leve:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
        except Exception:
            pass
        cena.render.threads_mode = 'FIXED'
        cena.render.threads = 4
    cena.unit_settings.system = 'METRIC'
    cena.unit_settings.scale_length = 0.001
    cena.render.engine = 'CYCLES'
    cena.cycles.device = 'CPU'
    cena.cycles.samples = 16 if leve else (24 if rapido else 256)
    cena.cycles.use_denoising = True
    cena.cycles.denoiser = 'OPENIMAGEDENOISE'
    cena.render.resolution_x, cena.render.resolution_y = 1920, 1200
    cena.render.resolution_percentage = 50 if rapido else 100
    cena.view_settings.view_transform = 'AgX'
    cena.view_settings.look = 'None'

    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.125, 1)
    cena.world = mundo

    chao = -290.0
    perfil = [(chao, 0), (chao, 1500)]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        perfil.append((chao + 700 - 700 * math.cos(a), 1500 + 700 * math.sin(a)))
    perfil += [(5000, 2200), (5000, 0)]
    fundo = tornear("fundo", perfil, material("fundo", (0.36, 0.355, 0.35), rug=0.8), eixo='z', seg=128)
    acabar(fundo, angulo=60)

    alvo = (-15, 0, -50)
    luz_de_estudio("luz_topo", (0, 0, 600), alvo, (440, 300), 5.0)
    luz_de_estudio("luz_principal", (-290, -650, 330), alvo, (300, 220), 13)
    luz_de_estudio("luz_faixa", (90, -320, 500), (30, 0, -10), (560, 45), 30)
    luz_de_estudio("luz_contra", (390, 470, 130), alvo, (200, 330), 15)
    luz_de_estudio("luz_recorte", (-550, 380, 60), alvo, (170, 300), 11)
    luz_de_estudio("luz_baixa", (220, -500, -140), alvo, (260, 90), 4)

    cam_ob = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam_ob.data.clip_start, cam_ob.data.clip_end = 5, 20000
    cena.collection.objects.link(cam_ob)
    cena.camera = cam_ob
    mira = bpy.data.objects.new("mira_camera", None)
    cena.collection.objects.link(mira)
    trava = cam_ob.constraints.new('TRACK_TO')
    trava.target = mira
    trava.track_axis = 'TRACK_NEGATIVE_Z'
    trava.up_axis = 'UP_Y'

    RENDER.mkdir(exist_ok=True)
    for velho in RENDER.glob("*.png"):
        velho.unlink()

    def foto(nome, local, ponto, lente, f=None, foco=None, quadro=0):
        if leve and nome not in vistas_leves:
            return
        cena.frame_set(quadro)
        cam_ob.location = local
        mira.location = ponto
        cam_ob.data.lens = lente
        cam_ob.data.dof.use_dof = f is not None
        if f is not None:
            cam_ob.data.dof.aperture_fstop = f
            cam_ob.data.dof.focus_distance = (Vector(local) - Vector(foco or ponto)).length
        cena.render.filepath = str(RENDER / f"{nome}.png")
        bpy.ops.render.render(write_still=True)

    foto("lateral-direita", (18, -1350, -58), (18, 0, -60), 125)
    foto("lateral-esquerda", (18, 1350, -58), (18, 0, -60), 125)
    foto("tres-quartos", (380, -600, 220), (20, 0, -55), 62, f=11, foco=(10, -15, -20))
    foto("traseira-esquerda", (-430, 450, 220), (0, 0, -55), 62, f=11, foco=(-40, 10, -30))
    foto("boca", (560, -200, 110), (140, 0, 0), 105, f=5.6, foco=(X_BOCA, 0, 0))
    foto("detalhe-cao", (-300, -260, 130), (-95, 0, -12), 105, f=5.6, foco=(-98, -5, -5))
    foto("anim-tiro-ferrolho", (18, -1350, -40), (18, 0, -45), 125, quadro=VISTAS_ANIMACAO["anim-tiro-ferrolho"])
    foto("anim-aberta", (380, -600, 220), (20, 0, -55), 62, quadro=VISTAS_ANIMACAO["anim-aberta"])
    for nome in ("anim-recarga-pente", "anim-recarga-entrando"):
        foto(nome, (150, -860, -110), (-40, 0, -120), 45, quadro=VISTAS_ANIMACAO[nome])
    cena.frame_set(0)
    cena.unit_settings.scale_length = 1.0


# ---------------------------------------------------------------- exportação

def exportar(raiz):
    SAIDA.mkdir(exist_ok=True)
    cena = bpy.context.scene
    cena.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    for ob in bpy.data.objects:
        ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SAIDA / "deagle.blend"))
    # OBJ em milímetros, parado e carregado, sem o clarão nem o estojo que voa (escondidos)
    for velho in SAIDA.glob("deagle.obj*"):
        velho.unlink()
    for ob in bpy.data.objects:
        ob.select_set(ob.type == 'MESH' and ob.name not in ("clarao", "estojo_ejetado"))
    bpy.ops.wm.obj_export(filepath=str(SAIDA / "deagle.obj"), export_materials=True, path_mode='COPY',
                          forward_axis='NEGATIVE_Z', up_axis='Y', apply_modifiers=True,
                          export_selected_objects=True)
    # GLB em metros, com uma animação por faixa, todas começando no zero
    for ob in bpy.data.objects:
        if ob.animation_data:
            for trilha in ob.animation_data.nla_tracks:
                for faixa in trilha.strips:
                    faixa.frame_start_ui = 1
    escala = bpy.data.objects.new("escala_metros", None)
    cena.collection.objects.link(escala)
    escala.scale = (0.001, 0.001, 0.001)
    raiz.parent = escala
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(SAIDA / "deagle.glb"), export_format='GLB', use_selection=False,
                              export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS')


def principal():
    P = construir()
    raiz = animar(P)
    relatorio(P, conferir_movimento(P))
    if "--sem-render" not in ARGS:
        renderizar()
        for o in list(bpy.data.objects):
            if o.name.startswith(("luz_", "fundo", "camera", "mira_camera")):
                bpy.data.objects.remove(o)
    exportar(raiz)
    print("pronto")


principal()
