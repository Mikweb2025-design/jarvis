
from kokoro_onnx import Kokoro
k = Kokoro('kokoro-v0_19.onnx', 'voices-v1.0.bin')
samples, rate = k.create('Ciao, sono Jarvis', voice='im_nicola', speed=1.0, lang='it')
import soundfile as sf
sf.write('/tmp/test.wav', samples, rate)
import subprocess
subprocess.run(['afplay', '/tmp/test.wav'])
