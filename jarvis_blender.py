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
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = ({r}, {g}, {b}, 1.0)
        bsdf.inputs['Metallic'].default_value = {metallic}
        bsdf.inputs['Roughness'].default_value = {roughness}
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    print("Materiale applicato a {object_name}")
else:
    print("Oggetto non trovato: {object_name}")
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
                   frame: int = None) -> str:
    """Esegue il render della scena Blender e salva in output_path."""
    frame_code = f"bpy.context.scene.frame_set({frame})" if frame else ""
    code = f"""
import bpy
{frame_code}
bpy.context.scene.render.filepath = r'{output_path}'
bpy.ops.render.render(write_still=True)
print("Render completato: {output_path}")
"""
    return blender_execute(code)

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
