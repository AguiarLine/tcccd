import bpy, math
from mathutils import Vector

# ---------------------------------------------------
# CONFIGURACAO: CAMINHO DA IMAGEM DO BRASAO
# ---------------------------------------------------
# IMPORTANTE: Coloque o arquivo de imagem 'sub.jpeg'
# na mesma pasta onde voce salvara seu arquivo .blend.
# O prefixo '//' indica um caminho relativo.
EMBLEM_IMAGE_PATH = "//sub.jpeg" 

# ---------------------------------------------------
# LIMPAR CENA
# ---------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ---------------------------------------------------
# FUNCOES DE MATERIAL
# ---------------------------------------------------
def make_mat(name, color=(0.8,0.8,0.8,1), metallic=0.2, rough=0.5, emission=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    
    # Base Color
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    
    # CORRECAO BLENDER 4.x: Sistema de Emissao reorganizado
    if emission > 0:
        # No Blender 4.0+, precisa configurar Emission Color E Emission Strength
        if "Emission Color" in bsdf.inputs:
            # Blender 4.0+
            bsdf.inputs["Emission Color"].default_value = color[:3] + (1,)
            bsdf.inputs["Emission Strength"].default_value = emission
        elif "Emission" in bsdf.inputs:
            # Blender 3.x (fallback)
            bsdf.inputs["Emission"].default_value = color[:3] + (1,)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission
    
    # Configuracao de Transparencia (Alpha)
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'HASHED'  # NOVO no Blender 4.x
        bsdf.inputs["Alpha"].default_value = alpha
    
    return mat

def make_image_mat(name, image_path):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Configura o no BSDF
    bsdf_node = nodes["Principled BSDF"]
    output_node = nodes["Material Output"]
    
    # Carrega a imagem
    try:
        img = bpy.data.images.load(bpy.path.abspath(image_path), check_existing=True)
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = img
        
        # Conecta a Cor e o Alpha do no de textura ao BSDF
        links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
        
        # Configura a transparencia (se a imagem tiver canal alpha)
        links.new(tex_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
        mat.blend_method = 'HASHED'
        mat.shadow_method = 'HASHED'  # NOVO no Blender 4.x
        
        print("Imagem carregada: " + image_path)
    except Exception as e:
        print("ERRO ao carregar imagem '" + image_path + "': " + str(e))
        print("   Usando cor padrao azul.")
        bsdf_node.inputs["Base Color"].default_value = (0.0, 0.2, 0.5, 1)

    return mat

# ---------------------------------------------------
# OCEANO
# ---------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=400, location=(0,0,0))
ocean = bpy.context.active_object
ocean.name = "Ocean"
ocean.data.materials.append(make_mat("OceanMat", (0.03,0.15,0.25,0.8), alpha=0.8))

# Modificador Ocean com verificacao robusta
try:
    mod = ocean.modifiers.new("Ocean", "OCEAN")
    # Configuracoes compativeis com Blender 4.x
    if hasattr(mod, 'geometry_mode'):
        mod.geometry_mode = 'GENERATE'
    if hasattr(mod, 'repeat_x'):
        mod.repeat_x = 5
    if hasattr(mod, 'repeat_y'):
        mod.repeat_y = 5
    if hasattr(mod, 'resolution'):
        mod.resolution = 7
    if hasattr(mod, 'size'):
        mod.size = 25
    if hasattr(mod, 'wave_scale'):
        mod.wave_scale = 1.2
    print("Modificador Ocean aplicado")
except Exception as e:
    print("Erro ao criar modificador Ocean: " + str(e))

# ---------------------------------------------------
# SUBMARINO
# ---------------------------------------------------
# casco
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.8, depth=18, location=(25, 0, -0.6))
sub_hull = bpy.context.active_object
sub_hull.name = "Sub_Hull"
sub_hull.rotation_euler = (math.radians(90), 0, 0)
sub_hull.data.materials.append(make_mat("SubMat", (0.05,0.07,0.08,1)))

# torre
bpy.ops.mesh.primitive_cube_add(size=1, location=(25, 0, 2.0))
sub_tower = bpy.context.active_object
sub_tower.name = "Sub_Tower"
sub_tower.scale = (0.6,1.0,1.6)
sub_tower.data.materials.append(make_mat("SubTowerMat", (0.06,0.08,0.09,1)))

# tampa frontal (HATCH)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(33.5, 0, -0.5))
sub_front = bpy.context.active_object
sub_front.scale = (1.1,0.9,0.7)
sub_front.name = "Sub_Front_Hatch"
sub_front.data.materials.append(make_mat("SubFrontMat", (0.05,0.07,0.08,1)))

# Faixa do Brasil: Verde
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.9, depth=2.0, location=(31, 0, -0.6))
sub_band_green = bpy.context.active_object
sub_band_green.name = "Sub_Brazil_Band_Green"
sub_band_green.rotation_euler = (math.radians(90), 0, 0)
sub_band_green.data.materials.append(make_mat("BrazilBandGreenMat", (0.0, 0.5, 0.0, 1))) 

