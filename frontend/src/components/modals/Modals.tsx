// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { CONSOLE_URL, resolveIssueUrl, TYPE_MAP } from '@/data/services'
import { envText, fmtDate } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'

/** 삭제 확인 다이얼로그. */
export function DeleteModal() {
  const target = useKeylens((s) => s.deleteTarget)
  const cancel = useKeylens((s) => s.cancelDelete)
  const confirm = useKeylens((s) => s.confirmDelete)

  return (
    <Modal open={!!target} onClose={cancel} title="항목 삭제" className="w-[360px]">
      <div className="text-[15px] font-bold">항목 삭제</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        <span className="font-mono text-fg-soft">{target?.varName}</span> 을(를) 삭제할까요?
        <br />
        원본 스크린샷·메모도 함께 삭제되며, 되돌릴 수 없습니다.
      </p>
      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={cancel}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={confirm}
          className="cursor-pointer rounded-lg border-none bg-danger px-[14px] py-2 text-[12.5px] font-bold text-[#2A0B08] hover:brightness-[1.08]"
        >
          삭제
        </button>
      </div>
    </Modal>
  )
}

/** 값 교체(회전) 다이얼로그 — 새로 발급받은 값으로 교체(재암호화). */
export function RotateModal() {
  const target = useKeylens((s) => s.rotateTarget)
  const cancel = useKeylens((s) => s.cancelRotate)
  const confirm = useKeylens((s) => s.confirmRotate)
  const [value, setValue] = useState('')

  useEffect(() => {
    if (target) setValue('') // 열릴 때마다 입력 초기화
  }, [target])

  // 발급 콘솔 바로가기(GUIDE-2) — 회전 전에 새 키를 발급받도록.
  const issueUrl = target
    ? resolveIssueUrl(
        TYPE_MAP[target.service]?.find((t) => t.var === target.varName)?.issueUrl ||
          CONSOLE_URL[target.service],
        target.project,
      )
    : null

  return (
    <Modal open={!!target} onClose={cancel} title="값 교체" className="w-[420px]">
      <div className="text-[15px] font-bold">값 교체 (회전)</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        <span className="font-mono text-fg-soft">{target?.varName}</span> 의 값을 새로 발급받은 값으로 교체합니다.
        <br />
        옛 값은 즉시 폐기되어 복구할 수 없고, 교체는 이력에 기록됩니다.
      </p>
      {issueUrl && (
        <a
          href={issueUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-[10px] inline-flex items-center rounded-[7px] border border-border bg-chip px-[11px] py-[6px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          먼저 새 키 발급 →
        </a>
      )}
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && value.trim()) confirm(value)
        }}
        placeholder="새 값 붙여넣기"
        autoFocus
        className="mt-3 w-full rounded-lg border border-border bg-surface px-3 py-[10px] font-mono text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
      />
      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={cancel}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={() => confirm(value)}
          disabled={!value.trim()}
          className="rounded-lg border-none px-[14px] py-2 text-[12.5px] font-bold hover:brightness-[1.07]"
          style={{
            background: value.trim() ? '#3ECF8E' : '#1B2128',
            color: value.trim() ? '#05231A' : '#525B67',
            cursor: value.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          교체
        </button>
      </div>
    </Modal>
  )
}

/** 중복 감지 다이얼로그. */
export function DupModal() {
  const target = useKeylens((s) => s.dupTarget)
  const cancel = useKeylens((s) => s.cancelDup)
  const confirm = useKeylens((s) => s.confirmDup)

  return (
    <Modal
      open={!!target}
      onClose={cancel}
      title="이미 보관 중인 키"
      className="w-[400px] border-[rgba(227,179,65,.35)]"
    >
      <div className="flex items-center gap-2 text-[15px] font-bold">
        <span className="inline-block size-2 flex-none rotate-45 bg-amber" />
        이미 보관 중인 키
      </div>
      <p className="mt-[10px] text-[12.5px] leading-[1.65] text-muted">
        <span className="font-mono text-fg-soft">{target?.varName}</span> 이(가) 프로젝트{' '}
        <span className="font-semibold text-blue-tag">
          "{target ? target.existing.project || '미분류' : ''}"
        </span>
        에 {target ? fmtDate(target.existing.addedAt) : ''} 등록되어 있어요.
        <br />
        같은 키를 또 추가할까요?
      </p>
      <div className="mt-3 border-t border-line pt-[10px] text-[11.5px] leading-[1.55] text-dim">
        다른 프로젝트에서 쓰는 키라면, 카드의 <strong className="text-muted-2">프로젝트</strong>를 바꿔
        저장하면 나란히 구분돼요.
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={cancel}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={confirm}
          className="cursor-pointer rounded-lg border-none bg-mint px-[14px] py-2 text-[12.5px] font-bold text-on-mint hover:brightness-[1.08]"
        >
          그래도 추가
        </button>
      </div>
    </Modal>
  )
}

/** 암호화 금고 가져오기 다이얼로그(SYNC-0) — 파일 선택 + 마스터 비밀번호 + 방식. */
export function SyncModal() {
  const open = useKeylens((s) => s.syncOpen)
  const close = useKeylens((s) => s.closeSync)
  const importVault = useKeylens((s) => s.importVault)
  const [file, setFile] = useState<File | null>(null)
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'merge' | 'replace'>('merge')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) {
      setFile(null)
      setPassword('')
      setMode('merge')
      setBusy(false)
    }
  }, [open])

  const canRun = !!file && !!password && !busy
  const run = async () => {
    if (!file || !password) return
    setBusy(true)
    const ok = await importVault(file, password, mode)
    setBusy(false)
    if (!ok) setPassword('') // 실패 시 비밀번호만 비우고 모달 유지(재시도)
  }

  return (
    <Modal open={open} onClose={close} title="금고 가져오기" className="w-[460px] max-w-[92vw]">
      <div className="text-[15px] font-bold">금고 가져오기</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        다른 기기에서 내보낸 <span className="font-mono text-fg-soft">.klvault.json</span> 파일을
        마스터 비밀번호로 엽니다. 파일은 전부 암호문이라, 비밀번호가 없으면 아무도 열 수 없어요.
      </p>

      <label className="mt-[14px] block cursor-pointer rounded-lg border border-dashed border-border bg-inset px-[14px] py-3 text-[12px] text-muted hover:border-border-strong">
        <input
          type="file"
          accept=".json,application/json"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="hidden"
        />
        {file ? (
          <span className="font-mono text-fg-soft">{file.name}</span>
        ) : (
          '금고 파일 선택 (.klvault.json)'
        )}
      </label>

      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && canRun) void run()
        }}
        placeholder="이 금고의 마스터 비밀번호"
        className="mt-[10px] w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
      />

      <div className="mt-3 flex flex-col gap-[6px] text-[12px] text-muted">
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="radio"
            name="kl-sync-mode"
            checked={mode === 'merge'}
            onChange={() => setMode('merge')}
            className="mt-[3px]"
          />
          <span>
            <span className="font-semibold text-fg-soft">병합</span> — 현재 금고에 새 항목만
            추가(같은 변수명은 건너뜀). <span className="text-dim">현재 금고를 잠금 해제한 상태여야 해요.</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="radio"
            name="kl-sync-mode"
            checked={mode === 'replace'}
            onChange={() => setMode('replace')}
            className="mt-[3px]"
          />
          <span>
            <span className="font-semibold text-[#E3B341]">교체</span> — 현재 금고를 이 파일로
            완전히 대체(기존 항목 삭제). 빈 기기에 복원할 때 사용.
          </span>
        </label>
      </div>

      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={() => void run()}
          disabled={!canRun}
          className="rounded-lg border-none px-[14px] py-2 text-[12.5px] font-bold hover:brightness-[1.07]"
          style={{
            background: canRun ? '#3ECF8E' : '#1B2128',
            color: canRun ? '#05231A' : '#525B67',
            cursor: canRun ? 'pointer' : 'not-allowed',
          }}
        >
          {busy ? '가져오는 중…' : '가져오기'}
        </button>
      </div>
    </Modal>
  )
}

