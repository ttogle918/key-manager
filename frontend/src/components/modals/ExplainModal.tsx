// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { useKeylens } from '@/store/keylensStore'
import { isAllowedUrl, isSafeExternalUrl } from '@/data/services'

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
  const approvedIndices = useKeylens((s) => s.explainApprovedIndices)
  const approveDiscovery = useKeylens((s) => s.approveDiscovery)
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
              // 🟢 known 등급은 지식베이스 docs_url을 그대로 표시(설계 스펙 tier 표) — 화이트리스트
              // 통과분만(KeyHelp.tsx의 docsUrl 처리와 동일한 방어적 패턴). ai_verified는 Tavily
              // 검색으로 확인된 링크라 도메인 화이트리스트 대상이 아니다(설계 판단 A) — https
              // 프로토콜만 검증한다.
              const docsUrl =
                b.tier === 'known'
                  ? isAllowedUrl(b.docs_url)
                    ? b.docs_url
                    : null
                  : isSafeExternalUrl(b.docs_url)
                    ? b.docs_url
                    : null
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
                    className="absolute -top-[18px] left-0 flex items-center gap-[4px] whitespace-nowrap rounded-[3px] px-[4px] text-[10px] font-semibold text-white"
                    style={{ background: style.border.split(' ')[2] }}
                  >
                    {b.label}
                    {docsUrl && (
                      <a
                        href={docsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="공식 문서 열기"
                        className="underline decoration-dotted underline-offset-2 text-white/90 hover:text-white"
                      >
                        문서
                      </a>
                    )}
                    {b.tier !== 'known' && !approvedIndices.has(i) && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          void approveDiscovery(i)
                        }}
                        title="이 추정을 저장해 다음번에 재검색 없이 재사용"
                        className="cursor-pointer rounded-[2px] bg-white/20 px-[3px] text-white hover:bg-white/35"
                      >
                        저장
                      </button>
                    )}
                    {b.tier !== 'known' && approvedIndices.has(i) && (
                      <span className="text-white/70">✓ 저장됨</span>
                    )}
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