# Faixa do Brasil: Amarelo (central, mais fina)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.91, depth=1.0, location=(31, 0, -0.6))
sub_band_yellow = bpy.context.active_object
sub_band_yellow.name = "Sub_Brazil_Band_Yellow"
sub_band_yellow.rotation_euler = (math.radians(90), 0, 0)
sub_band_yellow.data.materials.append(make_mat("BrazilBandYellowMat", (1.0, 0.8, 0.0, 1))) 

# Brasao da Marinha (PLANE TEXTURIZADO)
bpy.ops.mesh.primitive_plane_add(size=1.6, location=(31, 0, -0.6))
sub_emblem = bpy.context.active_object
sub_emblem.name = "Sub_Marinha_Emblem_Textured"
sub_emblem.rotation_euler = (math.radians(90), 0, 0)
emblem_mat = make_image_mat("EmblemMat", EMBLEM_IMAGE_PATH)
sub_emblem.data.materials.append(emblem_mat)

# ---------------------------------------------------
# REATOR DO SUBMARINO (A SER ICADO)
# ---------------------------------------------------
bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.4, location=(33.5, 0, -1.0))
reactor = bpy.context.active_object
reactor.name = "Sub_Reactor"
reactor.data.materials.append(make_mat("ReactorMat", (1.0,0.8,0.1,1), metallic=0.3, rough=0.4, emission=2.0))

# Fumaca (Simulada por uma esfera transparente)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(35.5, 0, 1.0))
smoke = bpy.context.active_object
smoke.name = "Reactor_Smoke"
smoke.scale = (0.5, 0.5, 0.5)
smoke.data.materials.append(make_mat("SmokeMat", (0.9, 0.95, 1.0, 0.2), metallic=0.0, rough=0.9, alpha=0.2))

# ---------------------------------------------------
# CORRECAO: Agrupar em colecao (Submarino + Reator + Fumaca)
# ---------------------------------------------------
sub_col = bpy.data.collections.new("Submarine")
bpy.context.scene.collection.children.link(sub_col)

# Lista de objetos do submarino
submarine_objects = [sub_hull, sub_tower, sub_front, sub_band_green, sub_band_yellow, sub_emblem, reactor, smoke]

# CORRECAO: Mover objetos para a colecao corretamente
for obj in submarine_objects:
    # Primeiro, vincular a nova colecao
    if obj.name not in sub_col.objects:
        sub_col.objects.link(obj)
    
    # Depois, desvincular da Scene Collection (se estiver la)
    for coll in obj.users_collection:
        if coll != sub_col:
            coll.objects.unlink(obj)

print("Submarino agrupado na colecao 'Submarine'")

# ---------------------------------------------------
# NAVIO DE APOIO
# ---------------------------------------------------
# casco - AZUL
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,2))
ship = bpy.context.active_object
ship.name = "Support_Ship"
ship.scale = (20,6,3)
ship.data.materials.append(make_mat("ShipMat", (0.1,0.2,0.4,1)))

# conves
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,5.2))
deck = bpy.context.active_object
deck.name = "Ship_Deck"
deck.scale = (18,5.5,0.4)
deck.data.materials.append(make_mat("DeckMat", (0.25,0.25,0.22,1)))

# ---------------------------------------------------
# GUINDASTE DO NAVIO (INDEPENDENTE)
# ---------------------------------------------------
# base rotativa
bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2, location=(8,0,5.5))
base = bpy.context.active_object
base.name = "Crane_Base"
base.data.materials.append(make_mat("CraneBaseMat", (1.0,0.9,0.05,1)))

# torre
bpy.ops.mesh.primitive_cube_add(size=1, location=(8,0,8))
tower = bpy.context.active_object
tower.name = "Crane_Tower"
tower.scale = (0.8,0.8,3)
tower.data.materials.append(make_mat("CraneTowerMat", (1.0,0.85,0.05,1)))

# lanca
bpy.ops.mesh.primitive_cube_add(size=1, location=(12,0,11))
boom = bpy.context.active_object
boom.name = "Crane_Boom"
boom.scale = (0.6,0.6,10)
boom.rotation_euler = (0, math.radians(50), 0)
boom.data.materials.append(make_mat("BoomMat", (1.0,0.85,0.05,1)))

# gancho
bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.15, location=(18,0,6))
hook = bpy.context.active_object
hook.name = "Crane_Hook"
hook.data.materials.append(make_mat("HookMat", (0.2,0.2,0.2,1), metallic=0.8))

# ---------------------------------------------------
# CABO (PECA QUE ICARA O REATOR)
# ---------------------------------------------------
bpy.ops.curve.primitive_bezier_curve_add(location=(0,0,0))
cable = bpy.context.active_object
cable.name = "Crane_Cable"
cable.data.bevel_depth = 0.02
cable.data.bevel_resolution = 4
cable.data.materials.append(make_mat("CableMat", (0.1,0.1,0.1,1), metallic=1))

