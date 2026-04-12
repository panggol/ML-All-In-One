# Constitution Compliance Check — Data Management Module

**Spec**: `specs/data_management/spec.md`  
**Checked Against**: `CONSTITUTION.md` (Version 1.0.0)  
**Check Date**: 2026-04-11  
**Status**: ✅ Pass (with 2 clarifications required)

---

## Compliance Summary

| Principle | Status | Notes |
|-----------|--------|-------|
| I. 规划先行，接口第一 | ✅ Compliant | API contracts defined in spec; UI layout documented |
| II. Library-First | ✅ Compliant | Data management is a standalone module; frontend is React component |
| III. 接口标准化 | ⚠️ Partial | Python API not explicitly defined; CLI interface not specified |
| IV. 测试不可绕过 | ✅ Compliant | FR-027 mandates unit tests; SC-009/010 require ≥80% coverage and contract tests |
| V. 集成测试重点区域 | ✅ Compliant | Module integration with `/data/*` APIs noted in Assumptions |
| VI. 可观测性 | ✅ Compliant | FR-025 mandates structured JSON logs with required fields |
| VII. 版本管理 | ✅ Compliant | Assumes semantic versioning; no breaking changes in v1 scope |
| VIII. 简洁优先 (YAGNI) | ✅ Compliant | Only CSV supported in v1; versioning, mobile, multi-format out of scope |
| 大数据处理约束 | ✅ Compliant | FR-026 mandates pandas chunksize or Dask for >50GB files |
| 技术栈约束 | ✅ Compliant | React+TS frontend, FastAPI backend, pytest testing |
| 部署约束 | ✅ Compliant | Docker/K8s mentioned; config via env vars assumed |

---

## Detailed Compliance Analysis

### ✅ Principle I — 规划先行，接口第一

**Constitution Requirement**: Complex features must have design documents (SPEC.md) before code. Interface contracts (API/CLI) must be defined first.

**Compliance**:
- This spec (`spec.md`) follows the spec-template format and defines API contracts before implementation details.
- All 6 API endpoints (`/data/list`, `/data/upload`, `/data/{id}`, `/data/{id}/preview`, `/data/{id}/stats`, `/data/{id}/export`) are fully defined with HTTP methods, request/response schemas, and TypeScript interfaces.
- UI layout is documented via ASCII wireframe.

**Verdict**: ✅ Fully Compliant

---

### ✅ Principle II — Library-First

**Constitution Requirement**: Each functional module must be an independent Python package under `src/mlkit/`.

**Compliance**:
- Data Management is a frontend React module in this project context. It does not introduce a Python library.
- The module communicates via the `/data/*` API contracts, which are independent of the frontend implementation.
- No "utility-only" packages introduced.

**Verdict**: ✅ Compliant (frontend module is orthogonal to library-first principle)

---

### ⚠️ Principle III — 接口标准化

**Constitution Requirement**: All core features must expose both Python API and CLI interface. CLI follows `stdin/args → stdout` protocol; errors → `stderr`. API supports JSON output.

**Compliance**:
- **Python API**: The backend `/data/*` FastAPI endpoints provide a Python-callable interface via HTTP. However, a Python package-level API (e.g., `from mlkit.data import upload_dataset`) is not explicitly defined in this spec.
- **CLI Interface**: No CLI interface is specified for data management operations.

**Gap**: No explicit Python package API or CLI for data management operations.

**Recommendation**: Define:
1. Python API: `mlkit.data.upload(path)`, `mlkit.data.list()`, `mlkit.data.preview(id, n=10)`, `mlkit.data.stats(id)`, `mlkit.data.delete(id)`, `mlkit.data.export(id, path)`.
2. CLI: `mlkit data upload <path>`, `mlkit data list`, `mlkit data preview <id>`, `mlkit data stats <id>`, `mlkit data delete <id>`, `mlkit data export <id> <path>`.

**Verdict**: ⚠️ Partial — [NEEDS CLARIFICATION: Is Python/CLI interface required for this module, or is HTTP API sufficient?]

---

### ✅ Principle IV — 测试不可绕过

**Constitution Requirement**: New code must have unit tests (pytest). Integration tests for cross-module interactions. Contract tests for API endpoints and CLI output formats.

**Compliance**:
- **FR-027**: "All new code MUST include unit tests (pytest)." — explicitly mandated.
- **SC-009**: "Unit test coverage for data management module is ≥ 80%." — measurable coverage target.
- **SC-010**: "All API contract tests pass." — contract testing required.
- Integration with backend `/data/*` APIs is acknowledged in Assumptions.

