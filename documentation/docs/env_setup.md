
## 1. Env Set Up

### 🧰 1.1 Prerequisites

Make sure you have the following installed:

- Python 3.12+
- Git
- (Recommended) Make
- (Recommended) uv

---

#### Option A — ⚡ Recommended Setup Using Make (Fully Automated)

`make install` will:

- create virtual environment
- install dependencies
- install dev dependencies
- install pre-commit hooks

##### 📦 Install Make

**macOS**
```bash
brew install make
```

##### ⚡ Install uv:
```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```
check installation
```bash
$ uv --version
uv 0.6.12 (e4e03833f 2025-04-02)
```
##### One-step setup
```git
git clone <repo>
cd dwa-dv-generator
make install
```
##### ⚙️ Available Make Commands
make install     # create venv + install deps
make lint        # run ruff + sqlfluff
make format      # format python + sql
make test        # run tests
make clean       # remove venv and caches


#### Option B — Manual Setup Using uv
##### 🐍 Create virtual environment
From the project root:
```bash
uv venv
```
Activate it:
-   (macOS / Linux)
```bash
source .venv/bin/activate
```

#####  Install project dependencies
Install dependencies from pyproject.toml:
```bash
uv pip install -e .
```
Install development dependencies:
```bash
uv pip install -e ".[dev]"
```
##### 🔧 Install pre-commit hooks
This ensures formatting and linting before every commit.
```bash
pre-commit install
```
You can run manually:
```bash
pre-commit run --all-files
```
If a new dipendecy is added to the toml file you can run:
```bash
uv sync
```

#### Option C — Classic pip (fallback)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

### VS Code Recommended Extensions
- dbt Power User
- SQLFluff
- YAML
- Ruff
- Python
- Pylance

### UPDATES

🔄 Update dependencies
To update lock resolution:
```bash
uv pip compile pyproject.toml
```
Then reinstall:
```bash
uv pip install -e .
``
🧼 Clean environment
Remove virtual environment:
```bash
rm -rf .venv
```
Create again:
```bash
uv venv
```
If a new dipendecy is added to the toml file you can run:
```bash
uv sync
```