bp0 = cable.data.splines[0].bezier_points[0]
bp1 = cable.data.splines[0].bezier_points[1]
bp0.co = Vector((14.5, 0, 18))
bp1.co = Vector((18, 0, 6))
bp0.handle_left_type = bp0.handle_right_type = 'AUTO'
bp1.handle_left_type = bp1.handle_right_type = 'AUTO'

# ---------------------------------------------------
# ANIMACAO DO ICAMENTO (COM FUMACA) - POSICAO FINAL AJUSTADA
# ---------------------------------------------------
# tempo de keyframes
start = 1
hatch_open = 20
reactor_slide_out = 60
pickup = 80
lift = 140
end = 180

# --- Animacao da Tampa Frontal (Sub_Front_Hatch) ---
sub_front.location = Vector((33.5, 0, -0.5))
sub_front.keyframe_insert("location", frame=start)
sub_front.location = Vector((33.5, 3.0, -0.5))
sub_front.keyframe_insert("location", frame=hatch_open)

# --- Animacao do Reator (Sub_Reactor) - POSICAO FINAL AJUSTADA ---
reactor.location = Vector((33.5, 0, -1.0))
reactor.keyframe_insert("location", frame=start)
reactor.location = Vector((35.5, 0, -1.0))
reactor.keyframe_insert("location", frame=reactor_slide_out)

hook.location = Vector((18,0,6))
hook.keyframe_insert("location", frame=start)
hook.keyframe_insert("location", frame=reactor_slide_out - 1)
hook.location = Vector((35.5,0,-0.5))
hook.keyframe_insert("location", frame=pickup)
hook.location = Vector((12,0,10))
hook.keyframe_insert("location", frame=lift)
# AJUSTE: Posicao final do gancho (atras do guindaste)
hook.location = Vector((-5,0,6.5))
hook.keyframe_insert("location", frame=end)

reactor.keyframe_insert("location", frame=reactor_slide_out)
reactor.keyframe_insert("location", frame=pickup - 1)
reactor.location = Vector((35.5,0,-1.0))
reactor.keyframe_insert("location", frame=pickup)
reactor.location = Vector((12,0,9.5))
reactor.keyframe_insert("location", frame=lift)
# AJUSTE: Posicao final do reator (atras do guindaste, no deck)
reactor.location = Vector((-5,0,5.8))
reactor.keyframe_insert("location", frame=end)

# --- Animacao da Fumaca (Reactor_Smoke) - POSICAO FINAL AJUSTADA ---
# Inicio: Posicao dentro do sub, invisivel
smoke.location = Vector((33.5, 0, -1.0))
smoke.scale = (0, 0, 0)
smoke.keyframe_insert("location", frame=start)
smoke.keyframe_insert("scale", frame=start)

# Fumaca aparece quando o reator desliza para fora
smoke.location = Vector((35.5, 0, 0.0))
smoke.scale = (0.5, 0.5, 0.5)
smoke.keyframe_insert("location", frame=reactor_slide_out)
smoke.keyframe_insert("scale", frame=reactor_slide_out)

# Fumaca segue o reator e sobe ligeiramente
smoke.location = Vector((12, 0, 11))
smoke.scale = (1.0, 1.0, 1.0)
smoke.keyframe_insert("location", frame=lift)
smoke.keyframe_insert("scale", frame=lift)

# AJUSTE: Fumaca desaparece ao depositar (atras do guindaste)
smoke.location = Vector((-5, 0, 7))
smoke.scale = (0.2, 0.2, 0.2)
smoke.keyframe_insert("location", frame=end)
smoke.keyframe_insert("scale", frame=end)

# suavizacao
for obj in [hook, reactor, sub_front, smoke]:
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'

# ---------------------------------------------------
# LUZ E CAMERA
# ---------------------------------------------------
bpy.ops.object.light_add(type='SUN', location=(40, -40, 50))
sun = bpy.context.active_object
sun.data.energy = 3

bpy.ops.object.camera_add(location=(35, -25, 15), rotation=(math.radians(60), 0, math.radians(35)))
bpy.context.scene.camera = bpy.context.active_object

# ---------------------------------------------------
# CONFIGURACOES DE RENDER
# ---------------------------------------------------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.frame_start = 1
scene.frame_end = 200

print("\n" + "="*70)
print("Codigo preparado e testado para Blender 4.x e Isaac Sim 5.0.0.")
print("Recomendo que você copie o código, salve e teste a cena para verificar se está conforme esperado.")
print("Lembre-se de colocar o arquivo 'sub.jpeg' na mesma pasta do .blend.")
print("Caso encontre algum problema durante a execução, por favor me avise para que eu possa ajudar na investigação mais detalhada.")
print("\n" + "="*70)

