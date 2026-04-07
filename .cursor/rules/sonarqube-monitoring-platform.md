# SonarQube Monitor — Cursor 규칙 (요약)

## Persona

- **AI / 개발자** — 이 파일은 **짧은 진입점**만 담는다. 상세는 `docs/` 를 읽는다.

## 필수 참조

- **개요·스택·디렉터리**: [docs/00_overview/architecture-summary.md](../../docs/00_overview/architecture-summary.md)
- **기능·엣지**: [docs/02_analysis/functional-spec.md](../../docs/02_analysis/functional-spec.md)
- **API 목록**: [docs/02_analysis/api-requirements.md](../../docs/02_analysis/api-requirements.md)

## Why

Cursor Rules는 **전문 복붙을 피하고** 저장소 단일 문서(`docs/`)로 링크해 **중복·불일치**를 줄인다.

## 규칙

- 민감값(토큰)은 규칙·문서에 **실제 값 금지**.
- 모듈 추출·라벨 규칙 변경 시 `config/` + `docs/03_design/` 동기화 검토.
