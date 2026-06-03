import os, sys, cv2, torch, argparse, numpy as np, subprocess, time
from tqdm import tqdm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Wav2Lip'))
import face_detection
from models import Wav2Lip
import audio

device = 'mps' if torch.backends.mps.is_available() else 'cpu'
use_half = device == 'mps'  # half precision solo su MPS
mel_step_size = 16
img_size = 96

# Cache globali
_model_cache = None
_face_cache = None
_model_half = False

def load_model(path):
    global _model_cache, _model_half
    if _model_cache is not None:
        return _model_cache
    t0 = time.time()
    print('[wav2lip] loading model...')
    model = Wav2Lip()
    ckpt = torch.load(path, map_location='cpu', weights_only=False)
    model.load_state_dict(ckpt.get('state_dict', ckpt))
    model.eval()
    model = model.to(device)
    if use_half:
        try:
            model = model.half()
            _model_half = True
            print('[wav2lip] half precision enabled')
        except:
            _model_half = False
    _model_cache = model
    print(f'[wav2lip] model ready in {time.time()-t0:.1f}s')
    return _model_cache

def prepare_face(face_path, pads=[0, 10, 0, 0]):
    global _face_cache
    if _face_cache is not None:
        return _face_cache
    t0 = time.time()
    print('[wav2lip] detecting face...')
    img = cv2.imread(face_path)
    if img is None:
        raise ValueError(f'Cannot read face image: {face_path}')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    orig_h, orig_w = img.shape[:2]

    # Scala output se troppo grande (model lavora a 96x96, inutile full-res)
    MAX_OUT = 512
    scale = min(MAX_OUT / orig_w, MAX_OUT / orig_h, 1.0)
    if scale < 1:
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        img = cv2.resize(img, (new_w, new_h))
        orig_w, orig_h = new_w, new_h

    detector = face_detection.FaceAlignment(face_detection.LandmarksType._2D, flip_input=False, device='cpu')
    dets = detector.get_detections_for_batch(np.array([img]))
    if not dets or dets[0] is None:
        x1, y1, x2, y2 = 0, 0, orig_w, orig_h
    else:
        x1, y1, x2, y2 = dets[0]
        y1 = max(0, y1 - pads[0])
        y2 = min(orig_h, y2 + pads[1])
        x1 = max(0, x1 - pads[2])
        x2 = min(orig_w, x2 + pads[3])
    print(f'[wav2lip] face box: ({x1},{y1})->({x2},{y2})')
    face_img = img[y1:y2, x1:x2]
    if face_img.shape[0] < 10 or face_img.shape[1] < 10:
        face_img = cv2.resize(img, (img_size, img_size))
        y1, y2, x1, x2 = 0, orig_h, 0, orig_w
    face_img = cv2.resize(face_img, (img_size, img_size))
    _face_cache = (face_img, y1, y2, x1, x2, img, orig_h, orig_w)
    print(f'[wav2lip] face ready in {time.time()-t0:.1f}s')
    return _face_cache

def run(face_path, audio_path, out_path, pads=[0, 10, 0, 0], fps=20):
    checkpoint = os.path.join(os.path.dirname(__file__), 'Wav2Lip/checkpoints/wav2lip_gan.pth')
    if not os.path.exists(checkpoint):
        raise FileNotFoundError(f'Model not found: {checkpoint}')

    face_img, y1, y2, x1, x2, img, orig_h, orig_w = prepare_face(face_path, pads)

    t0 = time.time()
    wav = audio.load_wav(audio_path, 16000)
    mel = audio.melspectrogram(wav)
    print(f'[wav2lip] mel: {mel.shape}')

    mel_chunks = []
    mel_idx = 80.0 / fps
    i = 0
    while True:
        start = int(i * mel_idx)
        if start + mel_step_size > mel.shape[-1]:
            mel_chunks.append(mel[:, -mel_step_size:])
            break
        mel_chunks.append(mel[:, start:start+mel_step_size])
        i += 1
    print(f'[wav2lip] chunks: {len(mel_chunks)}')

    model = load_model(checkpoint)
    out_path_raw = '/tmp/wav2lip_raw.avi'
    out = cv2.VideoWriter(out_path_raw, cv2.VideoWriter_fourcc(*'DIVX'), fps, (orig_w, orig_h))

    batch_size = 16  # batch piu piccolo per MPS
    for start_idx in range(0, len(mel_chunks), batch_size):
        batch_mels = mel_chunks[start_idx:start_idx+batch_size]
        bs = len(batch_mels)
        batch_faces = np.array([face_img] * bs)

        img_masked = batch_faces.copy()
        img_masked[:, img_size//2:] = 0
        img_batch = np.concatenate([img_masked, batch_faces], axis=3) / 255.0
        img_batch = img_batch.transpose(0, 3, 1, 2)

        mel_batch = np.array(batch_mels)[:, np.newaxis, :, :]

        img_batch = torch.FloatTensor(img_batch).to(device)
        mel_batch = torch.FloatTensor(mel_batch).to(device)
        if _model_half:
            img_batch = img_batch.half()
            mel_batch = mel_batch.half()

        with torch.no_grad():
            pred = model(mel_batch, img_batch)

        pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0
        for p in pred:
            p = cv2.resize(p.astype(np.uint8), (x2-x1, y2-y1))
            frame = img.copy()
            frame[y1:y2, x1:x2] = p
            out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    out.release()
    # ffmpeg piu veloce: preset ultrafast, qualita media
    subprocess.call(
        f'ffmpeg -y -i {audio_path} -i {out_path_raw} '
        f'-strict -2 -c:v libx264 -preset ultrafast -crf 28 '
        f'-c:a aac -b:a 64k -shortest {out_path}',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print(f'[wav2lip] done in {time.time()-t0:.1f}s: {out_path}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--face', required=True)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--out', default='/tmp/wav2lip_output.mp4')
    args = parser.parse_args()
    run(args.face, args.audio, args.out)
