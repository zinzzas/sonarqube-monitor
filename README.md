# SonarQube Monitor

SonarQube 이슈를 대시보드(프로젝트·모듈·Severity)와 상세 목록으로 보는 도구입니다. **FastAPI** + **Vue 3 / Vite**입니다.

---

## Windows 로컬 실행 가이드 (Hatch)

이 문서는 **Windows 10/11**, **PowerShell**을 기준으로 합니다. macOS·Linux는 명령만 해당 셸에 맞게 바꾸면 됩니다.

### 1. 사전 이해: Python·pip·Hatch

| 도구 | 역할 |
|------|------|
| **Python 3.11+** | 백엔드(FastAPI) 실행에 필요합니다. |
| **Hatch** | 프로젝트 전용 가상환경을 만들고, 그 안에서 `python`·의존성을 고정해 실행합니다. (`pyproject.toml` 기준) |
| **pip** | Python에 **기본 포함**됩니다. 별도 “pip 설치” 단계는 보통 필요 없습니다. Hatch는 `pip install hatch` 등으로 설치합니다. |

**Hatch는 Python 패키지**이므로, 어떤 방식이든 **한 번은 Python 실행 환경**이 있어야 합니다. “PC에 Python이 전혀 없다”면 아래 **방법 A** 또는 **방법 B** 중 하나로만 준비하면 됩니다.

---

### 2. 방법 A — Python을 먼저 설치한 뒤 Hatch (일반적)

