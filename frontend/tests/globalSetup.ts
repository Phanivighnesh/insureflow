// Boots the REAL FastAPI backend (fresh SQLite DB) once for all frontend integration tests.
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

export const PORT = 8791
export const STAFF_CODE = 'fe-test-code'
let proc: ChildProcess | null = null
let dir = ''

export async function setup() {
  dir = mkdtempSync(join(tmpdir(), 'insureflow-fe-'))
  const candidatePythons = [
    resolve(__dirname, '../../.insureflow/Scripts/python.exe'),
    resolve(__dirname, '../../backend/.venv/Scripts/python.exe'),
    resolve(__dirname, '../../backend/.venv/bin/python'),
    resolve(__dirname, '../../.venv/bin/python'),
    process.env.PYTHON,
    process.platform === 'win32' ? 'python' : 'python3'
  ].filter(Boolean) as string[]
  const pyCmd = candidatePythons.find(p => p.includes('/') || p.includes('\\') ? existsSync(p) : true) || 'python'
  proc = spawn(pyCmd, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: resolve(__dirname, '../../backend'),
    env: { ...process.env, GROQ_API_KEY: '', DATABASE_URL: `sqlite:///${join(dir, 'fe.db')}`, SESSION_SECRET: 'fe-test-secret', STAFF_ACCESS_CODE: STAFF_CODE, DATA_DIR: join(dir, 'data') },
    stdio: 'pipe',
  })
  let log = ''
  proc.stderr?.on('data', (d) => (log += d)); proc.stdout?.on('data', (d) => (log += d))
  const deadline = Date.now() + 40000
  while (Date.now() < deadline) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/api/health`); if (r.ok) return } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 300))
  }
  throw new Error('Backend did not start:\n' + log)
}
export async function teardown() { proc?.kill('SIGTERM'); await new Promise((r) => setTimeout(r, 300)); if (dir) rmSync(dir, { recursive: true, force: true }) }
