// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
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

  return (
    <Modal open={!!target} onClose={cancel} title="값 교체" className="w-[420px]">
      <div className="text-[15px] font-bold">값 교체 (회전)</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        <span className="font-mono text-fg-soft">{target?.varName}</span> 의 값을 새로 발급받은 값으로 교체합니다.
        <br />
        옛 값은 즉시 폐기되어 복구할 수 없고, 교체는 이력에 기록됩니다.
      </p>
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
