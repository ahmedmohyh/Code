import json
import csv
import yaml
from pathlib import Path
import numpy as np

root = Path('results/biraffe2')
config_root = Path('config/biraffe2')
irshad_root = Path('results/irshad')
irshad_config_root = Path('config/irshad')

METRICS = ['accuracy', 'f1_macro', 'precision_low', 'recall_low', 'precision_high', 'recall_high', 'auc']


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_config_path(sub, name):
    if sub == 'normal':
        candidates = [config_root / 'normal_configs' / f'{name}.yaml']
    elif sub == 'gridsearch':
        candidates = [config_root / 'grid_search' / f'{name}.yaml']
    else:  # extreme_percentile
        candidates = [
            config_root / 'extreme_percentile_configs' / f'{name}.yaml',
            config_root / 'real_level_configs' / f'{name}.yaml',
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_best_model(metrics_data, metric='auc'):
    """Find best model by a subject-level metric (default AUC)."""
    models = metrics_data.get('models', {})
    best = None
    for model_name, model_data in models.items():
        if not isinstance(model_data, dict):
            continue
        sub = model_data.get('subject_aggregate', {})
        value = sub.get(metric)
        if value is None or np.isnan(value):
            continue
        if best is None or value > best[metric]:
            best = {
                'model': model_name,
                'auc': sub.get('auc'),
                'metrics': {m: sub.get(m, np.nan) for m in METRICS},
                'n': sub.get('n_subjects_used'),
            }
    return best


def get_irshad_config_path(name):
    candidates = [
        irshad_config_root / f'{name}.yaml',
        irshad_config_root / 'grid_search' / f'{name}.yaml',
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def describe_pipeline(cfg):
    """Extract pipeline description from config."""
    ds = cfg.get('dataset', {})
    modalities = ds.get('modalities', [])
    treat_levels = ds.get('treat_levels_as_subjects', False)

    lbl = cfg.get('label', {})
    method = lbl.get('method', '')
    margin = lbl.get('margin', 0.0)
    percentile_low = lbl.get('percentile_low')
    percentile_high = lbl.get('percentile_high')

    prep = cfg.get('preprocessing', {})
    cleaning_pkg = prep.get('cleaning_package', '')
    outlier = prep.get('outlier_strategy', '')
    zscore = prep.get('z_standardise', False)
    baseline = prep.get('baseline_correction', 'none')
    baseline_from_proc = prep.get('baseline_from_procedure', False)
    baseline_length = prep.get('baseline_length_s', '')
    per_subject_norm = prep.get('per_subject_normalize', False)

    seg = cfg.get('segmentation', {})
    window = seg.get('window_length_s', '')
    step = seg.get('step_s', '')

    feats = cfg.get('features', {})
    feature_pkg = feats.get('package', '')

    models = cfg.get('models', {})
    classical = models.get('classical', [])
    deep = models.get('deep', [])
    all_models = classical + deep

    games_zip = ds.get('games_zip_path') or ds.get('games_path')
    real_level_times = games_zip is not None

    # Build a compact human-readable label description
    if method == 'extreme_percentile':
        low_pct = int(round(percentile_low * 100)) if percentile_low is not None else ''
        high_pct = int(round((1 - percentile_high) * 100)) if percentile_high is not None else ''
        label_desc = f"extreme percentile bottom {low_pct}% / top {high_pct}%"
    elif method == 'median_split':
        label_desc = f"median split (margin={margin})"
    elif method == 'filename':
        label_desc = "binary labels from filename (flow / no_flow)"
    else:
        label_desc = method

    # Build a compact pipeline description
    parts = []
    parts.append(f"Data: {', '.join(modalities)}")
    if treat_levels:
        parts.append("levels as pseudo-subjects")
    if real_level_times:
        parts.append("real-level timestamps")
    parts.append(f"labels={label_desc}")
    parts.append(f"cleaning={cleaning_pkg}")
    parts.append(f"features={feature_pkg}")
    parts.append(f"outliers={outlier}")
    parts.append(f"z-std={zscore}")
    if per_subject_norm:
        parts.append("per-subject normalization")
    if baseline != 'none':
        parts.append(f"baseline={baseline} ({baseline_length}s from procedure={baseline_from_proc})")
    parts.append(f"window={window}s/step={step}s")
    parts.append(f"models={', '.join(all_models) if all_models else '—'}")
    parts.append("validation=LOSO")

    return {
        'dataset': ds.get('name', ''),
        'modalities': ', '.join(modalities),
        'treat_levels_as_subjects': treat_levels,
        'label_method': method,
        'margin': margin,
        'percentile_low': percentile_low,
        'percentile_high': percentile_high,
        'outlier_strategy': outlier,
        'z_standardise': zscore,
        'baseline_correction': baseline,
        'baseline_from_procedure': baseline_from_proc,
        'baseline_length_s': baseline_length,
        'per_subject_normalize': per_subject_norm,
        'window_length_s': window,
        'step_s': step,
        'models': ', '.join(all_models) if all_models else '—',
        'real_level_times': real_level_times,
        'cleaning_package': cleaning_pkg,
        'feature_package': feature_pkg,
        'label_description': label_desc,
        'pipeline_description': ' | '.join(parts),
    }


def fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    if isinstance(v, float):
        return f'{v:.3f}'
    return str(v)


# Collect data
normal_rows = []
grid_rows = []
extreme_rows = []
all_high_accuracy = []
all_high_auc = []

# Normal setups
for d in sorted((root / 'normal').iterdir()):
    if not d.is_dir():
        continue
    name = d.name
    metrics_file = d / 'metrics.json'
    if not metrics_file.exists():
        continue
    metrics = load_json(metrics_file)
    best = find_best_model(metrics)
    if best is None:
        continue
    cfg_path = get_config_path('normal', name)
    cfg = load_yaml(cfg_path) if cfg_path else {}
    pipe = describe_pipeline(cfg)
    row = {
        'experiment': name,
        'model': best['model'],
        **{m: best['metrics'][m] for m in METRICS},
        'n': best['n'],
        'pipeline': pipe,
    }
    normal_rows.append(row)
    if best['metrics']['accuracy'] > 0.68:
        all_high_accuracy.append({
            'category': 'normal',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })
    if best['auc'] > 0.68:
        all_high_auc.append({
            'category': 'normal',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })

# Grid search setups
grid_search_root = root / 'gridsearch' / 'grid_search'
for d in sorted(grid_search_root.iterdir()):
    if not d.is_dir():
        continue
    name = d.name
    metrics_file = d / 'metrics.json'
    if not metrics_file.exists():
        continue
    metrics = load_json(metrics_file)
    best = find_best_model(metrics)
    if best is None:
        continue
    cfg_path = get_config_path('gridsearch', name)
    cfg = load_yaml(cfg_path) if cfg_path else {}
    pipe = describe_pipeline(cfg)
    row = {
        'experiment': name,
        'model': best['model'],
        **{m: best['metrics'][m] for m in METRICS},
        'n': best['n'],
        'pipeline': pipe,
    }
    grid_rows.append(row)
    if best['metrics']['accuracy'] > 0.68:
        all_high_accuracy.append({
            'category': 'grid search',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })
    if best['auc'] > 0.68:
        all_high_auc.append({
            'category': 'grid search',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })

# Extreme percentile setups
for d in sorted((root / 'extreme_percentile').iterdir()):
    if not d.is_dir():
        continue
    name = d.name
    metrics_file = d / 'metrics.json'
    if not metrics_file.exists():
        continue
    metrics = load_json(metrics_file)
    best = find_best_model(metrics)
    if best is None:
        continue
    cfg_path = get_config_path('extreme_percentile', name)
    cfg = load_yaml(cfg_path) if cfg_path else {}
    pipe = describe_pipeline(cfg)
    variant = 'real level times' if '_real_level_times_' in name else 'equal split'
    row = {
        'experiment': name,
        'variant': variant,
        'model': best['model'],
        **{m: best['metrics'][m] for m in METRICS},
        'n': best['n'],
        'pipeline': pipe,
    }
    extreme_rows.append(row)
    if best['metrics']['accuracy'] > 0.68:
        all_high_accuracy.append({
            'category': f'extreme percentile ({variant})',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })
    if best['auc'] > 0.68:
        all_high_auc.append({
            'category': f'extreme percentile ({variant})',
            'experiment': name,
            'model': best['model'],
            'accuracy': best['metrics']['accuracy'],
            'auc': best['auc'],
            'pipeline': pipe,
            'n': best['n'],
        })

# Irshad/PhySF setups
irshad_rows = []

# Current metrics.json results (outlier_strategy: none)
for d in sorted(irshad_root.iterdir()):
    if not d.is_dir() or d.name == 'grid_search':
        continue
    name = d.name
    metrics_file = d / 'metrics.json'
    if not metrics_file.exists():
        continue
    metrics = load_json(metrics_file)
    best = find_best_model(metrics)
    if best is None:
        continue
    cfg_path = get_irshad_config_path(name)
    cfg = load_yaml(cfg_path) if cfg_path else {}
    pipe = describe_pipeline(cfg)
    row = {
        'experiment': name,
        'variant': 'no outlier removal',
        'model': best['model'],
        **{m: best['metrics'][m] for m in METRICS},
        'n': best['n'],
        'pipeline': pipe,
    }
    irshad_rows.append(row)

# Grid-search result
grid_metrics_file = irshad_root / 'grid_search' / 'setup_08_irshad_physf_grid_search' / 'metrics.json'
if grid_metrics_file.exists():
    metrics = load_json(grid_metrics_file)
    best = find_best_model(metrics)
    if best is not None:
        cfg_path = get_irshad_config_path('setup_08_irshad_physf_grid_search')
        cfg = load_yaml(cfg_path) if cfg_path else {}
        pipe = describe_pipeline(cfg)
        irshad_rows.append({
            'experiment': 'setup_08_irshad_physf_grid_search',
            'variant': 'grid search (no outlier removal)',
            'model': best['model'],
            **{m: best['metrics'][m] for m in METRICS},
            'n': best['n'],
            'pipeline': pipe,
        })

# Historical CSV results (outlier_strategy: train_only)
irshad_csv_path = irshad_root / 'ablation_comparison.csv'
if irshad_csv_path.exists():
    with open(irshad_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # train_only results
            auc = row.get('auc')
            acc = row.get('accuracy')
            n = row.get('n')
            if auc and float(auc) >= 0.68:
                exp = row['experiment']
                cfg_path = get_irshad_config_path(exp)
                cfg = load_yaml(cfg_path) if cfg_path else {}
                pipe = describe_pipeline(cfg)
                # Override outlier strategy to reflect the train_only variant
                pipe = dict(pipe)
                pipe['outlier_strategy'] = 'train_only'
                pipe['pipeline_description'] = pipe['pipeline_description'].replace('outliers=none', 'outliers=train_only')
                irshad_rows.append({
                    'experiment': exp,
                    'variant': 'IQR outlier removal (train_only)',
                    'model': row['model'],
                    'accuracy': float(acc) if acc else np.nan,
                    'f1_macro': float(row['f1_macro']) if row.get('f1_macro') else np.nan,
                    'precision_low': np.nan,
                    'recall_low': np.nan,
                    'precision_high': np.nan,
                    'recall_high': np.nan,
                    'auc': float(auc),
                    'n': int(n) if n else np.nan,
                    'pipeline': pipe,
                })

for row in irshad_rows:
    if row['accuracy'] > 0.68:
        all_high_accuracy.append({
            'category': f"Irshad/PhySF ({row['variant']})",
            'experiment': row['experiment'],
            'model': row['model'],
            'accuracy': row['accuracy'],
            'auc': row['auc'],
            'pipeline': row['pipeline'],
            'n': row['n'],
        })
    if row['auc'] > 0.68:
        all_high_auc.append({
            'category': f"Irshad/PhySF ({row['variant']})",
            'experiment': row['experiment'],
            'model': row['model'],
            'accuracy': row['accuracy'],
            'auc': row['auc'],
            'pipeline': row['pipeline'],
            'n': row['n'],
        })

# Build overview table mapping experiments to their variants
overview = {}
for r in normal_rows:
    overview.setdefault(r['experiment'], {})['normal'] = r
for r in grid_rows:
    base = r['experiment'].replace('_grid_search', '')
    overview.setdefault(base, {})['grid'] = r
for r in extreme_rows:
    base = r['experiment'].replace('_extreme_percentile', '').replace('_real_level_times_extreme_percentile', '')
    key = 'extreme_equal' if r['variant'] == 'equal split' else 'extreme_real'
    overview.setdefault(base, {})[key] = r


# Write ablation_comparison.md
lines = []
lines.append('# Biraffe2 Ablation Comparison')
lines.append('')
lines.append('Results are organized into three sub-folders:')
lines.append('- `normal/` — standard median-split labels')
lines.append('- `gridsearch/` — hyperparameter-tuned classical classifiers')
lines.append('- `extreme_percentile/` — bottom 20 % / top 20 % labels (equal split and real level timestamp variants)')
lines.append('')
lines.append('All metrics below are **subject-level aggregates** from LOSO cross-validation.')
lines.append('')

# Overview table
lines.append('## Best model overview per experiment')
lines.append('')
header = '| Experiment | Normal Model | Normal Acc | Normal F1 | Normal AUC | Normal n | Grid-Search Model | Grid-Search AUC | Grid-Search n | Extreme-Percentile Model | Extreme-Percentile AUC | Extreme-Percentile n |'
sep = '|---|---|---|---|---|---|---|---|---|---|---|---|'
lines.append(header)
lines.append(sep)
for exp in sorted(overview.keys()):
    d = overview[exp]
    norm = d.get('normal')
    grid = d.get('grid')
    ext = d.get('extreme_equal') or d.get('extreme_real')

    def cell(row, key):
        if row is None:
            return '—'
        if key == 'model':
            return row['model']
        if key == 'n':
            return fmt(row.get('n'))
        return fmt(row.get(key, np.nan))

    lines.append(
        f'| {exp} | {cell(norm, "model")} | {cell(norm, "accuracy")} | {cell(norm, "f1_macro")} | '
        f'{cell(norm, "auc")} | {cell(norm, "n")} | {cell(grid, "model")} | {cell(grid, "auc")} | '
        f'{cell(grid, "n")} | {cell(ext, "model")} | {cell(ext, "auc")} | {cell(ext, "n")} |'
    )
lines.append('')

# Detailed normal table
lines.append('## Normal setups — full subject-level metrics')
lines.append('')
header = '| Experiment | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |'
sep = '|---|---|---|---|---|---|---|---|---|---|'
lines.append(header)
lines.append(sep)
for r in sorted(normal_rows, key=lambda x: x['experiment']):
    lines.append(
        f'| {r["experiment"]} | {r["model"]} | {fmt(r["accuracy"])} | {fmt(r["f1_macro"])} | '
        f'{fmt(r["auc"])} | {fmt(r["precision_low"])} | {fmt(r["recall_low"])} | '
        f'{fmt(r["precision_high"])} | {fmt(r["recall_high"])} | {fmt(r["n"])} |'
    )
lines.append('')

# Detailed grid search table
lines.append('## Grid-search setups — full subject-level metrics')
lines.append('')
header = '| Experiment | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |'
sep = '|---|---|---|---|---|---|---|---|---|---|'
lines.append(header)
lines.append(sep)
for r in sorted(grid_rows, key=lambda x: x['experiment']):
    lines.append(
        f'| {r["experiment"]} | {r["model"]} | {fmt(r["accuracy"])} | {fmt(r["f1_macro"])} | '
        f'{fmt(r["auc"])} | {fmt(r["precision_low"])} | {fmt(r["recall_low"])} | '
        f'{fmt(r["precision_high"])} | {fmt(r["recall_high"])} | {fmt(r["n"])} |'
    )
lines.append('')

# Detailed extreme percentile table
lines.append('## Extreme-percentile setups — full subject-level metrics')
lines.append('')
header = '| Experiment | Variant | Best Model | Accuracy | F1 | AUC | Precision Low | Recall Low | Precision High | Recall High | n |'
sep = '|---|---|---|---|---|---|---|---|---|---|---|'
lines.append(header)
lines.append(sep)
for r in sorted(extreme_rows, key=lambda x: x['experiment']):
    lines.append(
        f'| {r["experiment"]} | {r["variant"]} | {r["model"]} | {fmt(r["accuracy"])} | {fmt(r["f1_macro"])} | '
        f'{fmt(r["auc"])} | {fmt(r["precision_low"])} | {fmt(r["recall_low"])} | '
        f'{fmt(r["precision_high"])} | {fmt(r["recall_high"])} | {fmt(r["n"])} |'
    )
lines.append('')

# Supervisor summary embedded in the table
lines.append('## Supervisor summary: setups with subject-level accuracy > 0.68 or AUC > 0.68')
lines.append('')
if not all_high_accuracy and not all_high_auc:
    lines.append('No setup reached a subject-level accuracy or AUC above 0.68.')
else:
    if all_high_accuracy:
        lines.append('### Accuracy > 0.68')
        lines.append('')
        for item in sorted(all_high_accuracy, key=lambda x: x['accuracy'], reverse=True):
            p = item['pipeline']
            lines.append(
                f'#### {item["experiment"]} ({item["category"]} — {item["model"]}, '
                f'accuracy={fmt(item["accuracy"])}, AUC={fmt(item["auc"])}, n={fmt(item["n"])})'
            )
            lines.append('')
            lines.append(f'- **Data / modalities:** {p["modalities"]}')
            lines.append(f'- **Levels as pseudo-subjects:** {p["treat_levels_as_subjects"]}')
            lines.append(f'- **Classifier:** {item["model"]}')
            lines.append(f'- **Outlier strategy:** {p["outlier_strategy"]}')
            lines.append(f'- **Z-standardisation:** {p["z_standardise"]}')
            lines.append(f'- **Baseline correction:** {p["baseline_correction"]} (from procedure: {p["baseline_from_procedure"]})')
            lines.append(f'- **Window / step:** {p["window_length_s"]}s / {p["step_s"]}s')
            lines.append(f'- **Label method:** {p["label_method"]} (margin={p["margin"]})')
            lines.append(f'- **Real level timestamps:** {p["real_level_times"]}')
            lines.append(f'- **Models tested in config:** {p["models"]}')
            lines.append('')
    if all_high_auc:
        lines.append('### AUC > 0.68')
        lines.append('')
        for item in sorted(all_high_auc, key=lambda x: x['auc'], reverse=True):
            p = item['pipeline']
            lines.append(
                f'#### {item["experiment"]} ({item["category"]} — {item["model"]}, '
                f'accuracy={fmt(item["accuracy"])}, AUC={fmt(item["auc"])}, n={fmt(item["n"])})'
            )
            lines.append('')
            lines.append(f'- **Data / modalities:** {p["modalities"]}')
            lines.append(f'- **Levels as pseudo-subjects:** {p["treat_levels_as_subjects"]}')
            lines.append(f'- **Classifier:** {item["model"]}')
            lines.append(f'- **Outlier strategy:** {p["outlier_strategy"]}')
            lines.append(f'- **Z-standardisation:** {p["z_standardise"]}')
            lines.append(f'- **Baseline correction:** {p["baseline_correction"]} (from procedure: {p["baseline_from_procedure"]})')
            lines.append(f'- **Window / step:** {p["window_length_s"]}s / {p["step_s"]}s')
            lines.append(f'- **Label method:** {p["label_method"]} (margin={p["margin"]})')
            lines.append(f'- **Real level timestamps:** {p["real_level_times"]}')
            lines.append(f'- **Models tested in config:** {p["models"]}')
            lines.append('')

# Write MD
md_path = root / 'ablation_comparison.md'
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'wrote {md_path}')

# Write CSV with all details
csv_rows = []
for r in normal_rows:
    csv_rows.append({
        'category': 'normal',
        'experiment': r['experiment'],
        'model': r['model'],
        **{m: r[m] for m in METRICS},
        'n': r['n'],
        'modalities': r['pipeline']['modalities'],
        'outlier_strategy': r['pipeline']['outlier_strategy'],
        'z_standardise': r['pipeline']['z_standardise'],
        'baseline_correction': r['pipeline']['baseline_correction'],
        'window_step_s': f'{r["pipeline"]["window_length_s"]}/{r["pipeline"]["step_s"]}',
        'label_method': r['pipeline']['label_method'],
        'margin': r['pipeline']['margin'],
    })
for r in grid_rows:
    csv_rows.append({
        'category': 'grid_search',
        'experiment': r['experiment'],
        'model': r['model'],
        **{m: r[m] for m in METRICS},
        'n': r['n'],
        'modalities': r['pipeline']['modalities'],
        'outlier_strategy': r['pipeline']['outlier_strategy'],
        'z_standardise': r['pipeline']['z_standardise'],
        'baseline_correction': r['pipeline']['baseline_correction'],
        'window_step_s': f'{r["pipeline"]["window_length_s"]}/{r["pipeline"]["step_s"]}',
        'label_method': r['pipeline']['label_method'],
        'margin': r['pipeline']['margin'],
    })
for r in extreme_rows:
    csv_rows.append({
        'category': f'extreme_percentile_{r["variant"].replace(" ", "_")}',
        'experiment': r['experiment'],
        'model': r['model'],
        **{m: r[m] for m in METRICS},
        'n': r['n'],
        'modalities': r['pipeline']['modalities'],
        'outlier_strategy': r['pipeline']['outlier_strategy'],
        'z_standardise': r['pipeline']['z_standardise'],
        'baseline_correction': r['pipeline']['baseline_correction'],
        'window_step_s': f'{r["pipeline"]["window_length_s"]}/{r["pipeline"]["step_s"]}',
        'label_method': r['pipeline']['label_method'],
        'margin': r['pipeline']['margin'],
    })

if csv_rows:
    keys = list(csv_rows[0].keys())
    with open(root / 'ablation_comparison.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(csv_rows)
    print(f'wrote {root / "ablation_comparison.csv"}')

def _supervisor_category(p):
    """Translate internal category names into plain-language descriptions."""
    method = p['label_method']
    if method == 'extreme_percentile':
        low = int(round(p['percentile_low'] * 100)) if p['percentile_low'] is not None else ''
        high = int(round((1 - p['percentile_high']) * 100)) if p['percentile_high'] is not None else ''
        label_text = f"Labels: lowest {low}% vs. highest {high}% of summed FSS-GEQ flow scores (bottom/top)"
    elif method == 'median_split':
        label_text = f"Labels: above/below median of summed FSS-GEQ flow scores (margin={p['margin']})"
    elif method == 'filename':
        label_text = "Labels: binary flow / no-flow classes derived from the recording filename"
    else:
        label_text = f"Labels: {method}"

    if p.get('dataset') == 'Irshad_PhySF':
        label_text += "; windows are 60-second segments of the recording"
    elif p['real_level_times']:
        label_text += "; windows aligned to actual game-level timestamps from game logs"
    else:
        label_text += "; windows evenly distributed across the recorded signal"
    return label_text


def _supervisor_setup_description(item, p):
    """Build a plain-language description of what this setup actually does."""
    desc_parts = []
    if 'baseline_correction' in item['experiment'] and p['baseline_correction'] != 'none':
        desc_parts.append(
            f"Baseline-corrected ECG: windows compared against a {p['baseline_length_s']}s pre-task baseline "
            f"using '{p['baseline_correction']}' correction."
        )
    if 'full_multimodal' in item['experiment']:
        desc_parts.append("Multimodal input: ECG, EDA, and facial/video features combined.")
    if 'without_time_distortion' in item['experiment']:
        desc_parts.append("Uses the original, unmodified FSS-GEQ flow scores without any time/level distortion.")
    if 'raw_geq' in item['experiment']:
        desc_parts.append("Uses raw per-item FSS-GEQ scores instead of a summed subscale.")
    if 'heartpy' in item['experiment']:
        desc_parts.append("HeartPy package used for ECG cleaning and feature extraction.")
    if 'per_subject_normalization' in item['experiment'] or p['per_subject_normalize']:
        desc_parts.append("Features normalized per subject before classification.")
    if 'drop_unreliable_60s_features' in item['experiment']:
        desc_parts.append("Unreliable 60-second HRV features removed from the feature set.")
    if 'shorter_step' in item['experiment']:
        desc_parts.append("Smaller step size between consecutive windows (more overlapping windows).")
    if '5min_window' in item['experiment']:
        desc_parts.append("Longer 5-minute analysis windows instead of the default 60-second windows.")
    if 'levels_as_subjects' in item['experiment']:
        desc_parts.append("Each game level treated as an independent pseudo-subject.")
    if 'no_zscore' in item['experiment']:
        desc_parts.append("No z-standardisation applied to features.")
    if 'no_outlier' in item['experiment']:
        desc_parts.append("No outlier removal applied.")
    if 'label_margin' in item['experiment']:
        desc_parts.append(f"Ambiguous middle flow scores excluded from training (margin={p['margin']}).")
    if '_classical' in item['experiment']:
        desc_parts.append("Classical machine-learning classifiers tested (no deep learning).")
    if '_grid_search' in item['experiment']:
        desc_parts.append("Hyperparameter grid search performed for the listed classical classifier.")
    if 'irshad' in item['experiment']:
        if 'setup_08b' in item['experiment'] or 'ecg_only' in item['experiment']:
            desc_parts.append("Irshad/PhySF dataset: ECG-only classification of flow vs. no-flow.")
        elif 'setup_08a' in item['experiment'] or 'ecg_eda' in item['experiment']:
            desc_parts.append("Irshad/PhySF dataset: ECG + EDA classification of flow vs. no-flow.")
        elif 'setup_08' in item['experiment']:
            desc_parts.append("Irshad/PhySF dataset: ECG + EDA + EEG classification of flow vs. no-flow.")
        if 'grid_search' in item['experiment']:
            desc_parts.append("Hyperparameter grid search for classical classifiers.")

    if not desc_parts:
        desc_parts.append("Standard configuration with the listed modalities and preprocessing.")
    return ' '.join(desc_parts)


def _write_supervisor_table(sup_lines, items, title, sort_key):
    sup_lines.append(f'## {title}')
    sup_lines.append('')
    if not items:
        sup_lines.append(f'No setup reached a subject-level {title.lower()} above 0.68.')
        return
    header = (
        '| Description | How Labels Were Created | Accuracy | AUC | n | Best Classifier | '
        'Modalities | Preprocessing & Library | Normalization | Full Pipeline |'
    )
    sep = '|---|---|---|---|---|---|---|---|---|---|'
    sup_lines.append(header)
    sup_lines.append(sep)
    for item in sorted(items, key=lambda x: x[sort_key], reverse=True):
        p = item['pipeline']
        category = _supervisor_category(p)
        description = _supervisor_setup_description(item, p)
        preprocessing = (
            f"{p['cleaning_package']} cleaning; {p['feature_package']} feature extraction; "
            f"outliers={p['outlier_strategy']}; baseline={p['baseline_correction']}"
        )
        normalization = f"z-standardisation={p['z_standardise']}"
        if p['per_subject_normalize']:
            normalization += " + per-subject normalization"
        if p['dataset'] == 'Irshad_PhySF':
            subject_text = f"{item['n']} real subjects, 128 Hz. "
        elif p['treat_levels_as_subjects']:
            subject_text = "Levels treated as pseudo-subjects. "
        else:
            subject_text = ""
        window_timing = category.split(';')[1].strip() + '. ' if ';' in category else ''
        baseline_text = (
            f"Baseline correction: {p['baseline_correction']} "
            f"({p['baseline_length_s']}s from procedure={p['baseline_from_procedure']}). "
            if p['baseline_correction'] != 'none' else
            "No baseline correction. "
        )
        full_pipeline = (
            f"Data: {p['modalities']}. {subject_text}"
            f"{window_timing}"
            f"Features extracted with {p['feature_package']} after {p['cleaning_package']} cleaning. "
            f"Outlier handling: {p['outlier_strategy']}. "
            f"Normalization: {normalization}. "
            f"{baseline_text}"
            f"Segmentation: {p['window_length_s']}s windows, {p['step_s']}s step. "
            f"Models evaluated: {p['models']}. Validation: leave-one-subject-out (LOSO)."
        )
        sup_lines.append(
            f"| {description} | {category.split(';')[0].strip()} | {fmt(item['accuracy'])} | "
            f"{fmt(item['auc'])} | {fmt(item['n'])} | {item['model']} | "
            f"{p['modalities']} | {preprocessing} | {normalization} | {full_pipeline} |"
        )
    sup_lines.append('')


# Write supervisor summary as separate file
sup_lines = []
sup_lines.append('# BIRAFFE2 and Irshad/PhySF Setups with Subject-Level Accuracy or AUC > 0.68')
sup_lines.append('')
sup_lines.append(
    'This document lists every BIRAFFE2 and Irshad/PhySF setup whose best model achieved a subject-level accuracy or AUC above 0.68 in LOSO cross-validation.'
)
sup_lines.append('')
_write_supervisor_table(sup_lines, all_high_auc, 'Setups with AUC ≥ 0.68', 'auc')
_write_supervisor_table(sup_lines, all_high_accuracy, 'Setups with Accuracy ≥ 0.68', 'accuracy')

sup_path = root / 'supervisor_accuracy_or_auc_over_068.md'
with open(sup_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(sup_lines))
print(f'wrote {sup_path}')

print(f'\nHigh-accuracy setups found: {len(all_high_accuracy)}')
for h in sorted(all_high_accuracy, key=lambda x: x['accuracy'], reverse=True):
    print(f'  {h["accuracy"]:.3f}  {h["experiment"]:60s} {h["category"]:25s} {h["model"]}')
print(f'\nHigh-AUC setups found: {len(all_high_auc)}')
for h in sorted(all_high_auc, key=lambda x: x['auc'], reverse=True):
    print(f'  {h["auc"]:.3f}  {h["experiment"]:60s} {h["category"]:25s} {h["model"]}')
