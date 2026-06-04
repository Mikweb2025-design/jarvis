#!/usr/bin/env python3
"""jarvis_shape3d.py — Generazione text-to-3D LOCALE e GRATUITA con Shap-E (OpenAI).
Gira su Apple Silicon MPS. Nessuna API key, nessun costo, funziona offline
dopo il primo download del modello (~1.3GB).

Output: file .glb pronto da importare in Blender.
"""
import os, tempfile
from pathlib import Path

_pipe = None  # cache pipeline (caricata una sola volta)

def _get_pipe():
    """Carica (lazy) la pipeline Shap-E su MPS/CPU."""
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    from diffusers import ShapEPipeline
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    # float32 su MPS (Shap-E ha problemi con fp16 su MPS)
    _pipe = ShapEPipeline.from_pretrained(
        "openai/shap-e", torch_dtype=torch.float32
    ).to(device)
    return _pipe

def _to_np(x):
    """Converte un tensor (anche su MPS) o array in numpy."""
    import numpy as np
    if hasattr(x, "detach"):
        return x.detach().cpu().numpy()
    return np.asarray(x)

def _export_glb(mesh_obj, out_path):
    """Converte l'output mesh di Shap-E in un .glb via trimesh."""
    import numpy as np, trimesh
    verts = _to_np(mesh_obj.verts)
    faces = _to_np(mesh_obj.faces)
    # Colori vertici se disponibili
    vertex_colors = None
    try:
        ch = mesh_obj.vertex_channels
        if ch and "R" in ch:
            import numpy as _np
            rgb = _np.stack([_to_np(ch["R"]), _to_np(ch["G"]), _to_np(ch["B"])], axis=1)
            rgb = (rgb * 255).clip(0, 255).astype("uint8")
            alpha = _np.full((rgb.shape[0], 1), 255, dtype="uint8")
            vertex_colors = _np.concatenate([rgb, alpha], axis=1)
    except Exception:
        pass
    tm = trimesh.Trimesh(vertices=verts, faces=faces, vertex_colors=vertex_colors)
    # Shap-E genera con Y-up "sdraiato": ruota per metterlo in piedi (Z-up Blender)
    import numpy as _np
    R = trimesh.transformations.rotation_matrix(_np.pi / 2, [1, 0, 0])
    tm.apply_transform(R)
    tm.export(out_path)
    return out_path

def generate_3d(prompt: str, out_path: str = None,
                steps: int = 48, guidance: float = 15.0) -> dict:
    """Genera un modello 3D da testo con Shap-E (locale, gratuito).
    Ritorna {'ok': bool, 'path': str, 'error': str}."""
    if not out_path:
        out_path = os.path.join(tempfile.gettempdir(),
                                "shape3d_" + "".join(c for c in prompt[:20] if c.isalnum() or c == "_") + ".glb")
    try:
        import torch
        pipe = _get_pipe()
        gen = torch.Generator(device="cpu").manual_seed(0)
        result = pipe(
            prompt,
            guidance_scale=guidance,
            num_inference_steps=steps,
            frame_size=256,
            output_type="mesh",
        )
        mesh = result.images[0]
        _export_glb(mesh, out_path)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return {"ok": True, "path": out_path, "error": None}
        return {"ok": False, "path": None, "error": "file non creato"}
    except Exception as e:
        return {"ok": False, "path": None, "error": str(e)}


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "a cute dog"
    print(f"Generazione: {p} ...")
    r = generate_3d(p)
    print(r)
