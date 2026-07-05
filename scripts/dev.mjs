// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 로컬 개발 동시 기동 — 백엔드(FastAPI :8003) + 프론트엔드(Vite :5173)를 한 번에 띄운다.
 * 로컬 우선 데스크톱 도구라 docker 대신 단일 스크립트로 간다(OSS-3 결정).
 *
 * 사용: node scripts/dev.mjs
 * 사전: backend 의존성 설치(pip install -r backend/requirements.txt, venv 권장) + frontend `npm ci`.
 * Ctrl+C 로 둘 다 종료.
 */
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'

/** backend/.venv 가 있으면 그 파이썬을, 없으면 시스템 파이썬을 쓴다. */
function pythonCmd() {
  const venv = isWin
    ? join(root, 'backend', '.venv', 'Scripts', 'python.exe')
    : join(root, 'backend', '.venv', 'bin', 'python')
  if (existsSync(venv)) return venv
  return isWin ? 'python' : 'python3'
}

const procs = []
function run(name, cmd, args, cwd) {
  const p = spawn(cmd, args, { cwd, shell: isWin, env: process.env })
  const tag = `[${name}] `
  // 각 줄 앞에 이름 태그를 붙인다(마지막 빈 조각은 그대로 두어 이중 개행 방지).
  const pipe = (stream, out) =>
    stream.on('data', (b) => {
      const lines = b.toString().split('\n')
      out.write(lines.map((l, i) => (i === lines.length - 1 && l === '' ? l : tag + l)).join('\n'))
    })
  pipe(p.stdout, process.stdout)
  pipe(p.stderr, process.stderr)
  p.on('exit', (code) => {
    console.log(`${tag}종료 (code ${code}) — 나머지도 정리합니다`)
    shutdown()
  })
  procs.push(p)
  return p
}

let shuttingDown = false
function shutdown() {
  if (shuttingDown) return
  shuttingDown = true
  for (const p of procs) {
    try {
      p.kill()
    } catch {
      /* 이미 종료 */
    }
  }
  process.exit(0)
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)

console.log('KeyLens 개발 서버 기동 — 백엔드 :8003 · 프론트 :5173 (Ctrl+C 로 종료)')
run(
  'backend',
  pythonCmd(),
  ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8003'],
  join(root, 'backend'),
)
run('frontend', isWin ? 'npm.cmd' : 'npm', ['run', 'dev'], join(root, 'frontend'))
