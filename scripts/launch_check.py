"""Secret-free launch configuration report. Never deploys or mutates hosted data."""
import argparse
import json
from pathlib import Path

from dotenv import dotenv_values
from deploy_cloud_run import build_environment, invalid_configuration_keys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT/'backend/.env.production')
    args = parser.parse_args()
    values = {k: v for k, v in dotenv_values(args.env_file).items() if v}
    invalid = invalid_configuration_keys(values)
    report = {
        'deployment_ready': not invalid,
        'required_configuration': invalid,
        'target': 'Vercel frontend / Cloud Run backend / Supabase PostgreSQL and private Storage / TLS Redis',
        'model': build_environment(values)['LLM_MODEL'],
        'reranking': build_environment(values)['ENABLE_RERANKING'],
        'requires_approval': ['cloud project and budget', 'production migration', 'public deployment'],
    }
    output = ROOT / 'docs/verification/launch-check.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
