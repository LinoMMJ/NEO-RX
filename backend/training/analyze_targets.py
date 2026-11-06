"""Reproducible metadata audit; select targets on TRAIN, never test performance."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from diagnostico.priority_policy import SPECIFIC_CANDIDATES


def analyze(manifest_text, splits):
    rows = list(csv.DictReader(io.StringIO(manifest_text)))
    required = {'Image Index', 'Finding Labels', 'Patient ID'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Missing NIH metadata columns')
    image_names = [row['Image Index'] for row in rows]
    if len(image_names) != len(set(image_names)):
        raise ValueError('Duplicated Image Index; deduplicate before selecting targets')
    assignment = {}
    for part in ('train', 'val', 'test'):
        for name in splits[part]:
            if isinstance(name, int):
                name = image_names[name]
            if name in assignment:
                raise ValueError('An image occurs in multiple partitions')
            assignment[name] = part
    if set(assignment) != set(image_names):
        raise ValueError('Splits must cover exactly the manifest')
    counts = {part: Counter() for part in ('train', 'val', 'test', 'all')}
    patients, label_patients, hashes = defaultdict(set), defaultdict(set), defaultdict(set)
    contradictions = 0
    for row in rows:
        labels = set(filter(None, (value.strip() for value in row['Finding Labels'].split('|'))))
        part = assignment[row['Image Index']]
        patients[row['Patient ID']].add(part)
        if row.get('sha256'):
            hashes[row['sha256']].add(part)
        contradictions += bool('No Finding' in labels and len(labels) > 1)
        for label in labels:
            counts[part][label] += 1
            counts['all'][label] += 1
            label_patients[label].add(row['Patient ID'])
    overlaps = sum(len(parts) > 1 for parts in patients.values())
    duplicate_cross_split = sum(len(parts) > 1 for parts in hashes.values())
    if overlaps or duplicate_cross_split or contradictions:
        raise ValueError(f'Unsafe metadata: patient overlaps={overlaps}, duplicate hashes across splits={duplicate_cross_split}, conflicting No Finding rows={contradictions}')
    ranked = sorted(counts['all'], key=lambda label: (-counts['train'][label], label))
    selected = [label for label in ranked if label in SPECIFIC_CANDIDATES and counts['train'][label] > 0][:2]
    if not selected:
        raise ValueError('No specific pulmonary targets available in TRAIN')
    return {
        'source_sha256': hashlib.sha256(manifest_text.encode()).hexdigest(),
        'images': len(rows), 'patients': len(patients), 'selection_partition': 'train',
        'selected_targets': selected, 'patient_overlap': overlaps,
        'cross_split_duplicate_hashes': duplicate_cross_split,
        'ranking': [{'label': label, 'specific_candidate': label in SPECIFIC_CANDIDATES,
                     'positive_patients': len(label_patients[label]),
                     **{part: counts[part][label] for part in counts}} for label in ranked],
        'limitations': [
            'Frequency is not precision. These are image labels, not confirmed diagnoses.',
            'Infiltration and Consolidation are broad patterns retained for category training, not selected as specific disease targets.',
            'Only metadata audited locally; raw Kaggle pixels must be revalidated before training.',
            'Use all negative and co-labelled training images; do not keep only positives.',
            'Thresholds on validation; independent patient-level test required before clinical claims.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        manifests = [name for name in archive.namelist() if name.endswith('/clean_manifest.csv')]
        if len(manifests) != 1:
            raise ValueError('Expected exactly one clean manifest')
        manifest = manifests[0]
        text = archive.read(manifest).decode('utf-8-sig')
        splits = json.loads(archive.read(manifest.rsplit('/', 1)[0] + '/splits.json'))
    report = analyze(text, splits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
