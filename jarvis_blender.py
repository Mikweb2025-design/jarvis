#!/usr/bin/env python3
"""jarvis_blender.py — Client per blender-mcp (socket TCP porta 9876)
Protocollo: JSON su TCP, stesso formato di ahujasid/blender-mcp.
Blender deve essere aperto con l'addon blender_addon.py installato e attivo.
"""
import socket, json, time
from pathlib import Path

BLENDER_HOST = "localhost"
BLENDER_PORT = 9876
TIMEOUT      = 15  # secondi

# ── Client base ────────────────────────────────────────────────────────────

def _send(command: str, params: dict = None) -> dict:
    """Invia un comando JSON a Blender e ritorna il risultato."""
    payload = json.dumps({"type": command, "params": params or {}}).encode() + b"\n"
    try:
        with socket.create_connection((BLENDER_HOST, BLENDER_PORT), timeout=TIMEOUT) as s:
            s.sendall(payload)
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
                # prova a parsare: se valido JSON ci siamo
                try:
                    json.loads(data.decode())
                    break
                except json.JSONDecodeError:
                    pass
            return json.loads(data.decode())
    except ConnectionRefusedError:
        return {"status": "error", "message": "Blender non raggiungibile — apri Blender e attiva l'addon blender_addon.py"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _ok(resp: dict, field: str = None):
    """Estrae il risultato o ritorna il messaggio d'errore."""
    if resp.get("status") == "error":
        return f"❌ {resp.get('message', 'errore sconosciuto')}"
    result = resp.get("result", {})
    if field:
        return result.get(field, result)
    return result

# ── Scene ──────────────────────────────────────────────────────────────────

def blender_get_scene() -> str:
    """Ritorna informazioni sulla scena Blender attuale (oggetti, frame, motore render, ecc.)"""
    r = _send("get_scene_info")
    if r.get("status") == "error":
        return f"❌ {r.get('message')}"
    result = r.get("result", {})
    # Blender 5.x: struttura flat (result.name, result.objects)
    # Blender 4.x: struttura annidata (result.scene.name, result.objects)
    scene = result if "name" in result else result.get("scene", result)
    objects = result.get("objects", [])
    lines = [
        f"🎬 Scena: {scene.get('name', '?')} | Frame: {scene.get('frame_current', '?')} / {scene.get('frame_end', '?')}",
        f"   Render: {scene.get('render_engine', '?')} | FPS: {scene.get('fps', '?')}",
        f"   Oggetti ({len(objects)}) — Materiali: {result.get('materials_count','?')}:",
    ]
    for o in objects[:20]:
        loc = o.get('location', '?')
        if isinstance(loc, list):
            loc = f"[{', '.join(f'{v:.2f}' for v in loc)}]"
        lines.append(f"   • {o.get('name','?')} [{o.get('type','?')}] {loc}")
    if len(objects) > 20:
        lines.append(f"   ... e altri {len(objects)-20} oggetti")
    return "\n".join(lines)

def blender_get_object(name: str) -> str:
    """Ritorna dettagli su un oggetto specifico di Blender."""
    r = _send("get_object_info", {"name": name})
    res = _ok(r)
    if isinstance(res, str): return res
    return json.dumps(res, indent=2, ensure_ascii=False)

# ── Esecuzione codice ──────────────────────────────────────────────────────

def blender_execute(code: str) -> str:
    """Esegue codice Python arbitrario in Blender (bpy disponibile).
    Esempio: 'bpy.ops.mesh.primitive_cube_add(size=2)'"""
    r = _send("execute_code", {"code": code})
    if r.get("status") == "error":
        return f"❌ {r.get('message')}"
    result = r.get("result", {})
    out = result.get("output", "")
    return f"✅ Eseguito\n{out}" if out else "✅ Eseguito senza output"

# ── Oggetti ────────────────────────────────────────────────────────────────

def blender_create_object(object_type: str = "cube", name: str = None,
                          location: list = None, scale: list = None,
                          size: float = 1.0) -> str:
    """Crea un oggetto 3D in Blender.
    object_type: cube | sphere | cylinder | plane | torus | monkey | empty | light | camera
    location: [x, y, z]  scale: [x, y, z]"""
    loc = location or [0, 0, 0]
    scl = scale or [1, 1, 1]
    type_map = {
        "cube":     f"bpy.ops.mesh.primitive_cube_add(size={size}, location={tuple(loc)})",
        "sphere":   f"bpy.ops.mesh.primitive_uv_sphere_add(radius={size/2}, location={tuple(loc)})",
        "cylinder": f"bpy.ops.mesh.primitive_cylinder_add(radius={size/2}, depth={size}, location={tuple(loc)})",
        "plane":    f"bpy.ops.mesh.primitive_plane_add(size={size}, location={tuple(loc)})",
        "torus":    f"bpy.ops.mesh.primitive_torus_add(location={tuple(loc)})",
        "monkey":   f"bpy.ops.mesh.primitive_monkey_add(size={size}, location={tuple(loc)})",
        "empty":    f"bpy.ops.object.empty_add(location={tuple(loc)})",
        "light":    f"bpy.ops.object.light_add(type='POINT', location={tuple(loc)})",
        "camera":   f"bpy.ops.object.camera_add(location={tuple(loc)})",
        "cone":     f"bpy.ops.mesh.primitive_cone_add(radius1={size/2}, depth={size}, location={tuple(loc)})",
        "circle":   f"bpy.ops.mesh.primitive_circle_add(radius={size/2}, location={tuple(loc)})",
    }
    code = type_map.get(object_type.lower())
    if not code:
        return f"❌ Tipo non supportato: {object_type}. Usa: {', '.join(type_map.keys())}"
    # Aggiunge rinomina se richiesto
    if name:
        code += f"\nbpy.context.active_object.name = '{name}'"
    # Scale
    if scale and scale != [1, 1, 1]:
        code += f"\nbpy.context.active_object.scale = {tuple(scl)}"
    return blender_execute(code)

def blender_delete_object(name: str) -> str:
    """Elimina un oggetto dalla scena Blender per nome."""
    code = f"""
import bpy
obj = bpy.data.objects.get('{name}')
if obj:
    bpy.data.objects.remove(obj, do_unlink=True)
    print("Eliminato: {name}")
else:
    print("Oggetto non trovato: {name}")
"""
    return blender_execute(code)

def blender_set_material(object_name: str, color: list = None,
                         material_name: str = None, metallic: float = 0.0,
                         roughness: float = 0.5) -> str:
    """Imposta un materiale su un oggetto Blender.
    color: [R, G, B] valori 0-1. Crea un materiale PBR semplice."""
    r, g, b = (color or [1.0, 1.0, 1.0])[:3]
    mat_name = material_name or f"Mat_{object_name}"
    code = f"""
import bpy
obj = bpy.data.objects.get('{object_name}')
if obj:
    mat = bpy.data.materials.get('{mat_name}') or bpy.data.materials.new('{mat_name}')
    mat.use_nodes = True
    # Trova il nodo Principled BSDF per TIPO (robusto, indipendente dalla lingua/versione)
    bsdf = None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        out = None
        for node in mat.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                out = node
                break
        if out:
            mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    # Imposta gli input per indice (Base Color=0, Metallic=1, Roughness=2 nei principled)
    try:
        bsdf.inputs['Base Color'].default_value = ({r}, {g}, {b}, 1.0)
    except: pass
    try:
        bsdf.inputs['Metallic'].default_value = {metallic}
    except: pass
    try:
        bsdf.inputs['Roughness'].default_value = {roughness}
    except: pass
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
"""
    return blender_execute(code)

def blender_move_object(name: str, location: list = None,
                        rotation: list = None, scale: list = None) -> str:
    """Sposta/ruota/scala un oggetto Blender.
    rotation: [x, y, z] in radianti"""
    code_lines = [f"import bpy", f"obj = bpy.data.objects.get('{name}')"]
    code_lines.append("if obj:")
    if location:
        code_lines.append(f"    obj.location = {tuple(location)}")
    if rotation:
        code_lines.append(f"    obj.rotation_euler = {tuple(rotation)}")
    if scale:
        code_lines.append(f"    obj.scale = {tuple(scale)}")
    code_lines.append(f"    print('Oggetto {name} aggiornato')")
    code_lines.append(f"else: print('Oggetto non trovato: {name}')")
    return blender_execute("\n".join(code_lines))

# ── Render & Screenshot ────────────────────────────────────────────────────

def blender_screenshot(save_path: str = None) -> str:
    """Cattura uno screenshot del viewport 3D di Blender."""
    params = {"max_size": 1024}
    if save_path:
        params["filepath"] = save_path
    r = _send("get_viewport_screenshot", params)
    if r.get("status") == "error":
        return f"❌ {r.get('message')}"
    result = r.get("result", {})
    path = result.get("filepath") or result.get("path") or save_path
    if path:
        return f"📸 Screenshot salvato: {path}"
    # Prova a salvare base64 se presente
    img_data = result.get("image_data")
    if img_data:
        dst = save_path or "/tmp/blender_viewport.png"
        import base64
        with open(dst, "wb") as f:
            f.write(base64.b64decode(img_data))
        return f"📸 Screenshot salvato: {dst}"
    return f"📸 Screenshot catturato (nessun file path)"

def blender_render(output_path: str = "/tmp/blender_render.png",
                   frame: int = None, engine: str = "EEVEE") -> str:
    """Esegue il render della scena Blender e salva in output_path.
    engine: EEVEE | CYCLES | WORKBENCH"""
    frame_code = f"bpy.context.scene.frame_set({frame})" if frame else ""
    # Blender 4.x usa BLENDER_EEVEE, 5.x uguale
    engine_id = f"BLENDER_{engine}" if not engine.startswith("BLENDER_") else engine
    code = f"""
import bpy
{frame_code}
try:
    bpy.context.scene.render.engine = '{engine_id}'
except:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.filepath = r'{output_path}'
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 1000
bpy.context.scene.eevee.taa_render_samples = 32
bpy.ops.render.render(write_still=True)
"""
    r = blender_execute(code)
    import os
    if os.path.exists(output_path):
        size_kb = os.path.getsize(output_path) // 1024
        return f"✅ Render salvato: {output_path} ({size_kb} KB)"
    return r

def blender_setup_avatar(glb_path: str = None) -> str:
    """Importa l'avatar RPM in Blender con scena professionale (luci + camera ritratto).
    Se glb_path non specificato, usa l'avatar di Jarvis (assets/avatar.glb)."""
    import os
    if not glb_path:
        glb_path = str(Path(__file__).parent / "assets" / "avatar.glb")
    if not os.path.exists(glb_path):
        return f"❌ File non trovato: {glb_path}"

    code = f"""
import bpy, mathutils

# 1. Svuota scena (mantieni camera)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 2. Key light (area warm)
bpy.ops.object.light_add(type='AREA', location=(2, -2, 4))
key = bpy.context.active_object
key.name = 'KeyLight'
key.data.energy = 500
key.data.size = 2
key.rotation_euler = (0.9, 0.1, 0.5)

# 3. Fill light (freddo)
bpy.ops.object.light_add(type='AREA', location=(-2, -1, 2))
fill = bpy.context.active_object
fill.name = 'FillLight'
fill.data.energy = 150
fill.data.color = (0.8, 0.9, 1.0)

# 4. Rim light (blu/viola per effetto holo)
bpy.ops.object.light_add(type='SPOT', location=(-1, 2, 3))
rim = bpy.context.active_object
rim.name = 'RimLight'
rim.data.energy = 300
rim.data.color = (0.3, 0.6, 1.0)
rim.rotation_euler = (0.6, 0, -0.8)

# 5. Importa GLB
bpy.ops.import_scene.gltf(filepath=r'{glb_path}')
for obj in bpy.context.selected_objects:
    obj.location = (0, 0, 0)

# 6. Camera ritratto (busto)
bpy.ops.object.camera_add(location=(0, -0.7, 1.68))
cam = bpy.context.active_object
cam.name = 'PortraitCam'
cam.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
cam.data.lens = 85
bpy.context.scene.camera = cam

# 7. Sfondo scuro
world = bpy.context.scene.world or bpy.data.worlds.new('World')
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.02, 0.02, 0.05, 1)
    bg.inputs[1].default_value = 1.0

# 8. Render settings EEVEE
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 1000
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.film_transparent = False

# 9. VIEWPORT: material preview + inquadra l'avatar + redraw
#    (cosi l'utente VEDE l'avatar texturizzato nella finestra Blender)
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.select_set(True)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
        for region in area.regions:
            if region.type == 'WINDOW':
                try:
                    with bpy.context.temp_override(area=area, region=region):
                        bpy.ops.view3d.view_selected()
                except Exception as e:
                    print('frame err', e)
        area.tag_redraw()
"""
    r = blender_execute(code)
    # Conta oggetti nella scena
    info = _send("get_scene_info").get("result", {})
    n = info.get("object_count", "?")
    return f"✅ Avatar importato in Blender ({n} oggetti). Guarda la finestra di Blender — l'avatar è inquadrato in material preview. Di' 'renderizza' per il render finale."

def blender_focus_view() -> str:
    """Forza il viewport di Blender in material preview e inquadra tutti gli oggetti.
    Utile quando i comandi via socket non aggiornano la finestra."""
    code = """
import bpy
# Seleziona TUTTE le mesh così view_selected le inquadra tutte
bpy.ops.object.select_all(action='DESELECT')
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
for o in meshes:
    o.select_set(True)
if meshes:
    bpy.context.view_layer.objects.active = meshes[0]
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
        for region in area.regions:
            if region.type == 'WINDOW':
                try:
                    with bpy.context.temp_override(area=area, region=region):
                        if meshes:
                            bpy.ops.view3d.view_selected()
                        else:
                            bpy.ops.view3d.view_all(center=False)
                except Exception as e:
                    print('view err', e)
        area.tag_redraw()
"""
    blender_execute(code)
    return "✅ Viewport aggiornato (material preview + inquadratura)"

# ── Hyper3D Rodin (text-to-3D realistico) ──────────────────────────────────

def blender_enable_hyper3d(api_key: str = "vibecoding") -> str:
    """Abilita Hyper3D Rodin con la chiave indicata (default: trial gratuita 'vibecoding')."""
    code = f"""
import bpy
s = bpy.context.scene
s.blendermcp_use_hyper3d = True
s.blendermcp_hyper3d_mode = 'MAIN_SITE'
s.blendermcp_hyper3d_api_key = '{api_key}'
"""
    blender_execute(code)
    st = _send("get_hyper3d_status").get("result", {})
    return "✅ Hyper3D abilitato" if st.get("enabled") else "⚠ Hyper3D non abilitato"

def blender_generate_hyper3d(prompt: str, timeout: int = 150):
    """Genera un modello 3D realistico da testo via Hyper3D Rodin e lo importa.
    Ritorna (success: bool, message: str). Se fallisce (es. fondi esauriti),
    success=False così il chiamante può ripiegare sul codice LLM."""
    import time as _t
    # 1. Crea il job
    r = _send("create_rodin_job", {"text_prompt": prompt})
    res = r.get("result", r)
    if not isinstance(res, dict) or res.get("error") or res.get("status") == "error":
        return False, f"Hyper3D non disponibile: {res.get('error') or res.get('message','?')}"
    # Estrai uuid + subscription_key (struttura API deemos)
    task_uuid = res.get("uuid")
    jobs = res.get("jobs", {})
    sub_key = jobs.get("subscription_key") if isinstance(jobs, dict) else None
    if not task_uuid or not sub_key:
        return False, f"Hyper3D risposta inattesa: {str(res)[:120]}"
    # 2. Poll fino a completamento
    t0 = _t.time()
    while _t.time() - t0 < timeout:
        ps = _send("poll_rodin_job_status", {"subscription_key": sub_key}).get("result", {})
        statuses = ps.get("status_list", []) if isinstance(ps, dict) else []
        if statuses and all(s in ("Done", "Failed") for s in statuses):
            if any(s == "Failed" for s in statuses):
                return False, "Hyper3D: generazione fallita"
            break
        _t.sleep(4)
    else:
        return False, "Hyper3D: timeout generazione"
    # 3. Importa l'asset
    name = prompt[:40].strip().replace("'", "")
    imp = _send("import_generated_asset", {"task_uuid": task_uuid, "name": name})
    impres = imp.get("result", imp)
    if isinstance(impres, dict) and (impres.get("error") or impres.get("status") == "error"):
        return False, f"Hyper3D import fallito: {impres.get('error') or impres.get('message')}"
    return True, f"✅ Modello realistico '{name}' generato e importato (Hyper3D Rodin)"

# ── PolyHaven ─────────────────────────────────────────────────────────────

def blender_polyhaven_search(query: str, asset_type: str = "hdris") -> str:
    """Cerca asset su PolyHaven (hdris | textures | models).
    Richiede PolyHaven abilitato nell'addon Blender."""
    r = _send("search_polyhaven_assets", {"query": query, "asset_type": asset_type})
    res = _ok(r)
    if isinstance(res, str): return res
    assets = res.get("assets", res) if isinstance(res, dict) else res
    if isinstance(assets, list) and assets:
        lines = [f"🌐 PolyHaven — '{query}' ({asset_type}):"]
        for a in assets[:10]:
            name = a.get("name") or a.get("id", "?")
            lines.append(f"  • {name}")
        return "\n".join(lines)
    return f"Nessun risultato per '{query}' su PolyHaven"

def blender_polyhaven_download(asset_id: str, asset_type: str = "textures",
                                resolution: str = "2k") -> str:
    """Scarica e importa un asset da PolyHaven in Blender.
    Richiede PolyHaven abilitato nell'addon."""
    r = _send("download_polyhaven_asset", {
        "asset_id": asset_id, "asset_type": asset_type, "resolution": resolution
    })
    res = _ok(r)
    if isinstance(res, str): return res
    return f"✅ PolyHaven asset '{asset_id}' importato in Blender"

# ── Sketchfab ─────────────────────────────────────────────────────────────

def blender_sketchfab_search(query: str, count: int = 10) -> str:
    """Cerca modelli 3D su Sketchfab. Richiede API key configurata nell'addon."""
    r = _send("search_sketchfab_models", {"query": query, "count": count})
    res = _ok(r)
    if isinstance(res, str): return res
    models = res.get("models", res) if isinstance(res, dict) else res
    if isinstance(models, list) and models:
        lines = [f"🔍 Sketchfab — '{query}':"]
        for m in models[:10]:
            name = m.get("name", "?")
            uid = m.get("uid", "?")
            lines.append(f"  • {name}  [uid: {uid}]")
        return "\n".join(lines)
    return f"Nessun risultato Sketchfab per '{query}'"

def blender_sketchfab_download(model_id: str) -> str:
    """Scarica e importa un modello Sketchfab in Blender tramite il suo UID."""
    r = _send("download_sketchfab_model", {"model_id": model_id})
    res = _ok(r)
    if isinstance(res, str): return res
    return f"✅ Modello Sketchfab '{model_id}' importato"

# ── Status ─────────────────────────────────────────────────────────────────

def blender_status() -> str:
    """Verifica se Blender è raggiungibile e quali addon sono attivi."""
    r = _send("get_scene_info")
    if r.get("status") == "error":
        return f"🔴 Blender offline — {r.get('message')}"
    ph = _send("get_polyhaven_status").get("result", {})
    sk = _send("get_sketchfab_status").get("result", {})
    ph_ok = ph.get("polyhaven_enabled") or ph.get("enabled")
    sk_ok = sk.get("sketchfab_enabled") or sk.get("enabled")
    return (
        f"🟢 Blender connesso ({BLENDER_HOST}:{BLENDER_PORT})\n"
        f"   PolyHaven: {'✅ attivo' if ph_ok else '⚪ disabilitato'}\n"
        f"   Sketchfab:  {'✅ attivo' if sk_ok else '⚪ disabilitato'}"
    )
