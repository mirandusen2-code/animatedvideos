# A Four-Inch Fish Built This Six-Foot Circle

An English 9:16 documentary short about the sand nest built by a male white-spotted pufferfish off Amami Ōshima, Japan. The closing wide shot gives viewers a moment to look for the builder.

The camera, sand displacement and fins follow the measured voice track. See RESEARCH.md and DESIGN_BRIEF.md for observations and staging. UPLOAD.md contains English release metadata. The uploaded publishing material also contains the SRT, three thumbnail candidates, timed word data, frame contact sheets and measurements from the actual encoded MP4.

## Reproduce this production

Use Python 3.11 with kokoro-onnx, soundfile, scipy, faster-whisper and CPU ONNX Runtime for voiceover.py and realign.py. Set KOKORO_MODEL and KOKORO_VOICES to the Kokoro ONNX v1.0 release files. FFmpeg, FFprobe and eSpeak NG must be on PATH. The narrator is the synthetic bm_george voice. The spoken timing is measured after a pitch-preserving tempo adjustment.

The scene renderer uses Python 3.13, bpy 5.2.3 (Cycles CPU), NumPy and Pillow. post.py also uses SciPy, SoundFile and the Montserrat variable font from the Google Fonts repository. The staging workflow lives on the codex/pufferfish-sand-circle branch. It runs the camera proof before the final native frame production. The separate published-topic folder contains only the movie project.

Run `python voiceover.py`, then `python realign.py`. Set FRAME_DIR to an empty directory outside the checkout and run `bash render_missing.sh START END` for each forty-frame range. Set CLIP_DIR to a temporary batch directory, then run `python post.py clip START END`. A completed batch is reusable. Place the ordered batch directories under RUNNER_TEMP, named puffer-clip-0, puffer-clip-40 and so on. Use `python post.py finish`, `python qa_motion.py`, `python realign.py pufferfish-sand-circle.mp4` and `python qa_sheets.py` to finish and verify the export. Native frames live on disposable workers and are removed with their workspace. Only the compressed assembly clips and visual QA sheets are cached.
