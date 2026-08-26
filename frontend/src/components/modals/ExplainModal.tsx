// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { useKeylens } from '@/store/keylensStore'

const TIER_STYLE: Record<string, { border: string; bg: string; badge: string }> = {
  known: { border: '2px solid #3ECF8E', bg: 'rgba(62,207,142,.08)', badge: '분류됨' },
  ai_verified: { border: '2px dashed #E3B341', bg: 'rgba(227,179,65,.08)', badge: 'AI 추정(확인)' },
  ai_unverified: { border: '2px dashed #6B7280', bg: 'rgba(107,114,128,.08)', badge: 'AI 추정' },
}

/** "이 화면 설명해줘" 결과 모달(1단계) — 스크린샷 원본 비율 위에 박스+라벨 오버레이. */
export function ExplainModal() {
  const open = useKeylens((s) => s.explainOpen)
  const loading = useKeylens((s) => s.explainLoading)
  const boxes = useKeylens((s) => s.explainBoxes)
  const image = useKeylens((s) => s.analyzedImage)
  const close = useKeylens((s) => s.closeExplain)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)

  return (
    <Modal open={open} onClose={close} title="이 화면 설명" className="w-[720px] max-w-[94vw]">
      <div className="text-[15px] font-bold">이 화면 설명</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        초록 실선은 이미 아는 서비스, 회색/노랑 점선은 AI 추정이에요 — AI 추정은 틀릴 수 있습니다.
      </p>
      {loading && (
        <div className="mt-4 py-8 text-center text-[13px] text-muted">로컬 LLM이 분석 중…</div>
      )}
      {!loading && image && image !== 'sample' && (
        <div className="relative mt-3 inline-block max-w-full">
          <img
            src={image}
            alt="분석한 스크린샷"
            className="block max-h-[70vh] max-w-full rounded-lg"
            onLoad={(e) => {
              const el = e.currentTarget
              setNaturalSize({ w: el.naturalWidth, h: el.naturalHeight })
            }}
          />
          {naturalSize &&
            boxes.map((b, i) => {
              const style = TIER_STYLE[b.tier] ?? TIER_STYLE.ai_unverified
              return (
                <div
                  key={i}
                  title={`${b.text} → ${b.label}`}
                  className="absolute rounded-[2px]"
                  style={{
                    left: `${(b.x / naturalSize.w) * 100}%`,
                    top: `${(b.y / naturalSize.h) * 100}%`,
                    width: `${(b.w / naturalSize.w) * 100}%`,
                    height: `${(b.h / naturalSize.h) * 100}%`,
                    border: style.border,
                    background: style.bg,
                  }}
                >
                  <span
                    className="absolute -top-[18px] left-0 whitespace-nowrap rounded-[3px] px-[4px] text-[10px] font-semibold text-white"
                    style={{ background: style.border.split(' ')[2] }}
                  >
                    {b.label}
                  </span>
                </div>
              )
            })}
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          닫기
        </button>
      </div>
    </Modal>
  )
}
