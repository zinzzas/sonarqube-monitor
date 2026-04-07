# DB Schema

## Persona

- **Architect / DBA 습관 있는 개발자**

## Status

**이 애플리케이션은 애플리케이션 DB를 사용하지 않는다.**

## Why

- 집계는 **Sonar API + 인메모리 캐시**로 충분하다.
- 프로젝트·용어·팀 규칙은 **`config/*.json`** 이 스키마 역할을 한다.

## Configuration as data

| 파일 | 역할 |
|------|------|
| `component_projects.json` | 프로젝트 id, Sonar componentKey |
| `module_grouping.json` | 경로 추출 프로필 |
| `module_segment_labels.json` | 한글 라벨 트리, exclude, teamMapping |
| `dashboard.json` | 카피·메타 |

## See also

- [system-architecture.md](./system-architecture.md)
