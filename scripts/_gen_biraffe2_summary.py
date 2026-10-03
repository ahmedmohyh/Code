import json
import csv
import yaml
from pathlib import Path
import numpy as np

root = Path('results/biraffe2')
config_root = Path('config/biraffe2')

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


def find_best_model(metrics_data):
    """Find best model by subject-level AUC."""
    models = metrics_data.get('models', {})
    best = None
    for model_name, model_data in models.items():
        if not isinstance(model_data, dict):
            continue
        sub = model_data.get('subject_aggregate', {})
        auc = sub.get('auc')
        if auc is None or np.isnan(auc):
            continue
        if best is None or auc > best['auc']:
            best = {
                'model': model_name,
                'auc': auc,
                'metrics': {m: sub.get(m, np.nan) for m in METRICS},
                'n': sub.get('n_subjects_used'),
            }
    return best


def describe_pipeline(cfg):
    """Extract pipeline description from config."""
    ds = cfg.get('dataset', {})
    modalities = ds.get('modalities', [])
    treat_levels = ds.get('treat_levels_as_subjects', False)

    lbl = cfg.get('label', {})
    method = lbl.get('method', '')
    margin = lbl.get('margin', 0.0)

    prep = cfg.get('preprocessing', {})
    outlier = prep.get('outlier_strategy', '')
    zscore = prep.get('z_standardise', False)
    baseline = prep.get('baseline_correction', 'none')
    baseline_from_proc = prep.get('baseline_from_procedure', False)

    seg = cfg.get('segmentation', {})
    window = seg.get('window_length_s', '')
    step = seg.get('step_s', '')

    models = cfg.get('models', {})
    classical = models.get('classical', [])
    deep = models.get('deep', [])
    all_models = classical + deep

    games_zip = ds.get('games_zip_path') or ds.get('games_path')
    real_level_times = games_zip is not None

    return {
        'modalities': ', '.join(modalities),
        'treat_levels_as_subjects': treat_levels,
        'label_method': method,
        'margin': margin,
        'outlier_strategy': outlier,
        'z_standardise': zscore,
        'baseline_correction': baseline,
        'baseline_from_procedure': baseline_from_proc,
        'window_length_s': window,
        'step_s': step,
        'models': ', '.join(all_models) if all_models else '—',
        'real_level_times': real_level_times,
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

def _write_supervisor_items(sup_lines, items, title, sort_key):
    sup_lines.append(f'## {title}')
    sup_lines.append('')
    if not items:
        sup_lines.append(f'No setup reached a subject-level {title.lower()} above 0.68.')
    else:
        for item in sorted(items, key=lambda x: x[sort_key], reverse=True):
            p = item['pipeline']
            sup_lines.append(f'### {item["experiment"]}')
            sup_lines.append('')
            sup_lines.append(f'- **Category:** {item["category"]}')
            sup_lines.append(f'- **Best classifier:** {item["model"]}')
            sup_lines.append(f'- **Subject-level accuracy:** {fmt(item["accuracy"])}')
            sup_lines.append(f'- **Subject-level AUC:** {fmt(item["auc"])}')
            sup_lines.append(f'- **Number of pseudo-subjects (n):** {fmt(item["n"])}')
            sup_lines.append(f'- **Data / modalities:** {p["modalities"]}')
            sup_lines.append(f'- **Levels treated as subjects:** {p["treat_levels_as_subjects"]}')
            sup_lines.append(f'- **Labeling:** {p["label_method"]} with margin={p["margin"]}')
            sup_lines.append(f'- **Outlier strategy:** {p["outlier_strategy"]}')
            sup_lines.append(f'- **Z-standardisation:** {p["z_standardise"]}')
            sup_lines.append(
                f'- **Baseline correction:** {p["baseline_correction"]} '
                f'(from procedure events: {p["baseline_from_procedure"]})'
            )
            sup_lines.append(f'- **Window length / step:** {p["window_length_s"]}s / {p["step_s"]}s')
            sup_lines.append(f'- **Real level timestamps (games_zip):** {p["real_level_times"]}')
            sup_lines.append(f'- **All models tested in config:** {p["models"]}')
            sup_lines.append('')


# Write supervisor summary as separate file
sup_lines = []
sup_lines.append('# Biraffe2 Setups with Subject-Level Accuracy or AUC > 0.68')
sup_lines.append('')
sup_lines.append(
    'This document lists every Biraffe2 setup whose best model achieved a subject-level accuracy or AUC above 0.68 in LOSO cross-validation.'
)
sup_lines.append('')
_write_supervisor_items(sup_lines, all_high_accuracy, 'Accuracy > 0.68', 'accuracy')
_write_supervisor_items(sup_lines, all_high_auc, 'AUC > 0.68', 'auc')

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
