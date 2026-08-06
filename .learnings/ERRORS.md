# Errors

Command failures and integration errors.

---

## [ERR-20260805-001] agent-browser proxy conflict

**Logged**: 2026-08-05T05:58:00Z
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
agent-browser fails with `ERR_NO_SUPPORTED_PROXIES` when system proxy (127.0.0.1:7897) is configured.

### Error
```
Navigation failed: net::ERR_NO_SUPPORTED_PROXIES
```

### Context
- macOS with HTTP/SOCKS proxy at 127.0.0.1:7897
- agent-browser picks up system proxy but Chromium engine doesn't support the proxy protocol

### Suggested Fix
Set `HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" NO_PROXY="*"` before agent-browser commands.

### Metadata
- Reproducible: yes

### Resolution
- **Resolved**: 2026-08-05T05:58:00Z
- **Notes**: Workaround is to unset proxy env vars for agent-browser calls.

---
