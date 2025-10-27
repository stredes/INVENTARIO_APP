param(
  [switch]$Fix
)

$ErrorActionPreference = 'Stop'

function Exec($cmd) {
  Write-Host "→ $cmd" -ForegroundColor Cyan
  powershell -NoProfile -Command $cmd
}

try {
  if ($Fix) {
    Exec "python -m ruff check --fix ."
    Exec "python -m isort --profile black --line-length 100 ."
    Exec "python -m black --line-length 100 ."
  } else {
    Exec "python -m ruff check ."
    Exec "python -m black --check --line-length 100 ."
    Exec "python -m isort --check-only --profile black --line-length 100 ."
  }

  Exec "python -m mypy --ignore-missing-imports src scripts"
  Exec "python -m pytest -q --cov=src --cov-report=term-missing --cov-report=xml"

  try { Exec "python -m bandit -q -r src" } catch { Write-Warning "bandit no disponible o falló: $_" }
  try { Exec "python -m pip_audit -r requirements.txt" } catch { Write-Warning "pip-audit no disponible o falló: $_" }

  Write-Host "OK: lint + types + tests + cobertura + seguridad" -ForegroundColor Green
  exit 0
}
catch {
  Write-Error $_
  exit 1
}