1. **Python 3.11 이상** 설치  
   - [python.org](https://www.python.org/downloads/windows/) 에서 Windows installer  
   - 또는 PowerShell(관리자):

     ```powershell
     winget install Python.Python.3.12
     ```

   - 설치 시 **“Add python.exe to PATH”** 를 켜는 것을 권장합니다.

2. **터미널을 다시 연 뒤** 버전 확인:

   ```powershell
   py --version
   ```

3. **Hatch 설치** (사용자 영역):

   ```powershell
   py -m pip install --user hatch
   ```

4. **PATH**에 사용자 Scripts 폴더가 없으면 Hatch를 찾지 못합니다. 예시 (Python 3.12):

   ```powershell
   $env:Path += ";$env:APPDATA\Python\Python312\Scripts"
   ```

   영구 반영: Windows 설정 → **환경 변수** → 사용자 `Path`에 위 `Scripts` 경로 추가.

5. 확인:

   ```powershell
   hatch --version
   ```

---

### 3. 방법 B — `uv`로 Hatch만 설치 (직접 `pip`를 치지 않을 때)

`pip` 명령을 쓰지 않고 도구만 설치하고 싶다면 **uv**를 쓸 수 있습니다.

1. **uv 설치** (공식 스크립트, PowerShell):

   ```powershell
   irm https://astral.sh/uv/install.ps1 | iex
   ```

2. **Hatch 설치** (uv가 관리하는 도구 영역):

   ```powershell
   uv tool install hatch
   ```

3. `hatch`가 PATH에 잡히는지 확인합니다. 안 되면 터미널 안내에 따라 `Path`를 추가합니다.

4. **백엔드용 Python**은 아래 `hatch env create` 시 Hatch가 프로젝트용으로 맞는 버전을 받아 씁니다(인터넷 필요).

---

### 4. 저장소 받기·Hatch 환경 만들기

```powershell
cd C:\path\to\your\repos
git clone <이-저장소-URL> sonarqube-monitor
cd sonarqube-monitor
```

가상환경 생성 및 의존성 설치(최초 1회 또는 `pyproject.toml` 변경 후):

```powershell
hatch env create
```

동작 확인:

```powershell
hatch run python -c "import fastapi; print('ok')"
```

---

### 5. 환경 변수 (`.env`)

프로젝트 **루트**에 `.env` 파일을 만들고 값을 넣습니다 (`main.py`와 같은 폴더).

```powershell
notepad .env
```

주요 항목:

| 변수 | 설명 |
|------|------|
| `SONAR_BASE_URL` | SonarQube 서버 베이스 URL (예: `https://sonarqube.example.com`) |
| `SONAR_TOKEN` | 분석/이슈 조회용 토큰 |
| `SONAR_SAMPLE_COMPONENT_KEYS` | (선택) UI에서 `componentKeys` 생략 시 기본 프로젝트 키 |
| `HTTP_LOG_LEVEL` | (선택) Sonar 업스트림 + 내부 `/api/*` 응답 로깅: `off` / `info` / `debug`. 기존 `SONAR_HTTP_LOG_LEVEL`과 동일 의미(호환). |

Sonar 호스트·토큰은 **코드에 넣지 말고 `.env`만** 수정합니다. 그 외 옵션(`SONAR_AUTH`, `SONAR_PROXY` 등)은 `.env` 안 주석을 참고합니다.

---

### 6. 백엔드 실행 (포트 `9999`)

프로젝트 루트에서:

```powershell
hatch run start
```

- `start`는 `python main.py`와 같으며, **코드·`.env` 변경 시 자동 재기동**(uvicorn `--reload`)입니다.
- 리로드 없이 고정 실행만 하려면:

  ```powershell
  hatch run serve
  ```

브라우저에서 API 확인: **http://127.0.0.1:9999/api/health**

---

### 7. 프론트엔드 (Node.js)

UI는 **Node.js**(LTS 권장)와 **npm**이 필요합니다. Windows에 없다면:

- [Node.js LTS](https://nodejs.org/) 설치, 또는

  ```powershell
  winget install OpenJS.NodeJS.LTS
  ```

#### 개발 모드 (Vite, 포트 `5173`)

`web/vite.config.js`에서 개발 서버는 **5173**이고, **`/api` 요청은 `http://127.0.0.1:9999`로 프록시**됩니다. **백엔드를 먼저** 띄운 뒤 프론트를 실행합니다.

```powershell
cd web
npm install
npm run dev
```

브라우저: **http://127.0.0.1:5173**

#### 한 포트만 쓰기 (백엔드가 정적 파일 서빙)

프로덕션과 비슷하게 **백엔드 한 개 포트**만 쓰려면 프론트를 빌드한 뒤 루트에서 백엔드를 띄웁니다.

```powershell
cd web
npm install
npm run build
cd ..
hatch run start
```

브라우저: **http://127.0.0.1:9999**

(`web/dist`가 있어야 `main.py`가 SPA를 루트에서 제공합니다.)

---

### 8. 자주 겪는 문제

| 증상 | 점검 |
|------|------|
| `hatch`를 찾을 수 없음 | Python Scripts 경로를 사용자 `Path`에 추가했는지, 터미널을 다시 열었는지 확인 |
| `All connection attempts failed` 등 Sonar 오류 | VPN·사내망, `SONAR_BASE_URL` 오타, 방화벽, `SONAR_SSL_VERIFY` (자체 서명 시 `false` 검토) |
| `9999` 포트 사용 중 | 다른 프로그램 종료 또는 `main.py` / `serve` 스크립트에서 포트 변경 |
| 프론트만 빈 화면 | `web`에서 `npm run build` 했는지, `web/dist` 존재 여부 |

---

## 설정 파일 (`config/`)

| 파일 | 용도 |
|------|------|
| `component_projects.json` | 프로젝트 목록·Sonar `componentKey` |
| `module_grouping.json` | 프로젝트별 모듈 경로 추출(Java·Vue 등) |
| `dashboard.json` | 대시보드 제목·설명 문구 |

---

## 주요 API

- `GET /api/health`
- `GET /api/metrics/dashboard` — 대시보드 집계
- `GET /api/issues/search` — Sonar 이슈 검색 프록시

---

## 요구 사항 요약

- **Python**: 3.11 이상 (Hatch가 프로젝트 환경에서 사용)
- **Hatch**: 위 가이드대로 설치
- **프론트 개발/빌드**: Node.js LTS + npm