**Verdict**: ✅ Fully Compliant

---

### ✅ Principle V — 集成测试重点区域

**Constitution Requirement**: Key integration test areas: new module contracts, module↔DB↔MLKit communication, shared schema changes.

**Compliance**:
- Backend API integration is listed as a dependency assumption.
- Schema for `DataFile`, `PreviewResult`, `ColumnStats` is defined, enabling contract testing.

**Verdict**: ✅ Compliant

---

### ✅ Principle VI — 可观测性

**Constitution Requirement**: All API routes must emit structured JSON logs (JSON format). Logs must include: request ID, user ID, operation type, duration, status code.

**Compliance**:
- **FR-025**: "All API calls MUST emit structured JSON logs containing: request ID, user ID, operation type, duration, status code."
- Fully aligned with Constitution observability requirements.

**Verdict**: ✅ Fully Compliant

---

### ✅ Principle VII — 版本管理

**Constitution Requirement**: Semantic versioning (`MAJOR.MINOR.BUILD`). Breaking changes must upgrade MAJOR version and update CHANGELOG.

**Compliance**:
- This spec describes v1 functionality with no breaking changes.
- Assumes semantic versioning is followed at the project level.

**Verdict**: ✅ Compliant

---

### ✅ Principle VIII — 简洁优先 (YAGNI)

**Constitution Requirement**: Start simple. No over-engineering. Every change must have clear value. Reject "might be useful someday" code.

**Compliance**:
- Only CSV format supported in v1 (no Excel, Parquet, JSON, Avro).
- No data versioning in v1.
- No per-user dataset isolation in v1.
- No mobile support in v1.
- Clear scope boundaries defined in Assumptions.

**Verdict**: ✅ Fully Compliant

---

### ✅ 大数据处理约束

**Constitution Requirement**: 50GB+ CSV files must use pandas `chunksize` or Dask for chunked reading. Non-streaming models must support sampling or Dask-ML.

**Compliance**:
- **FR-026**: "CSV files larger than 50GB MUST be processed using pandas `chunksize` or Dask to avoid memory exhaustion."
- Assumptions note: "Statistical computation is performed on full data — sampling strategy for very large datasets is [NEEDS CLARIFICATION]."

**Verdict**: ✅ Compliant (with open question on stats computation strategy for very large datasets)

---

## Confirmed Compliant Items

| ID | Requirement | Constitution Principle |
|----|-------------|----------------------|
| FR-025 | Structured JSON logging (request ID, user ID, operation, duration, status code) | VI. 可观测性 |
| FR-026 | pandas chunksize or Dask for >50GB CSV files | 大数据处理约束 |
| FR-027 | Unit tests (pytest) for all new code | IV. 测试不可绕过 |
| FR-028 | API contracts documented and versioned | I. 规划先行 |
| SC-009 | ≥ 80% unit test coverage | IV. 测试不可绕过 |
| SC-010 | API contract tests pass | IV. 测试不可绕过 |
| ASCII layout documented | UI wireframe defined | I. 规划先行 |
| TypeScript interfaces defined | Typed API contracts | I. 规划先行 |

---

## [NEEDS CLARIFICATION] Items

| # | Item | Question |
|---|------|----------|
| 1 | **Python/CLI API** | Does this module require a Python package-level API (`mlkit.data.*`) and CLI interface (`mlkit data ...`) per Constitution Principle III, or is the HTTP API sufficient? |
| 2 | **Stats computation for large datasets** | "Statistical computation is performed on full data." — What is the strategy when a dataset has millions of rows? Is sampling acceptable? What sample size? |
| 3 | **Large column datasets** | "CSV with 500+ columns — preview and stats should remain performant." — Is there a specific column rendering limit or lazy-loading strategy? |
| 4 | **Duplicate filename handling** | "System should either rename automatically or prompt the user." — Which behavior is preferred? |

---

## Recommendations

1. **Add Python/CLI API to spec** — Extend the API Contracts section with Python package function signatures and CLI command specifications aligned with Constitution Principle III.
2. **Clarify stats sampling strategy** — Add a note or separate story about large-dataset statistical computation (sampling threshold, method, and cached stats).
3. **Add contract tests to QA plan** — Ensure `harness/qa/` includes tests for all 6 API endpoints returning the documented schemas.
4. **Add observability logging to backend** — Ensure `/data/*` endpoints implement structured JSON logging per FR-025 before QA.

---

*Checked by: requirements-agent subagent | 2026-04-11*
