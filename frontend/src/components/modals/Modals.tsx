// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { CONSOLE_URL, resolveIssueUrl, TYPE_MAP } from '@/data/services'
import { envText, fmtDate } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'
import type { VaultItem } from '@/types'

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

/** 금고 완전 초기화 확인(VAULT-RESET) — 교육·공용 PC용. 비밀번호 재확인 필수. */
export function ResetVaultModal() {
  const open = useKeylens((s) => s.resetVaultOpen)
  const pw = useKeylens((s) => s.resetVaultPw)
  const err = useKeylens((s) => s.resetVaultErr)
  const resetting = useKeylens((s) => s.resettingVault)
  const setPw = useKeylens((s) => s.setResetVaultPw)
  const cancel = useKeylens((s) => s.closeResetVault)
  const confirm = useKeylens((s) => s.confirmResetVault)

  return (
    <Modal open={open} onClose={cancel} title="금고 완전 초기화" className="w-[380px]">
      <div className="text-[15px] font-bold">금고 완전 초기화</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        저장된 모든 자격증명·감사 이력·컬렉션 접근 승인 기록이 완전히 삭제됩니다.
        <br />
        <span className="font-semibold text-danger">되돌릴 수 없습니다.</span>
      </p>
      <div className="mt-[14px]">
        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && confirm()}
          placeholder="마스터 비밀번호"
          autoFocus
          className="w-full rounded-lg border bg-surface-3 px-[11px] py-[9px] text-[13px] text-fg outline-none"
          style={{ borderColor: err ? 'rgba(229,103,92,.55)' : '#232931' }}
        />
        {err && <div className="mt-[9px] text-[12px] text-danger">{err}</div>}
      </div>
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
          disabled={resetting}
          className="cursor-pointer rounded-lg border-none bg-danger px-[14px] py-2 text-[12.5px] font-bold text-[#2A0B08] hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {resetting ? '초기화 중…' : '완전 초기화'}
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
        <span className="font-mono text-fg-soft">{target?.varName}</span> 이(가) 컬렉션{' '}
        <span className="font-semibold text-blue-tag">
          "{target ? target.existing.project || '미분류' : ''}"
        </span>
        에 {target ? fmtDate(target.existing.addedAt) : ''} 등록되어 있어요.
        <br />
        같은 키를 또 추가할까요?
      </p>
      <div className="mt-3 border-t border-line pt-[10px] text-[11.5px] leading-[1.55] text-dim">
        다른 컬렉션에서 쓰는 키라면, 카드의 <strong className="text-muted-2">컬렉션</strong>을 바꿔
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
  const loadPreview = useKeylens((s) => s.loadEnvPreview)

  const items = vault.filter((v) => !projFilter || (v.project || '') === projFilter)

  // 미리보기는 store.vault 의 마스킹된 값이 아니라 실제 복호화된 값을 보여줘야 하므로,
  // 모달이 열릴 때마다 별도로 복호화해 로컬 상태에 담는다(클립보드 복사·다운로드와 동일한 값).
  const [previewItems, setPreviewItems] = useState<VaultItem[] | null>(null)
  useEffect(() => {
    if (!envOpen) {
      setPreviewItems(null)
      return
    }
    let cancelled = false
    loadPreview().then((resolved) => {
      if (!cancelled) setPreviewItems(resolved)
    })
    return () => {
      cancelled = true
    }
  }, [envOpen, projFilter, loadPreview])

  const text = previewItems ? envText(previewItems) : '복호화하는 중…'

  return (
    <Modal open={envOpen} onClose={close} title=".env 내보내기" className="w-[540px] max-w-[90vw]">
      <div className="flex items-baseline gap-[10px]">
        <div className="text-[15px] font-bold">.env 내보내기</div>
        <div className="text-[12px] text-faint-2">
          {projFilter || '전체 컬렉션'} · {items.length}개 항목
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

/** 이메일로 내보내기 다이얼로그(SYNC-2 재설계) — 목적지 이메일 입력 → 확인 메일 발송 요청. */
export function EmailSyncModal() {
  const open = useKeylens((s) => s.emailSyncOpen)
  const close = useKeylens((s) => s.closeEmailSync)
  const emailExport = useKeylens((s) => s.emailExport)
  const code = useKeylens((s) => s.emailSyncCode)
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) {
      setEmail('')
      setBusy(false)
    }
  }, [open])

  const canRun = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) && !busy
  const run = async () => {
    if (!canRun) return
    setBusy(true)
    await emailExport(email)
    setBusy(false)
  }

  return (
    <Modal open={open} onClose={close} title="이메일로 내보내기" className="w-[440px] max-w-[92vw]">
      <div className="text-[15px] font-bold">이메일로 내보내기</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        금고 번들을 입력한 이메일로 보내드려요. 먼저{' '}
        <span className="font-mono text-fg-soft">확인 링크</span>가 담긴 메일이 가고, 그 링크를
        연 뒤 <span className="font-mono text-fg-soft">확인 코드</span>를 넣어야 실제 파일이 담긴
        메일이 발송됩니다. 코드는 메일이 아니라 이 화면에만 표시돼요 — 주소를 잘못 적었을 때
        낯선 사람이 링크만으로 받아가지 못하게 하려는 장치입니다. 비밀 값은 암호화되어 있지만,
        서비스명·라벨·컬렉션명·메모 같은 메타데이터는 평문으로 포함되어 이 메일을 중계하는
        매니저와 메일 제공자가 볼 수 있어요.
      </p>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && canRun) void run()
        }}
        placeholder="목적지 이메일 주소"
        autoFocus
        className="mt-[14px] w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
      />
      {code && (
        <div className="mt-[14px] rounded-xl border border-[rgba(62,207,142,.35)] bg-[rgba(62,207,142,.07)] px-4 py-[14px] text-center">
          <div className="text-[11.5px] text-muted">확인 페이지에 입력할 코드</div>
          <div className="mt-1 font-mono text-[30px] font-bold tracking-[.28em] text-fg">{code}</div>
          <div className="mt-1 text-[11px] text-dim-3">
            이 창을 닫으면 코드를 다시 볼 수 없어요 — 발송이 끝날 때까지 열어 두세요.
          </div>
        </div>
      )}
      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          {code ? '닫기' : '취소'}
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
          {busy ? '요청 중…' : code ? '다시 보내기' : '확인 메일 보내기'}
        </button>
      </div>
    </Modal>
  )
}
