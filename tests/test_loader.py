"""Test BIRAFFE2 loader and labeler without heavy ML dependencies."""
import sys
sys.path.insert(0, r"C:\Users\user\Downloads\Masterthesis\Code")

from flow_lol.utils.config import load_config
from flow_lol.data.loaders.biraffe2_loader import BIRAFFE2Loader
from flow_lol.data.labelers.flow_labeler import FlowLabeler

config = load_config(r"C:\Users\user\Downloads\Masterthesis\Code\config\setup_01_biraffe2_ecg_baseline.yaml")
loader = BIRAFFE2Loader(config.dataset)

subjects = loader.list_subjects()
print(f"Valid subjects: {len(subjects)}")

scores = [loader.load_subject(sid)["label"] for sid in subjects[:5]]
print(f"First 5 flow scores: {scores}")

labeler = FlowLabeler(config.label)
labels, mask = labeler.fit_transform(scores)
print(f"Labels: {labels.tolist()}")
print(f"Mask: {mask.tolist()}")
print(f"Median={labeler.median_:.3f}, IQR={labeler.iqr_:.3f}")

record = loader.load_subject(subjects[0])
print(f"Subject {record['subject_id']} signal shape: {record['signal'].shape}")
