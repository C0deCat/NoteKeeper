NoteKeeper environment setup
============================

1. Install project dependencies:

   uv sync

2. Create local environment config:

   copy .env.example .env

3. Install FFmpeg for TorchCodec on Windows.

   TorchCodec needs a shared FFmpeg build, not only ffmpeg.exe. Use FFmpeg
   7.1.1 full shared from GyanD:

   https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-full_build-shared.zip

   Extract it, for example, to:

   C:\Users\vldtp\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared

4. Configure .env.

   Set NOTEKEEPER_FFMPEG_BIN to the extracted bin directory:

   NOTEKEEPER_FFMPEG_BIN=C:\Users\vldtp\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared\bin

   This path is used by Python on Windows to load FFmpeg DLLs required by
   torchcodec. It does not replace NOTEKEEPER_FFMPEG_PATH or
   NOTEKEEPER_FFPROBE_PATH, which are command paths for subprocess calls.

5. Verify FFmpeg:

   ffmpeg -version

   The output should show ffmpeg version 7.1.1 and shared libraries such as
   libavcodec 61, libavformat 61, and libavutil 59.

6. Verify TorchCodec manually if needed:

   uv run python -c "import os; os.add_dll_directory(r'C:\Users\vldtp\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared\bin'); import torchcodec; print('torchcodec ok')"

7. Run the application or tests:

   uv run notekeeper --help
   uv run pytest
