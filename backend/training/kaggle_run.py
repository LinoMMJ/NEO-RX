"""One-session Kaggle entry point. No Django, database or clinical records."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

import yaml

from training.analyze_targets import analyze
from training.session import resume_signature


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def discover_data_root(input_root):
    matches = list(Path(input_root).rglob('Data_Entry_2017.csv'))
    if len(matches) != 1:
        raise ValueError(f'Found {len(matches)} NIH metadata files. Set DATA_ROOT explicitly to the folder containing all NIH images.')
    return matches[0].parent


def verify_bundle(bundle):
    manifest = json.loads((bundle / 'bundle_manifest.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['sha256'].items():
        path = (bundle / relative).resolve()
        if not path.is_relative_to(bundle.resolve()):
            raise ValueError('Invalid bundle path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Bundle checksum failed: {relative}')
    return manifest


def package_outputs(output):
    """Only this run's allowlisted directories; never input images or credentials."""
    target = output.parent / 'neorx_entrenamiento_resultados.zip'
    temporary = target.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file() and path.suffix != '.tmp':
                archive.write(path, f'{output.name}/{path.relative_to(output).as_posix()}')
    temporary.replace(target)
    print(f'DESCARGAR: {target}', flush=True)
    return target


def command(module, *arguments):
    subprocess.run([sys.executable, '-u', '-m', module, *map(str, arguments)], check=True)


def prepare_data(bundle, data_root, output, workers):
    folder = output / 'manifests'
    folder.mkdir(exist_ok=True)
    command('training.validate_dataset', '--input-root', data_root, '--csv', bundle / 'reference/metadata.csv',
            '--output-dir', folder, '--workers', workers)
    splits = json.loads((bundle / 'reference/splits.json').read_text(encoding='utf-8'))
    manifest = (folder / 'clean_manifest.csv').read_text(encoding='utf-8-sig')
    # Coverage changes, patient overlap and duplicate contents stop the run.
    audit = analyze(manifest, splits)
    write_json(folder / 'splits.json', splits)
    write_json(folder / 'priority_audit.json', audit)
    return folder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--input-root', type=Path, default=Path('/kaggle/input'))
    parser.add_argument('--output', type=Path, default=Path('/kaggle/working/neorx-run'))
    parser.add_argument('--previous-output', type=Path)
    parser.add_argument('--mode', choices=['train', 'evaluate'], default='train')
    parser.add_argument('--session-hours', type=float, default=8)
    parser.add_argument('--reserve-minutes', type=float, default=45)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if not 0 < args.reserve_minutes / 60 < args.session_hours or args.batch_size < 1 or args.workers < 0:
        raise ValueError('Invalid session budget, batch size or workers')
    started = time.monotonic()
    bundle, output = args.bundle.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output already contains a run. Use a fresh folder and PREVIOUS_OUTPUT to resume explicitly.')
    output.mkdir(parents=True, exist_ok=True)
    status = {'status': 'preparing', 'mode': args.mode, 'test_evaluated': False}
    try:
        build = verify_bundle(bundle)
        write_json(output / 'source_bundle.json', build)
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('Enable a GPU accelerator in Kaggle; this full training must not run on CPU.')
        write_json(output / 'environment.json', {
            'python': sys.version, 'torch': torch.__version__, 'cuda': torch.version.cuda,
            'gpu': torch.cuda.get_device_name(0), 'gpu_count': torch.cuda.device_count(),
            'note': 'Uses one GPU; a T4 x2 allocation does not automatically double speed.',
        })
        data_root = args.data_root.resolve() if args.data_root else discover_data_root(args.input_root)
        folder = prepare_data(bundle, data_root, output, max(1, args.workers))
        cfg = yaml.safe_load((bundle / 'training/config.priority2.v2.kaggle.yaml').read_text(encoding='utf-8'))
        cfg['data'].update(data_dir=str(data_root), manifest=str(folder / 'clean_manifest.csv'),
                           splits_json=str(folder / 'splits.json'))
        cfg['model'].update(checkpoint_dir=str(output / 'checkpoints'), cache_dir=str(bundle / 'weights'))
        cfg['train'].update(log_dir=str(output / 'runs'), batch_size=args.batch_size, num_workers=args.workers)
        runtime = output / 'config.runtime.yaml'
        runtime.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
        checkpoint_dir = output / 'checkpoints'
        previous = args.previous_output.resolve() if args.previous_output else None
        resume_args = []
        if previous:
            previous_build = json.loads((previous / 'source_bundle.json').read_text(encoding='utf-8'))
            if previous_build != build:
                raise ValueError('Code bundle changed. Resume with the exact bundle used for the previous run.')
            previous_cfg = yaml.safe_load((previous / 'config.runtime.yaml').read_text(encoding='utf-8'))
            # Use current paths for data identity comparison after Kaggle remounts inputs.
            previous_cfg['data'] = cfg['data']
            if resume_signature(previous_cfg) != resume_signature(cfg):
                raise ValueError('Training configuration changed; resume with the original batch size and settings.')
            if args.mode == 'train' and (previous / 'evaluation').exists():
                raise ValueError('TEST was already inspected. Do not resume model selection on this test set.')
            shutil.copytree(previous / 'checkpoints', checkpoint_dir)
            if (previous / 'runs').exists():
                shutil.copytree(previous / 'runs', output / 'runs')
            resume_args = ['--resume', checkpoint_dir / 'last.pt']
        if args.mode == 'evaluate':
            if not previous:
                raise ValueError('EVALUATE requires PREVIOUS_OUTPUT from the completed training run')
            state = json.loads((checkpoint_dir / 'session_status.json').read_text(encoding='utf-8'))
            if not state.get('training_finished'):
                raise ValueError('Finish training before inspecting TEST')
            previous_last = __import__('training.model', fromlist=['load_checkpoint']).load_checkpoint(checkpoint_dir / 'last.pt')
            if previous_last['training_state']['resume_signature'] != resume_signature(cfg):
                raise ValueError('Dataset changed since training; TEST evaluation blocked')
            command('training.evaluate', '--config', runtime, '--checkpoint',
                    checkpoint_dir / cfg['model']['checkpoint_name'], '--device', 'cuda',
                    '--output-dir', output / 'evaluation', '--plot')
            status = {'status': 'evaluated', 'test_evaluated': True,
                      'note': 'Internal NIH evaluation, not external clinical validation. Review routing_summary.json before deployment.'}
        else:
            remaining = args.session_hours * 3600 - args.reserve_minutes * 60 - (time.monotonic() - started)
            if remaining <= 60:
                status = {'status': 'preparation_only', 'test_evaluated': False,
                          'note': 'No training started: increase the session budget within your Kaggle allowance.'}
            else:
                command('training.train', '--config', runtime, '--device', 'cuda',
                        '--max-hours', remaining / 3600, *resume_args)
                status = json.loads((checkpoint_dir / 'session_status.json').read_text(encoding='utf-8'))
        print(json.dumps(status, indent=2, ensure_ascii=False), flush=True)
    except BaseException as exc:
        status = {'status': 'failed', 'error': str(exc), 'test_evaluated': False,
                  'note': 'Review logs. Use last.pt only if present; no successful training is claimed.'}
        raise
    finally:
        write_json(output / 'STATUS.json', status)
        package_outputs(output)


if __name__ == '__main__':
    main()
