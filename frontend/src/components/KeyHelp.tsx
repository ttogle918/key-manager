// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import {
  CONSOLE_URL,
  isAllowedUrl,
  resolveIssueUrl,
  SVC_PREREQ,
  SVC_STEPS,
  TYPE_MAP,
} from '@/data/services'

/** 외부 콘솔 링크 — 새 탭·noopener(자동 이동/전송 없음). */
function ExtLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-[3px] rounded-[6px] border border-border bg-chip px-[9px] py-[4px] text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
    >
      {children}
    </a>
  )
}

/**
 * 키 발급 도움말 (GUIDE-1) — "이 키가 무슨 역할인지 + 어디서 발급받는지".
 * 데이터는 지식베이스(`/knowledge`)에서 오며, 없으면 아무것도 그리지 않는다(하위호환).
 * 외부 링크만 열고(새 탭) 우리 쪽에서 어떤 데이터도 전송하지 않는다.
 */
export function KeyHelp({
  service,
  typeKey,
  project,
}: {
  service: string
  typeKey: string
  /** 저장된 프로젝트/ID — 딥링크(GUIDE-1 B) 치환에 사용. ID 형태가 아니면 기본 콘솔로 폴백. */
  project?: string | null
}) {
  const [open, setOpen] = useState(false)
  const t = TYPE_MAP[service]?.find((o) => o.v === typeKey)
  if (!t) return null
  // 발급 링크: 항목 project 로 딥링크 해석(치환 or 폴백) + 화이트리스트 통과분만
  const issueUrl = resolveIssueUrl(t.issueUrl || CONSOLE_URL[service], project)
  const docsUrl = isAllowedUrl(t.docsUrl) ? t.docsUrl! : null
  const steps = SVC_STEPS[service] || []
  const prereq = SVC_PREREQ[service] || null
  if (!t.role && !issueUrl && !docsUrl && !steps.length) return null

  return (
    <div className="w-full rounded-lg border border-line bg-inset px-3 py-[10px]">
      {t.role && (
        <div className="flex items-start gap-[7px] text-[12px] leading-[1.5] text-muted-2">
          <span className="relative top-[2px] flex-none text-[11px] text-dim">🔑</span>
          <span>{t.role}</span>
        </div>
      )}
      <div className="mt-[9px] flex flex-wrap items-center gap-[6px]">
        {issueUrl && <ExtLink href={issueUrl}>발급받기 →</ExtLink>}
        {docsUrl && <ExtLink href={docsUrl}>문서 →</ExtLink>}
        {(steps.length > 0 || prereq) && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="cursor-pointer rounded-[6px] border border-transparent px-[8px] py-[4px] text-[11px] font-semibold text-faint hover:text-fg-soft"
          >
            발급 방법 {open ? '▾' : '▸'}
          </button>
        )}
      </div>
      {open && (
        <div className="mt-[9px] border-t border-line pt-[9px]">
          {prereq && (
            <div className="mb-[7px] flex items-start gap-[6px] text-[11.5px] leading-[1.5] text-dim">
              <span className="flex-none font-semibold text-muted-2">사전조건</span>
              <span>{prereq}</span>
            </div>
          )}
          {steps.length > 0 && (
            <ol className="m-0 list-none space-y-[5px] p-0">
              {steps.map((s, i) => (
                <li key={i} className="flex items-start gap-[7px] text-[11.5px] leading-[1.5] text-muted-2">
                  <span className="flex size-[16px] flex-none items-center justify-center rounded-full bg-chip text-[10px] font-bold text-faint">
                    {i + 1}
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}
