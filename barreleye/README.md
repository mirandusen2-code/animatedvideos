# MindBlown 3D · Barreleye

Open barreleye.mp4 to watch the finished 9:16 Short. The film includes animated captions. barreleye.srt supplies optional platform subtitles. The three high-resolution covers are in thumbnails/. The original research, reconstruction choices, measured QA results and upload copy are included alongside the film.

## Recreate the edit

Use Python plus Pillow, NumPy, SciPy, SoundFile, imageio-ffmpeg and OpenCV. The scene was rendered with bpy 5.2.3, Cycles CPU and OIDN. Commands assume the working directory is the extracted topic folder. Linux also needs Blender's standard OpenGL and X11 runtime libraries (headless use). Install FFmpeg on PATH.

1. The approved synthetic male voice, reference, takes and timing are included. To recast from scratch, generate the documented Kokoro bm_george guide using kokoro-onnx and the environment variables KOKORO_MODEL and KOKORO_VOICES. In a separate Python 3.11 environment with CPU PyTorch, chatterbox-tts, faster-whisper, NumPy and SoundFile, run voiceover.py. Each take has its own ASR log. realign.py builds the full-track timings with small.en. The delivery edit uses a 0.90 tempo setting without pitch change.
2. Run bash render_missing.sh inside the bpy environment. Each image is an original native pixel crop of the 1080 × 1920 camera. Only the occupied scanlines are traced; post.py composites them 1:1 into the full-resolution open water. Nothing is enlarged. The deliverable contains the procedural scene and a Blender file of the opening pose. Eye, fin, water and camera animation are driven by scene.py.
3. Run python post.py all, then python qa_motion.py, python qa_sheets.py and python thumbnails.py. Run check_transcript.py in the Whisper environment to verify the encoded sound. The music, foley and narration have been assembled and mastered across the loop in three consecutive periods. The video and audio duration are derived from the same integer frame count.
4. RESEARCH.md contains the scientific sources. Montserrat is distributed with its SIL Open Font License. The physiological notes and poses are educational reconstructions.

The project uses no downloaded animal imagery or audio of an identifiable person. The full rendering is reproducible without the temporary distributed render service.