/** .env 내보내기 다이얼로그. */
export function EnvModal() {
  const envOpen = useKeylens((s) => s.envOpen)
  const vault = useKeylens((s) => s.vault)
  const projFilter = useKeylens((s) => s.projFilter)
  const close = useKeylens((s) => s.closeEnv)
  const copyAll = useKeylens((s) => s.envCopyAll)
  const download = useKeylens((s) => s.envDownload)

  const items = vault.filter((v) => !projFilter || (v.project || '') === projFilter)
  const text = envText(items)

  return (
    <Modal open={envOpen} onClose={close} title=".env 내보내기" className="w-[540px] max-w-[90vw]">
      <div className="flex items-baseline gap-[10px]">
        <div className="text-[15px] font-bold">.env 내보내기</div>
        <div className="text-[12px] text-faint-2">
          {projFilter || '전체 프로젝트'} · {items.length}개 항목
        </div>
      </div>
      <pre className="mt-[14px] max-h-[260px] overflow-y-auto whitespace-pre-wrap break-all rounded-lg border border-line bg-inset px-[14px] py-3 font-mono text-[11px] leading-[1.7] text-[#A8B0BC]">
        {text}
      </pre>
      <div className="mt-[10px] flex items-baseline gap-[7px] text-[11.5px] text-[#B08D45]">
        <span className="inline-block size-[6px] flex-none rotate-45 bg-amber" />
        값이 평문으로 포함됩니다 — 저장한 파일은 반드시 .gitignore에 추가하세요.
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          닫기
        </button>
        <button
          type="button"
          onClick={copyAll}
          className="cursor-pointer rounded-lg border border-border bg-chip px-[14px] py-2 text-[12.5px] font-semibold text-fg-soft hover:border-border-strong"
        >
          클립보드 복사
        </button>
        <button
          type="button"
          onClick={download}
          className="cursor-pointer rounded-lg border-none bg-mint px-[14px] py-2 text-[12.5px] font-bold text-on-mint hover:brightness-[1.08]"
        >
          파일 다운로드
        </button>
      </div>
    </Modal>
  )
}
