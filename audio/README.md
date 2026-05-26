# Audio Assets

The browser task loads MP3 files from this directory.

Use one MP3 file per pseudoword:

```text
audio/daknik.mp3
audio/deskan.mp3
audio/dikman.mp3
```

Generate the current set with gTTS:

```bash
python3 stimulus_tools/generate_gtts_audio.py
```

For actual data collection, review the generated MP3s before use. gTTS is more
stable than browser speech synthesis, but pronunciations for pseudowords can
still require manual checking against `stimuli/pronunciation_ipa.json`.
