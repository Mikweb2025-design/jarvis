import torch
from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
from pathlib import Path

BASE = Path(__file__).parent

pipe = DiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float32,
    use_safetensors=True
)
pipe.to("mps")
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
pipe.enable_attention_slicing()

prompt = """3D holographic AI avatar, wireframe mesh head, glowing cyan neon lines, humanoid facial structure, geometric digital patterns, floating data particles, digital coordinate grid, HUD interface fragments, futuristic cyberpunk, chroma key green background, holographic projection, Jarvis style"""

negative_prompt = "blurry, low quality, cartoon, anime, distorted, ugly, dark background, text, watermark"

print("Generating image...")
image = pipe(
    prompt=prompt,
    negative_prompt=negative_prompt,
    num_inference_steps=25,
    guidance_scale=7.5,
    height=768,
    width=768
).images[0]

output_path = str(BASE / "holographic_avatar.png")
image.save(output_path)
print(f"Image saved to {output_path}")
