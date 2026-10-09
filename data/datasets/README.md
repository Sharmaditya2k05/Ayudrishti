# Datasets

AyuDrishti works with **no dataset at all**. Pose recognition and assessment
are both driven by the explicit alignment rules in `data/pose_rules/`, which
need no training data and can explain every decision they make.

Datasets are used for two optional things:

1. **Evaluating the rules.** Running the assessment engine over labelled
   photographs shows how well hand-written thresholds hold up against real
   bodies, camera angles and clothing.
2. **Training the optional classifier** (`ai/pose_recognition/classifier.py`),
   which can improve recognition at awkward viewing angles.

## Expected layout

One directory per asana, named exactly as the asana id in `data/pose_rules/`:

```
data/datasets/yoga_poses/
├── tadasana/
│   ├── 001.jpg
│   └── clip_front.mp4
├── virabhadrasana_ii/
├── trikonasana/
├── vrikshasana/
├── utkatasana/
├── bhujangasana/
├── adho_mukha_svanasana/
├── balasana/
├── setu_bandhasana/
└── paschimottanasana/
```

Directory names that do not match a known asana are reported and skipped
rather than silently mislabelled.

Supported files: `.jpg .jpeg .png .bmp .webp` and `.mp4 .avi .mov .mkv .webm`.

## Building a feature file

```bash
python scripts/train_classifier.py extract \
    --data data/datasets/yoga_poses \
    --out  data/datasets/landmarks.csv
```

This runs MediaPipe over every image and samples every 10th video frame (a
held pose produces near-identical consecutive frames, so sampling avoids
inflating the dataset without adding information). Output is one CSV row per
detected frame: label, source file, frame index, then the 49 features from
`ai/pose_recognition/features.py`.

## Training

```bash
python scripts/train_classifier.py train --features data/datasets/landmarks.csv
```

Reports held-out accuracy, per-class F1 and a confusion matrix before saving.
Aim for **50+ samples per asana** across varied people, angles, distances and
lighting. Fewer than 20 and the script warns you: a model trained on a thin
class looks accurate overall while being useless for exactly the pose it was
meant to help with.

## Suitable public datasets

Several openly licensed yoga pose datasets exist, typically organised as
labelled image folders — the layout above matches how most of them ship. The
project was designed against a corpus of roughly 11,000 images and 80 videos
covering 10 asanas from multiple viewing angles.

Whatever you use, check two things:

- **The licence permits your use.** Many are research-only.
- **Class names map to `data/pose_rules/` ids.** Rename directories rather
  than editing the rule files, so the rules stay the single source of truth.

## Adding an asana

You do not need a dataset to add a pose. Drop a new JSON file in
`data/pose_rules/` and both the recogniser and the assessment engine pick it
up on the next restart — no code change, no retraining. See the main README
for the rule format.

## Privacy

Nothing in this directory is committed (`.gitignore` excludes it). If you
record your own footage, get explicit consent from anyone appearing in it,
and keep in mind that the running application never stores video: it stores
derived posture metrics only.
