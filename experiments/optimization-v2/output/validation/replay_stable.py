"""Replay every stable-profile seed in isolated processes, without overwriting evidence."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent))
from run import worker


def replay(row):
    with tempfile.TemporaryDirectory(prefix='mapgen-stable-replay-') as temp:
        folder = Path(temp) / 'case'
        got = worker(row['seed'], 'stable', folder, row['cohort'])
        matched = all(got[k] == row[k] for k in ('status', 'structural_sha256', 'state_sha256'))
        if not matched:
            shutil.copytree(folder, OUT / 'validation/replay-mismatches' / row['cohort'] / str(row['seed']))
        return dict(cohort=row['cohort'], seed=row['seed'], matched=matched,
                    expected_status=row['status'], actual_status=got['status'],
                    expected_structure=row['structural_sha256'], actual_structure=got['structural_sha256'],
                    expected_state=row['state_sha256'], actual_state=got['state_sha256'])


if __name__ == '__main__':
    data = json.loads((OUT / 'results.json').read_text())
    rows = [r for r in data['results'] if r['variant'] == 'stable']
    assert len(rows) == 40
    with ProcessPoolExecutor(max_workers=4) as pool:
        cases = list(pool.map(replay, rows))
    receipt = dict(status='PASS' if all(c['matched'] for c in cases) else 'FAIL',
                   replayed=len(cases), cases=cases)
    (OUT / 'validation/stable-replays.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'], 'all', receipt['replayed'], 'stable-profile states/signatures')
    assert receipt['status'] == 'PASS'
