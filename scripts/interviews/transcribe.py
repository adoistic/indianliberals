#!/usr/bin/env python3
"""Transcribe + diarize interview/lecture audio, fully local, no gated models.

- ASR: mlx-whisper large-v3-turbo (Apple-Silicon GPU).
- Diarization: sherpa-onnx (pyannote segmentation + 3D-Speaker CAM++ embedding),
  auto speaker count, clustering threshold 0.8.
- Each Whisper segment is tagged with the diarization speaker that overlaps it
  most; consecutive same-speaker segments fold into one paragraph.

Resumable: skips any id whose <id>.raw.txt already exists.

Output per id (data/transcripts/):
  <id>.raw.txt        formatted body: Duration header + **Speaker N** paragraphs
  <id>.segments.json  whisper segments with assigned speaker ids

Run from repo root inside .venv-whisper:
  source .venv-whisper/bin/activate && python scripts/interviews/transcribe.py
"""
import json
import os
import subprocess
import tempfile
import wave

import numpy as np

ROOT = os.getcwd()
AUDIO = os.path.join(ROOT, "data/audio")
TRANS = os.path.join(ROOT, "data/transcripts")
META = os.path.join(ROOT, "data/interview-transcripts/meta")
IDS = os.path.join(ROOT, "data/interview-transcripts/ingest.ids")

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
SEG_MODEL = os.path.join(ROOT, "data/models/sherpa-onnx-pyannote-segmentation-3-0/model.onnx")
EMB_MODEL = os.path.join(ROOT, "data/models/3dspeaker_campplus_en.onnx")
CLUSTER_THRESHOLD = 0.8

os.makedirs(TRANS, exist_ok=True)


def ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def load_wav_samples(mp3: str) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav = tf.name
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ac", "1", "-ar", "16000", wav],
        check=True,
    )
    w = wave.open(wav)
    samples = (
        np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        / 32768.0
    )
    w.close()
    os.unlink(wav)
    return samples


def build_diarizer():
    import sherpa_onnx

    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=SEG_MODEL
            )
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=-1, threshold=CLUSTER_THRESHOLD
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    return sherpa_onnx.OfflineSpeakerDiarization(cfg)


def assign_speakers(whisper_segs, diar_turns):
    """For each whisper segment, pick the diarization speaker with max overlap."""
    out = []
    for s in whisper_segs:
        a, b = s["start"], s["end"]
        best, best_ov = None, 0.0
        for t in diar_turns:
            ov = max(0.0, min(b, t["end"]) - max(a, t["start"]))
            if ov > best_ov:
                best_ov, best = ov, t["speaker"]
        out.append(best)
    return out


def relabel(speaker_ids):
    """Map raw cluster ids to 1-indexed labels by first appearance; if only one
    distinct speaker, return None-map so we emit a plain '**Speaker**'."""
    order, nxt = {}, 1
    for sid in speaker_ids:
        if sid is not None and sid not in order:
            order[sid] = nxt
            nxt += 1
    single = len(order) <= 1
    return order, single


def format_body(vid, whisper_segs, speaker_ids, duration):
    meta = {}
    mpath = os.path.join(META, f"{vid}.json")
    if os.path.exists(mpath):
        meta = json.load(open(mpath))
    title = meta.get("title") or vid
    url = meta.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
    order, single = relabel(speaker_ids)

    def label(sid):
        if single or sid is None:
            return "Speaker"
        return f"Speaker {order[sid]}"

    lines = [f"# {title}", "", f"Source: {url}", f"Duration: {duration:.1f}s", ""]
    cur, buf, start = None, [], None
    for seg, sid in zip(whisper_segs, speaker_ids):
        lbl = label(sid)
        if lbl != cur and buf:
            lines += [f"**{cur}** ({ts(start)}):", " ".join(buf).strip(), ""]
            buf, start = [], None
        if start is None:
            start = seg["start"]
        cur = lbl
        buf.append(seg["text"].strip())
    if buf:
        lines += [f"**{cur}** ({ts(start)}):", " ".join(buf).strip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    ids = [x.strip() for x in open(IDS) if x.strip()]
    todo = [
        v
        for v in ids
        if not os.path.exists(os.path.join(TRANS, f"{v}.raw.txt"))
        and os.path.exists(os.path.join(AUDIO, f"{v}.mp3"))
    ]
    print(f"{len(todo)} to transcribe (of {len(ids)} ids)", flush=True)
    if not todo:
        return
    import mlx_whisper

    diarizer = build_diarizer()
    for n, vid in enumerate(todo, 1):
        mp3 = os.path.join(AUDIO, f"{vid}.mp3")
        print(f"[{n}/{len(todo)}] {vid} ...", end=" ", flush=True)
        try:
            # Auto-detect language: many CCS videos are Marathi/Hindi/Bengali.
            # Forcing English makes Whisper hallucinate repetition loops on
            # non-English audio. condition_on_previous_text=False further curbs
            # the loops that occur over music / long silences.
            r = mlx_whisper.transcribe(
                mp3,
                path_or_hf_repo=WHISPER_MODEL,
                verbose=False,
                condition_on_previous_text=False,
            )
            lang = r.get("language", "en")
            open(os.path.join(TRANS, f"{vid}.lang"), "w").write(lang + "\n")
            wsegs = [
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in r["segments"]
            ]
            samples = load_wav_samples(mp3)
            turns = [
                {"start": t.start, "end": t.end, "speaker": t.speaker}
                for t in diarizer.process(samples).sort_by_start_time()
            ]
            spk = assign_speakers(wsegs, turns)
            dur = wsegs[-1]["end"] if wsegs else 0.0
            nspk = len({s for s in spk if s is not None})
            for s, sid in zip(wsegs, spk):
                s["speaker"] = sid
            json.dump(wsegs, open(os.path.join(TRANS, f"{vid}.segments.json"), "w"),
                      ensure_ascii=False)
            open(os.path.join(TRANS, f"{vid}.raw.txt"), "w").write(
                format_body(vid, wsegs, spk, dur)
            )
            print(f"ok ({len(wsegs)} segs, {dur/60:.1f} min, {nspk} spk, lang={lang})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"FAILED: {e}", flush=True)


if __name__ == "__main__":
    main()
